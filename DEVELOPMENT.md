# X-ONU Dashboard Development Guide

This document describes the internal architecture and development workflow for X-ONU Dashboard.

For installation, configuration, supported features, alert settings, notification providers, and normal operation, see [README.md](README.md).

## Architecture Overview

X-ONU Dashboard is a Flask application with two independent telemetry collection paths:

```text
8311 JSON metrics endpoint ──> Core Collector ────────┐
                                                      │
ONT SSH / pontop ────────────> AdvancedCollector ─────┤
                                                      v
                                                   SQLite
                                                      │
                                  ┌───────────────────┼───────────────────┐
                                  v                   v                   v
                            AlertManager        Flask API        History queries
                                  │                   │
                                  v                   v
                        NotificationManager    Web interface
```

Core telemetry is collected from the 8311 JSON metrics endpoint.

Advanced telemetry is optional and is collected independently over SSH. Failure of the SSH collector must not cause the core collector to report the ONT as offline.

Both collectors store historical data in SQLite and feed telemetry into the server-side alert system.

Alert generation and notification delivery are intentionally separate. An alert can be generated and stored even when external notifications are disabled or a notification provider is unavailable.

## Source Layout

### `app.py`

Main Flask application and core telemetry collector.

Responsibilities include:

- Flask application setup and HTTP routes
- Core 8311 JSON telemetry collection
- Core telemetry persistence
- Core history queries
- Core alert processing
- API endpoints used by the web interface
- Startup of the core and advanced collectors
- Integration with retention management

Application-level objects are initialized when the module starts, including the database, retention manager, advanced collector, and background collection threads.

Because collectors are started within the application process, the production Gunicorn configuration intentionally uses a single worker. Starting multiple worker processes without redesigning collector ownership could create duplicate collectors and duplicate alert evaluation.

Threads may still be used within that single process for HTTP handling and background work.

### `advanced.py`

Implements optional SSH-based advanced telemetry collection.

`AdvancedCollector` is responsible for:

- Connecting to the ONT over SSH
- Executing supported `pontop` and system commands
- Parsing advanced XGS-PON telemetry
- Selecting the active Ethernet data GEM
- Calculating traffic rates from byte-counter changes
- Storing advanced telemetry samples
- Feeding advanced metrics into the alert system
- Providing current and historical advanced telemetry to the application

Advanced collection runs independently from core JSON telemetry.

#### GEM selection

The ONT may expose multiple GEM entries.

The collector looks for valid Ethernet GEM candidates and excludes GEM ID `65534`. When multiple candidates are available, it selects the candidate with the greatest combined downstream and upstream byte count.

This heuristic is intended to identify the GEM carrying subscriber Ethernet traffic rather than assuming a fixed GEM ID.

A fallback permits selection of an Ethernet GEM when allocation status is not reported as `Valid`, allowing useful telemetry on firmware or states where that field is incomplete.

Changes to this logic should be tested against real `pontop` output from supported ONTs.

#### Traffic-rate calculation

Download and upload rates are calculated from changes in the ONT byte counters between collection cycles.

A negative counter delta is treated as a counter reset rather than negative network traffic. This can occur when the ONT reboots or its GEM counters reset.

The previous counter sample therefore acts as a baseline for the next rate calculation.

### `alerts.py`

Contains the server-side alert engine.

The alert system evaluates telemetry received from the collectors and records alert events in SQLite.

Responsibilities include:

- Alert configuration
- Threshold evaluation
- Warning debounce behavior
- Severity assignment
- Counter-delta alerts
- Counter cooldown behavior
- Recovery events
- Alert history persistence
- Coordination with notification delivery

Counter-based alerts are based on increases between observations rather than simply checking whether an ONT lifetime counter is non-zero.

This distinction is important: an existing historical error count should not repeatedly generate a new alert when no new errors have occurred.

When modifying counter handling, preserve the concepts of:

- baseline establishment
- positive counter deltas
- counter resets
- configured minimum deltas
- cooldown periods

#### TX health profiles

TX optical health uses configuration schema version `2`. The persisted `quality.tx_power` object has this shape:

```json
{
  "profile": "legacy",
  "low_alarm": 1,
  "low_warning": 2,
  "high_warning": 7,
  "high_alarm": 8,
  "cosmetic_great_low": 4,
  "cosmetic_great_high": 5
}
```

`high_warning` and `high_alarm` are independently optional. JSON `null` means the boundary is disabled. Do not replace a disabled boundary with `Infinity`, `999`, the SFF-8472 maximum, or another sentinel.

Supported profile identifiers are:

