# X-ONU Dashboard Development Guide

This document describes the internal architecture and development workflow for X-ONU Dashboard.

For installation, configuration, supported features, alert settings, notification providers, normal operation, and user-facing UCG Fiber helper instructions, see [README.md](README.md).

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

Dashboard authentication, browser security headers, ONT TLS verification, history downsampling, alert runtime-state persistence, and notification destination validation are application hardening layers around this same core runtime architecture. They do not change the two-collector model shown above.

The optional UCG Fiber ONT-management helper under `examples/ucg-fiber/` is not part of this runtime architecture. It runs independently on a UCG Fiber and exists only to help maintain management access to an ONT installed directly in the gateway.

## Source Layout

### `app.py`

Main Flask application and core telemetry collector.

Responsibilities include:

- Flask application setup and HTTP routes
- Optional dashboard authentication
- Browser security headers
- ONT TLS verification configuration
- Core 8311 JSON telemetry collection
- Core telemetry validation and persistence
- Core history queries and SQL-side downsampling
- Core alert processing
- API endpoints used by the web interface
- Health endpoint used by container health checking
- Startup of the core and advanced collectors
- Integration with retention management

Application-level objects are initialized when the module starts, including the database, retention manager, advanced collector, alert manager, and background collection threads.

Because collectors are started within the application process, the production Gunicorn configuration intentionally uses a single worker. Starting multiple worker processes without redesigning collector ownership could create duplicate collectors and duplicate alert evaluation.

Threads may still be used within that single process for HTTP handling and background work.

Core telemetry exposed to browser-facing JSON must be JSON-safe. Non-numeric or non-finite values such as `NaN` and `Infinity` must not be allowed to poison API responses. Preserve the current normalization behavior when changing parsing or API serialization.

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
- Running fixed, on-demand diagnostic profiles for troubleshooting

Advanced background collection runs independently from core JSON telemetry.

Diagnostics are deliberately separate from the background collection loop. A diagnostic request opens its own SSH connection, executes only a fixed server-side profile, returns the resulting sections to the requester, and closes the connection.

Diagnostic output is not persisted as telemetry and is not fed into alert processing.

Never accept an arbitrary shell command, `pontop` page name, or other executable command text from a browser request. Diagnostic profiles must remain explicitly allowlisted in server-side code.

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
- Runtime-state persistence across restarts
- Policy-change rebaselining
- Coordination with notification delivery

Counter-based alerts are based on increases between observations rather than simply checking whether an ONT lifetime counter is non-zero.

This distinction is important: an existing historical error count should not repeatedly generate a new alert when no new errors have occurred.

When modifying counter handling, preserve the concepts of:

- baseline establishment
- positive counter deltas
- counter resets
- configured minimum deltas
- cooldown periods
- persisted runtime baselines
- rebaselining after policy changes

Runtime alert state is persisted so a container or application restart does not automatically discard every active baseline, debounce state, and transition context.

Configuration changes deliberately rebaseline the affected policy state instead of treating the configuration change itself as a telemetry transition. Do not broadly reset unrelated alert state when only one policy area changes.

#### PLOAM operational state

PLOAM health must be evaluated against the configured operational state rather than a separate browser hard-coded value.

The default operational state is `51`, but both server and browser behavior must consume the configured value so installations using a different valid operational state remain consistent.

#### TX health profiles

TX optical health uses configuration schema version `3`. The persisted Legacy `quality.tx_power` object has this shape:

```json
{
  "profile": "legacy",
  "operating_min": null,
  "operating_max": null,
  "low_alarm": 1,
  "low_warning": 2,
  "high_warning": 7,
  "high_alarm": 8,
  "cosmetic_great_low": 4,
  "cosmetic_great_high": 5
}
```

`high_warning` and `high_alarm` remain independently optional for Custom profiles. JSON `null` means the boundary is disabled. Do not replace a disabled boundary with `Infinity`, `999`, the SFF-8472 maximum, or another sentinel.

Supported profile identifiers are:

- `legacy`: exact original dashboard grading and alert boundaries.
- `xgsponst2001-a01`: inclusive `4.00-9.00 dBm` XGS-PON operating envelope with no WARNING state.
- `custom`: user-edited threshold values.

The named XGSPONST2001 A-01 profile uses this distinct shape:

```json
{
  "profile": "xgsponst2001-a01",
  "operating_min": 4.0,
  "operating_max": 9.0,
  "low_alarm": null,
  "low_warning": null,
  "high_warning": null,
  "high_alarm": null,
  "cosmetic_great_low": null,
  "cosmetic_great_high": null
}
```