- `legacy`: exact original dashboard grading and alert boundaries.
- `xgsponst2001-a01`: low alarm `2.00 dBm`, low warning `3.00 dBm`, and no high-side warning or alarm.
- `custom`: user-edited threshold values.

The XGSPONST2001 A-01 module stores `0xFFFF` for both high TX threshold words. That value decodes to approximately `8.16 dBm` because it is the maximum representable SFF-8472 TX-power value. It is treated as an absent threshold, not as a calibrated alarm.

Operational classification is NORMAL, WARNING, ALARM, or UNKNOWN. The Legacy profile retains GOOD, FAIR, POOR, and cosmetic GREAT display labels for compatibility, but their operational levels are still good, warn, and bad. GREAT must never override a real warning or alarm and must never trigger an alert.

The authoritative Python classifier is the pure `classify_tx_power()` function in `tx_health.py`. The browser counterpart is in `static/tx_health.js`. Both consume the persisted configuration, and both must pass `tests/tx_classification_cases.json`. Never reintroduce separate hard-coded thresholds in `static/dashboard.js`.

Profile and threshold changes reset only these in-memory TX keys:

- the previous TX classification
- the active TX warning/alarm level
- the pending TX warning debounce counter

RX, thermal, reachability, active-alarm, GEM, and counter state must not be reset. Re-baselining prevents the policy change itself from generating a false transition. Historical telemetry and alert events are never reclassified or rewritten.

TX classification and state-transition processing are held under the same re-entrant manager lock used when activating and re-baselining a changed TX policy. Preserve this atomic boundary; otherwise a collector sample could be classified under one policy and processed after another policy becomes active.

Unversioned saved configurations are normalized in memory. Exact original defaults become `legacy`; user-edited values become `custom`. The stored row is not rewritten merely because the application loaded it. An explicit settings save persists schema version `2`. Do not infer migration consent from values that happen to match a default.

### `notifications.py`

Implements external notification delivery.

Supported providers include:

- Discord
- ntfy
- Gotify
- Pushover
- Generic Webhook

Notification delivery is asynchronous and intentionally isolated from telemetry collection and alert storage.

New alert events are placed into a FIFO notification queue. The notification worker processes those events separately so a slow, unreachable, or incorrectly configured notification service cannot block telemetry collection.

Provider failures should remain contained within the notification subsystem.

Alert generation must not depend on successful notification delivery.

### `retention.py`

Manages telemetry and alert-history retention.

Telemetry retention applies to both core and advanced telemetry tables. Alert-event retention is configured separately.

The retention system also handles compatibility with installations created before dashboard-managed retention settings existed.

For an existing installation without a saved retention configuration, the legacy `RETENTION_DAYS` value is used to preserve the installation's effective telemetry retention period during migration.

New installations use the dashboard's current default retention values.

Changes to retention initialization must be careful not to silently replace an existing user's effective retention policy.

## Persistent Data

Persistent application state is stored under `/data`.

The primary SQLite database is:

```text
/data/metrics.db
```

The database contains telemetry history as well as application configuration and alert history.

Important data includes:

- core telemetry samples
- advanced telemetry samples
- alert events
- alert configuration
- notification configuration
- retention configuration

The application creates required database structures during startup when they do not already exist.

Database changes should remain compatible with existing installations whenever practical. The dashboard is designed to upgrade an existing persistent `/data` directory without destroying historical telemetry or saved configuration.

## SSH Host-Key Handling

Advanced SSH telemetry uses trust on first use (TOFU).

The first SSH host key is held temporarily while authentication is attempted. It is persisted only after successful authentication.

The trusted key is stored in:

```text
/data/ssh_known_hosts
```

After a key has been saved, future connections require the ONT to present the same host key.

Do not change this behavior to automatically accept replacement keys. A changed host key should require deliberate intervention rather than silently replacing the trusted key.

## Alert and Notification Flow

The intended event flow is:

```text
Telemetry sample
      │
      v
 AlertManager
      │
      ├── no state/event change ──> continue
      │
      v
 Alert event
      │
      ├──> SQLite alert history
      │
      └──> Notification queue
                  │
                  v
          Notification worker
                  │
                  v
          Enabled providers
```

Alert storage occurs independently of external notification delivery.

This separation is deliberate. Do not make telemetry collection or alert persistence wait for a network notification request.

## Flask API

The Flask API is used by the browser interface to retrieve telemetry, history, alerts, and configuration.

The application exposes APIs for areas including:

- current core telemetry
- core telemetry history
- current advanced telemetry
- advanced telemetry history
- alert events and alert counts
- alert configuration
- available TX health profiles
- notification configuration
- retention configuration

Alert history supports `limit` and `offset` so the browser can paginate stored events without loading the entire retained history.

When adding or changing an API:

1. Keep existing clients and saved configuration in mind.
2. Validate user-supplied values server-side.
3. Avoid returning notification credentials or SSH passwords unnecessarily.
4. Keep telemetry collection independent from browser activity.

The collectors are server-side processes. The dashboard does not need to remain open in a browser for telemetry, alerts, or notifications to operate.

## Frontend

The browser interface is implemented with HTML templates and JavaScript under:

```text
web_templates/
static/
```

Important JavaScript files include:

- `dashboard.js` — main dashboard telemetry and UI behavior
- `tx_health.js` — pure browser-side TX classification
- `alerts.js` — alert and notification settings interface behavior
- `alert_history.js` — paginated alert-history interface
- `theme.js` — theme selection and persistence

HTML templates provide the corresponding pages and reusable content.

The frontend should consume the Flask API rather than duplicating server-side monitoring logic in the browser.

## Background Processing

The application performs several operations outside normal browser requests:

- core telemetry polling
- advanced SSH telemetry polling
- server-side alert evaluation
- asynchronous notification delivery
- retention cleanup

These operations are intended to continue whether or not a user has the dashboard open.

When changing startup or threading behavior, verify that a change cannot accidentally start duplicate collectors or duplicate notification processing.

## Design Principles

When modifying the project, preserve these behavioral boundaries unless a deliberate architectural change is being made.

### Core telemetry must stand alone

SSH telemetry is optional. Loss of SSH access must not make an otherwise reachable ONT appear offline.

### Collection is server-side

Monitoring must continue without an open browser.

### Alerts are not notifications

Alert detection and storage must work even when every notification provider is disabled or failing.

### Historical counters need baselines

ONT counters are generally cumulative. Alerting on the existence of a non-zero counter is different from alerting on newly accumulated errors.

### Counter resets are normal events

An ONT reboot or subsystem reset can cause cumulative counters to decrease. A reset must not be interpreted as a negative traffic rate or an unexpectedly large error delta.

### Persistent data belongs in `/data`

Container replacement and application upgrades should not destroy telemetry history or configuration when the persistent data directory is preserved.

### Existing installations matter

Database initialization, retention migration, and configuration changes should avoid silently changing established behavior.

### ONT behavior should be verified against hardware

Some advanced parsing and GEM-selection behavior depends on actual 8311 firmware and `pontop` output. Avoid replacing hardware-tested behavior based only on assumptions about how an ONT should report data.

## Building Locally

Clone the repository and build the image:

```bash
docker build -t x-onu-dashboard .
```

Run the locally built image with a separate development data directory:

```bash
docker run -d \
  --name x-onu-dashboard-dev \
  --restart unless-stopped \
  -p 8767:8080 \
  -v ./data-dev:/data \
  x-onu-dashboard
```

Using a separate container name, host port, and data directory helps prevent development work from modifying a production installation.

Adjust ONT and SSH environment variables as required for the development environment.

## Development Workflow

A safe development workflow is:

1. Start from a clean Git working tree.
2. Make changes in the source checkout rather than inside the production container.
3. Build a separate development image.
4. Run it with a separate container name, port, and persistent data directory.
5. Test against the intended ONT and 8311 firmware behavior.
6. Review the Git diff before committing.
7. Do not replace the production container until the change has been validated.

For documentation-only changes, verify that the diff contains only Markdown, comments, or docstrings and does not alter executable behavior.

## Before Submitting Changes

At minimum:

```bash
git status --short
git diff --check
git diff
```

For Python changes, also verify that modified modules compile successfully before building the container.

Run the automated TX profile, classification-parity, migration, and alert-state tests with:

```bash
python3 -m unittest discover -s tests -v
node tests/test_tx_health.js
node tests/test_alert_settings.js
```

Check Python and JavaScript syntax with:

```bash
python3 -m compileall -q .
node --check static/tx_health.js
node --check static/dashboard.js
node --check static/alerts.js
```

For changes involving collectors, alerts, retention, or notifications, test both normal operation and failure behavior. A failure in an optional subsystem should not unexpectedly stop unrelated monitoring.

## Project Scope

X-ONU Dashboard is primarily developed and hardware-tested against the EXEN X-ONU-SFPP and compatible ONTs running 8311 community firmware.

Compatibility changes for other hardware or firmware should avoid breaking behavior already validated on the project's primary supported platform.