Values below `operating_min` or above `operating_max` are ALARM; both boundaries themselves are NORMAL. Because the specification defines no intermediate warning bands, an out-of-spec observation follows the immediate alarm path rather than warning debounce.

The EEPROM investigation is background evidence, not this named profile's operational source. The module reports low alarm `2.00 dBm`, low warning `3.00 dBm`, and `0xFFFF` for both high TX threshold words. `0xFFFF` decodes to approximately `8.16 dBm` because it is the maximum representable SFF-8472 TX-power value. Those four EEPROM values are not used by the specification-driven profile.

Operational classification is NORMAL, WARNING, ALARM, or UNKNOWN. The Legacy profile retains GOOD, FAIR, POOR, and cosmetic GREAT display labels for compatibility, but their operational levels are still good, warn, and bad. GREAT must never override a real warning or alarm and must never trigger an alert.

The authoritative Python classifier is the pure `classify_tx_power()` function in `tx_health.py`. The browser counterpart is in `static/tx_health.js`. Both consume the persisted configuration, and both must pass `tests/tx_classification_cases.json`. Never reintroduce separate hard-coded thresholds in `static/dashboard.js`.

Profile and threshold changes reset only these in-memory TX keys:

- the previous TX classification
- the active TX warning/alarm level
- the pending TX warning debounce counter

RX, thermal, reachability, active-alarm, GEM, and counter state must not be reset. Re-baselining prevents the policy change itself from generating a false transition. Historical telemetry and alert events are never reclassified or rewritten.

TX classification and state-transition processing are held under the same re-entrant manager lock used when activating and re-baselining a changed TX policy. Preserve this atomic boundary; otherwise a collector sample could be classified under one policy and processed after another policy becomes active.

Unversioned saved configurations are normalized in memory. Exact original defaults become `legacy`; user-edited values become `custom`. Version 2 Legacy and Custom configurations gain disabled operating-envelope fields without changing their thresholds. A version 2 `xgsponst2001-a01` configuration becomes Custom in memory so its former `2.00/3.00 dBm` behavior is preserved rather than silently adopting the new specification policy. The stored row is not rewritten merely because the application loaded it. An explicit settings save persists schema version `3`. Do not infer migration consent from values that happen to match a default.

### `notifications.py`

Implements external notification delivery.

Supported providers include:

- Discord
- ntfy
- Gotify
- Pushover
- Generic Webhook

Notification delivery is asynchronous and intentionally isolated from telemetry collection and alert storage.

New alert events are placed into a bounded FIFO notification queue. When the queue reaches its configured maximum size, the queue policy preserves newer work rather than allowing an unbounded backlog to consume memory indefinitely.

The notification worker processes events separately so a slow, unreachable, or incorrectly configured notification service cannot block telemetry collection.

Notification destinations are treated as untrusted network input. Preserve the current SSRF protections and destination validation when adding providers or changing request behavior.

Provider failures should remain contained within the notification subsystem.

Alert generation must not depend on successful notification delivery.

### `retention.py`

Manages telemetry and alert-history retention.

Telemetry retention applies to both core and advanced telemetry tables. Alert-event retention is configured separately.

The retention system also handles compatibility with installations created before dashboard-managed retention settings existed.

For an existing installation without a saved retention configuration, the legacy `RETENTION_DAYS` value is used to preserve the installation's effective telemetry retention period during migration.

New installations use the dashboard's current default retention values.

Invalid or corrupt retention configuration must fail defensively rather than silently deleting more data than intended.

Changes to retention initialization must be careful not to silently replace an existing user's effective retention policy.

## Persistent Data

Persistent application state is stored under `/data`.

The primary SQLite database is:

```text
/data/metrics.db
```

The database contains telemetry history as well as application configuration, alert history, and persisted alert runtime state.

Important data includes:

- core telemetry samples
- advanced telemetry samples
- alert events
- alert configuration
- alert runtime state
- notification configuration
- retention configuration

The application creates required database structures during startup when they do not already exist.

Database changes should remain compatible with existing installations whenever practical. The dashboard is designed to upgrade an existing persistent `/data` directory without destroying historical telemetry or saved configuration.

Runtime-state persistence must remain compatible with existing databases. Loading persisted state should never make an older installation unusable merely because the stored runtime-state row is absent, incomplete, or from an earlier compatible configuration.

## SSH Host-Key Handling

Advanced SSH telemetry uses trust on first use (TOFU).

The first SSH host key is held temporarily while authentication is attempted. It is persisted only after successful authentication.

The trusted key is stored in:

```text
/data/ssh_known_hosts
```

After a key has been saved, future connections require the ONT to present the same host key.

Do not change this behavior to automatically accept replacement keys. A changed host key should require deliberate intervention rather than silently replacing the trusted key.

## Dashboard Authentication

Dashboard authentication is optional.

It is enabled only when both environment variables are configured:

```text
DASHBOARD_AUTH_USERNAME
DASHBOARD_AUTH_PASSWORD
```

If only one variable is supplied, the application must refuse to start rather than run with a partially configured authentication state.

When authentication is enabled, normal dashboard pages and APIs require valid credentials. The `/api/health` endpoint is intentionally exempt so container health checking does not depend on application credentials.

Do not weaken route coverage when adding pages or API endpoints. New routes should inherit the same authentication boundary unless there is a deliberate, documented reason for an exception.

Credentials must not be returned through configuration APIs, logs, browser JavaScript, or error responses.

## ONT TLS Verification

Core metrics requests support configurable TLS certificate verification.

Relevant environment variables are:

```text
ONT_TLS_VERIFY
ONT_TLS_CA_BUNDLE
```

Do not replace the configurable verification behavior with a global `verify=False` or another unconditional certificate bypass.

When verification is enabled, certificate failures should remain visible as collection failures rather than being silently ignored.

If a custom CA bundle is configured, validate and use it only for the intended ONT HTTPS connection path.

## Browser Security Headers

The Flask application deliberately applies restrictive browser security headers, including:

- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy

The Content Security Policy is intended to keep application resources self-hosted and prevent unexpected script, object, framing, and form-action sources.

When adding frontend dependencies or browser features, prefer self-hosted assets and preserve the restrictive policy. Do not relax CSP merely to make an external script or stylesheet convenient.

Persisted or server-provided alert/error text must be rendered as text, not injected as trusted HTML. Avoid routing untrusted strings through `innerHTML` or equivalent HTML-parsing sinks.

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
      └──> Bounded notification queue
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

The Flask API is used by the browser interface to retrieve telemetry, history, alerts, configuration, and health status.

The application exposes APIs for areas including:

- current core telemetry
- core telemetry history
- current advanced telemetry
- advanced telemetry history
- fixed-profile on-demand diagnostics
- alert events and alert counts
- alert configuration
- available TX health profiles
- notification configuration
- retention configuration
- application health

Alert history supports `limit` and `offset` so the browser can paginate stored events without loading the entire retained history.

Pagination inputs must remain bounded. Large user-controlled offsets or limits must not be allowed to create unbounded work or pathological database behavior.

History endpoints downsample in SQL when appropriate instead of loading an arbitrarily large retained dataset into Python and reducing it afterward. Preserve this property when changing chart history queries.

`/api/diagnostics` is request-driven rather than part of background telemetry collection. It accepts only the supported diagnostic profile names, currently `overview` and `counters`. The selected profile maps to fixed server-side SSH commands; user-controlled command text must never reach the SSH execution layer.

Diagnostic results are transient. They are returned to the current request but are not written to telemetry history and are not evaluated by the alert engine.

When adding or changing an API:

1. Keep existing clients and saved configuration in mind.
2. Validate user-supplied values server-side.
3. Normalize non-finite telemetry before JSON serialization.
4. Avoid returning notification credentials or SSH passwords unnecessarily.
5. Preserve the dashboard authentication boundary.
6. Keep background telemetry collection independent from browser activity.
7. Treat request-driven diagnostics as an explicit exception and keep their command surface fixed and allowlisted.

The collectors are server-side processes. The dashboard does not need to remain open in a browser for telemetry, alerts, or notifications to operate.

### Health endpoint

`/api/health` is used by the container health check.

It should remain lightweight, deterministic, and safe to call without dashboard authentication. Do not make health reporting depend on optional SSH telemetry or an external notification provider.

A healthy application process does not necessarily mean every optional external dependency is reachable. Keep health semantics focused on whether the dashboard service itself is operating.

## Frontend

The browser interface is implemented with HTML templates and JavaScript under:

```text
web_templates/
static/
```

Important JavaScript files include:

- `dashboard.js` — shared Dashboard and Advanced telemetry/UI behavior
- `tx_health.js` — pure browser-side TX classification
- `diagnostics.js` — manual, profile-scoped Diagnostics requests and safe raw-output rendering
- `alerts.js` — alert and notification settings interface behavior
- `alert_history.js` — paginated alert-history interface
- `theme.js` — theme selection and persistence

The primary telemetry pages are:

- `/` — Dashboard: at-a-glance health, optical signal, live traffic, and recent alerts
- `/advanced` — detailed system/PON telemetry and historical charts
- `/diagnostics` — explicitly triggered troubleshooting output

The Dashboard and Advanced pages may share telemetry code, but their templates intentionally expose different levels of detail.

The Diagnostics page must not execute a diagnostic request merely because the page was opened. `diagnostics.js` runs a profile only after explicit user action.

Diagnostic and other server-provided raw text must be rendered through text-safe DOM operations such as `textContent`, not through HTML-parsing sinks.

HTML templates provide the corresponding pages and reusable content.

The frontend should consume the Flask API rather than duplicating server-side monitoring logic in the browser.

Browser display logic must not silently diverge from server-side operational policy. Shared behaviors such as TX classification and configured PLOAM operational state require parity tests when changed.

Untrusted server or persisted text must be inserted with text-safe DOM operations unless the content is explicitly static and trusted.

## Background Processing

The application performs several operations outside normal browser requests:

- core telemetry polling
- advanced SSH telemetry polling
- server-side alert evaluation
- alert runtime-state persistence
- asynchronous notification delivery
- retention cleanup

These operations are intended to continue whether or not a user has the dashboard open.

On-demand Diagnostics are intentionally **not** background processing. They run only for an explicit diagnostic request and must not be added to the normal polling loop.

When changing startup or threading behavior, verify that a change cannot accidentally start duplicate collectors or duplicate notification processing.

## Optional UCG Fiber ONT-Management Helper

The files under:

```text
examples/ucg-fiber/
```

are optional helper material for installations where an X-ONU-SFPP or compatible ONT is installed directly in a UniFi Cloud Gateway Fiber and management access must coexist with PPPoE.

The helper is deliberately separate from the dashboard runtime:

- it runs on the UCG Fiber, not in the dashboard container
- the dashboard does not require it
- the dashboard must continue to work normally when it is not installed
- helper failure must not be treated as a dashboard application failure
- installing or removing the helper is an explicit administrator action

The helper scripts are unofficial community examples. UniFi OS behavior can change between releases, so networking commands and interface assumptions must be treated cautiously.

When changing these scripts:

1. Preserve the warnings and explicit opt-in nature of the helper.
2. Do not assume a fixed physical interface, management subnet, or gateway-side address without validation.
3. Avoid commands that unnecessarily disrupt the PPPoE WAN session.
4. Keep installation and removal steps reversible.
5. Validate POSIX shell syntax.
6. Keep Linux/macOS and Windows installation documentation aligned with the actual files in `examples/ucg-fiber/`.
7. Do not make the dashboard container depend on UCG Fiber-specific behavior.

Detailed user instructions belong in [docs/ucg-fiber-ont-management.md](docs/ucg-fiber-ont-management.md) and [examples/ucg-fiber/README.md](examples/ucg-fiber/README.md), not in the runtime architecture sections of this document.

## Design Principles

When modifying the project, preserve these behavioral boundaries unless a deliberate architectural change is being made.

### Core telemetry must stand alone

SSH telemetry is optional. Loss of SSH access must not make an otherwise reachable ONT appear offline.

### Collection is server-side

Monitoring must continue without an open browser.

### Alerts are not notifications

Alert detection and storage must work even when every notification provider is disabled or failing.

### Notification delivery is bounded

A failed or slow notification destination must not create an indefinitely growing in-memory backlog.

### Historical counters need baselines

ONT counters are generally cumulative. Alerting on the existence of a non-zero counter is different from alerting on newly accumulated errors.

### Counter resets are normal events

An ONT reboot or subsystem reset can cause cumulative counters to decrease. A reset must not be interpreted as a negative traffic rate or an unexpectedly large error delta.

### Alert state survives ordinary restarts

Runtime alert state is persisted deliberately. Avoid changes that turn every normal restart into a complete loss of debounce, baseline, cooldown, or transition context.

### Policy changes rebaseline, not replay history

Changing alert policy should not itself fabricate telemetry transitions or rewrite historical events.

### Persistent data belongs in `/data`

Container replacement and application upgrades should not destroy telemetry history or configuration when the persistent data directory is preserved.

### Existing installations matter

Database initialization, retention migration, and configuration changes should avoid silently changing established behavior.

### Browser-facing data must be safe

Telemetry must be valid JSON, untrusted text must not become executable HTML, and security headers should remain restrictive.

### Network destinations are untrusted input

Notification URLs and similar outbound destinations must preserve SSRF protections. ONT HTTPS certificate verification must remain explicit and configurable rather than globally disabled.

### Optional helpers stay optional

UCG Fiber helper scripts are separate from dashboard runtime behavior. Do not introduce a dependency from the core application onto platform-specific gateway modifications.

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

Adjust ONT, TLS, authentication, and SSH environment variables as required for the development environment.

Do not reuse a production `/data` directory for development testing.

## Development Workflow

A safe development workflow is:

1. Start from a clean Git working tree.
2. Make changes in the source checkout rather than inside the production container.
3. Build a separate development image.
4. Run it with a separate container name, port, and persistent data directory.
5. Test against the intended ONT and 8311 firmware behavior when hardware interaction is relevant.
6. Test security and failure behavior appropriate to the changed subsystem.
7. Review the Git diff before committing.
8. Do not replace the production container until the change has been validated.

For documentation-only changes, verify that the diff contains only Markdown, comments, or docstrings and does not alter executable behavior.

Changes to UCG Fiber helper scripts should be treated as networking/system-script changes rather than ordinary dashboard frontend changes. Do not test an unreviewed helper change against a production WAN path merely to validate syntax.

## Before Submitting Changes

At minimum:

```bash
git status --short
git diff --check
git diff
```

Run the complete Python regression suite with:

```bash
python3 -m unittest discover -s tests -v
```

Run the JavaScript regression suites with:

```bash
node tests/test_tx_health.js
node tests/test_alert_settings.js
node tests/test_dashboard_health.js
node tests/test_alert_rendering.js
node tests/test_diagnostics_ui.js
```

The Diagnostics backend is covered by `tests/test_diagnostics.py`. Those tests must mock SSH execution so routine regression testing cannot contact a real ONT.

The Diagnostics frontend test verifies that loading the script does not automatically fetch diagnostics and that returned diagnostic text is rendered safely.

The TX classification implementations must continue to agree with the shared cases in:

```text
tests/tx_classification_cases.json
```

Check Python syntax with:

```bash
python3 -m compileall -q .
```

Check JavaScript syntax for all maintained frontend files, or at minimum every modified JavaScript file. For example:

```bash
for f in static/*.js; do
  node --check "$f"
done
```

Validate the UCG Fiber helper scripts when they are modified:

```bash
sh -n examples/ucg-fiber/20-ont-management.sh
sh -n examples/ucg-fiber/ont-management-watch.sh
```

For container or startup changes, build the development image and verify that its health check reaches a healthy state.

For authentication changes, test:

- authentication disabled when both variables are unset
- startup refusal for partial configuration
- successful and failed authentication
- `/api/health` remains reachable as intended

For TLS changes, test verification enabled, verification disabled, invalid configuration, and custom CA-bundle handling as applicable.

For notification changes, test queue bounds, provider failure isolation, and SSRF protections.

For alert changes, test restart persistence, policy rebaselining, configured PLOAM operational state, and browser/server classification parity where applicable.

For history changes, test SQL-side downsampling and bounded pagination behavior.

For retention changes, test both valid configuration and corrupt/invalid saved configuration.

For changes involving collectors, alerts, retention, notifications, authentication, TLS, or helper scripts, test both normal operation and failure behavior. A failure in an optional subsystem should not unexpectedly stop unrelated monitoring.

## Project Scope

X-ONU Dashboard is primarily developed and hardware-tested against the EXEN X-ONU-SFPP and compatible ONTs running 8311 community firmware.

Compatibility changes for other hardware or firmware should avoid breaking behavior already validated on the project's primary supported platform.

The UCG Fiber helper is platform-specific optional tooling and should not narrow the dashboard application's broader ability to run anywhere that can reach the ONT management interface.

## Dependency Lock Maintenance

Python dependency intent is recorded in `requirements.in`.

Production container builds install only from `requirements.lock`, which
contains the complete resolved dependency graph with SHA-256 hashes.
The Docker build enforces both `--require-hashes` and
`--only-binary=:all:`.

Do not hand-edit `requirements.lock`.

When dependencies are intentionally changed, regenerate the lock using
`pip-tools==7.6.1`, then run:

    pip-compile --generate-hashes --strip-extras \
      --output-file=requirements.lock requirements.in

After regenerating the lock, review every dependency version change, run
the complete regression suites, build the Docker image, and verify binary
wheel availability for every published architecture.

The Docker base image and GitHub Actions are deliberately pinned to
immutable digests or commit SHAs. Updating those pins must be an explicit,
reviewed maintenance change rather than a floating-tag update.
