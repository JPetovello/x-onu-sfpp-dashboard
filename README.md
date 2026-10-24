# X-ONU-SFPP Dashboard

A lightweight monitoring dashboard for the EXEN X-ONU-SFPP and compatible ONTs running 8311 community firmware.

The dashboard provides live and historical XGS-PON telemetry using the 8311 JSON metrics endpoint, with optional SSH-based advanced monitoring, configurable alerting, alert history, and multiple notification providers.

The browser interface is organized around three telemetry views:

- **Dashboard** — quick operational health, optical signal, live traffic, and recent alerts.
- **Advanced** — detailed system health, PON error counters, historical charts, and module information.
- **Diagnostics** — explicit, on-demand troubleshooting using fixed SSH diagnostic profiles. Diagnostics do not run automatically when the page is opened.

Alert, notification, and retention settings remain on the separate **Alerts & Notifications** page.

## Quick Start (TL;DR)

**Prerequisite:** An X-ONU-SFPP or compatible ONT running 8311 community firmware. Your Docker or Unraid host must be able to reach the ONT management IP.

### Unraid

1. In **Apps**, find and install **X-ONU-SFPP Dashboard** using the [Unraid template](https://github.com/JPetovello/unraid-templates/blob/main/templates/x-onu-sfpp-dashboard.xml).
2. Verify the **ONT Metrics URL** and persistent **Appdata** mapping.
3. Click **Apply**, then open `http://YOUR-UNRAID-IP:8766` (or your configured host port).

### Docker

1. In the [Docker Installation](#docker-installation) command below, set `ONT_URL` to your ONT's metrics endpoint and map `/data` to persistent storage.
2. Run the command to start the container.
3. Open `http://YOUR-DOCKER-HOST-IP:8766` (or your configured host port).

The default metrics endpoint is `https://192.168.11.1/cgi-bin/luci/8311/metrics`. Change it if your ONT uses a different management address.

**Optional:** SSH telemetry adds advanced monitoring and on-demand diagnostics. The [UCG Fiber management helper](docs/ucg-fiber-ont-management.md) is not required if your ONT is already reachable.

**Security:** Keep the dashboard on a trusted network. Do not expose its application port directly to the public Internet.

## Features

Core telemetry does not require SSH and includes:

- RX optical power
- TX optical power
- TX bias current
- Module voltage
- Optical temperature
- CPU temperatures
- PLOAM state
- ONT reachability
- Historical optical and temperature charts
- History ranges of 1 hour, 6 hours, 24 hours, 7 days, and 30 days
- Persistent history-range selection
- Configurable telemetry and alert-history retention

Optional advanced SSH telemetry adds:

- Live XGS-PON download and upload rate
- Downloaded and uploaded byte counters
- FEC upstream/downstream status
- BIP errors
- Corrected and uncorrected FEC counters
- HEC counters
- PLOAM MIC errors
- Active alarms
- GEM key-error counters
- ONT uptime
- Memory usage
- Load averages
- Ethernet GEM / Allocation information
- Optical module information
- Historical traffic charts
- Error-counter deltas over the selected history range

Advanced telemetry is optional. If SSH is disabled or unavailable, the core dashboard continues to operate normally.

## Alerts

The dashboard includes server-side alert monitoring. Alerts are evaluated by the collectors even when the dashboard is not open in a browser.

Alert monitoring includes:

- RX optical power quality changes
- TX optical power quality changes
- Optical and CPU thermal conditions
- PLOAM leaving or returning to the configured operational state
- Core telemetry becoming unreachable or recovering
- Active ONT alarm increases, decreases, and clearing
- GEM key-error increases
- BIP error increases
- Corrected and uncorrected FEC errors
- Corrected and uncorrected PSBd HEC errors
- Corrected and uncorrected FS HEC errors
- PLOAM MIC errors

Alert thresholds, severities, debounce behaviour, minimum counter deltas, and counter cooldowns can be configured from the dedicated **Alerts & Notifications** page.

Warning conditions can require multiple consecutive samples before an alert is generated. Critical conditions can be reported immediately.

Counter alerts are based on increases rather than simply whether a lifetime counter is non-zero. This helps distinguish new errors from historical errors already recorded by the ONT.

### Alert Settings Reference

For detailed alert thresholds, severity rules, warning debounce,
counter cooldowns, recovery events, and notification behaviour,
see the [Alert Settings Reference](docs/alerts.md).

### Recent Alerts and Alert History

Generated alerts are stored in the dashboard SQLite database.

The main dashboard displays the **3 most recent alerts**, keeping the Recent Alerts section compact while still providing immediate visibility into the latest events.

Select **View Alert History →** to open the dedicated Alert History page. Stored alerts are displayed newest first with **25 alerts per page** and **Previous** / **Next** pagination, allowing older retained events to be reviewed without cluttering the main dashboard.

The amount of alert history available depends on the configured alert-history retention period.

Alert events include information such as:

- Timestamp
- Severity
- Alert type
- Metric
- Previous value
- Current value
- Delta
- Human-readable message

Recovery events are also recorded when supported conditions return to normal.

## Notification Providers

The dashboard supports Discord, ntfy, Gotify, Pushover,
Generic Webhook, and Gmail SMTP notifications.

Notifications are sent server-side. Delivery operates
independently of telemetry collection and alert storage.

For provider setup instructions, private destination
restrictions, and credential security, see the
[Notification Providers Guide](docs/notifications.md).

## Data Retention

Telemetry and alert-history retention can be configured from the **Data Retention** panel on the **Alerts & Notifications** page.

Telemetry retention applies to both standard and advanced telemetry samples.

Available telemetry retention periods are:

- 7 days
- 30 days
- 60 days
- 90 days
- 180 days
- 1 year
- Unlimited

New installations default to **90 days** of telemetry history.

Alert-history retention can be configured separately.

Available alert-history retention periods are:

- 30 days
- 90 days
- 180 days
- 1 year
- Unlimited

New installations default to **1 year** of alert history.

Expired records are removed automatically. Selecting **Unlimited** disables automatic cleanup for that data type.

Existing installations preserve their effective telemetry retention setting during upgrade rather than being silently changed to the new-install default.

## Requirements

You need an ONT running compatible 8311 community firmware with the metrics endpoint available at:

    /cgi-bin/luci/8311/metrics

The default endpoint is:

    https://192.168.11.1/cgi-bin/luci/8311/metrics

The Docker host must be able to reach the management IP of the ONT.

For advanced monitoring, SSH access to the ONT is also required.

### Internet-Facing HTTPS

The dashboard can be used over plain HTTP on a trusted local network by
default.

Internet-facing deployments should be placed behind a trusted HTTPS reverse
proxy and configured with:

    REQUIRE_HTTPS=true

When `REQUIRE_HTTPS` is enabled, the dashboard sends:

    Strict-Transport-Security: max-age=31536000

The reverse proxy is responsible for terminating TLS and redirecting or
rejecting plain HTTP traffic. The dashboard does not automatically trust
client-supplied forwarding headers such as `X-Forwarded-Proto`.

Do not expose the dashboard application port directly to the Internet.
Leave `REQUIRE_HTTPS` disabled for ordinary HTTP-only LAN deployments.

### Optional Dashboard Authentication

The dashboard offers two optional authentication modes. Authentication is
**disabled** when both dashboard credential variables are unset.

Set both variables to require authentication:

```text
DASHBOARD_AUTH_USERNAME=admin
DASHBOARD_AUTH_PASSWORD=use-a-strong-password
```

Providing only one credential variable is rejected on startup.

**HTTP Basic authentication** is the default (`DASHBOARD_AUTH_MODE=basic`).
Existing installations retain their current authentication behaviour when
they upgrade without changing this setting.

**Browser authentication** adds a sign-in page, remembered sessions, Sign out,
and a Trusted Browsers page. It requires an HTTPS reverse proxy and these
additional environment variables:

```text
DASHBOARD_AUTH_MODE=browser
DASHBOARD_PUBLIC_ORIGIN=https://dashboard.example.com
```

Replace the sample origin with the exact HTTPS address opened in the browser,
including a port when applicable. An HTTPS origin must not contain a path,
query string, fragment, or embedded username/password. The app validates the
request host and origin for browser authentication. Ordinary HTTP cannot
establish browser sessions.

**Remember This Browser** offers 1, 3, 7, 14, or 30 days (default: 7 days).
Without the option enabled, the cookie is nonpersistent and the server-enforced
session expiry is 12 hours. The server always enforces expiry, and sessions
can be revoked from Trusted Browsers.

Login attempts are rate-limited after five failed attempts in a five-minute
window for the apparent client. By default, clients behind the same reverse
proxy share its login limit. `DASHBOARD_TRUSTED_PROXY_IPS` allows an optional
explicit list of exact trusted reverse-proxy IP addresses for recognizing a
single forwarded client address. Do not trust user-supplied forwarding headers
or hardcode temporary Docker container IPs.

Only hashes of bearer-session tokens are stored in the SQLite database.
Session cookies are Secure, HttpOnly, and SameSite=Lax. Preserve and protect
persistent `/data`, dashboard credentials, and HTTPS proxy configuration.

See [Configuration](docs/configuration.md) and
[Upgrade and Rollback](docs/upgrading.md) for more information.
Never expose the application port directly to the public Internet.

## ONT Management Connectivity

The Docker host must be able to reach the management IP of the ONT. The dashboard does not create or manage that network path for you.

The optional UCG Fiber helper scripts are also usable **without X-ONU-SFPP Dashboard**. They can be used independently to maintain persistent access to an ONT management interface for its web UI, SSH, or other administrative tools.

The helper documentation includes installation paths for Linux/macOS and Windows PowerShell. In all cases, the helper scripts themselves execute on the UCG Fiber gateway, not on the administrator's computer.

### UniFi Cloud Gateway Fiber users

> [!CAUTION]
> **⚠️ USE AT YOUR OWN RISK.** Optional UCG Fiber reference scripts are provided for users whose gateway repeatedly removes a manually configured ONT management address. These scripts modify a **WAN-side interface** and can disrupt Internet access, PPPoE connectivity, ONT management access, or other network services if configured incorrectly. They are unofficial, are not required by the dashboard, and **must be reviewed and adapted for each network before use**.

See [UCG Fiber and Persistent ONT Management Access](docs/ucg-fiber-ont-management.md) and the [`examples/ucg-fiber/`](examples/ucg-fiber/) reference scripts.

## Docker Image

The published Docker image is:

    ghcr.io/jpetovello/x-onu-sfpp-dashboard:latest

## Docker Installation

Basic installation without SSH telemetry:

    docker run -d \
      --name x-onu-dashboard \
      --restart unless-stopped \
      -p 8766:8080 \
      -e ONT_URL="https://192.168.11.1/cgi-bin/luci/8311/metrics" \
      -e POLL_SECONDS="10" \
      -e REQUEST_TIMEOUT="5" \
      -e DATA_DIR="/data" \
      -e SSH_ENABLED="false" \
      -v ./data:/data \
      ghcr.io/jpetovello/x-onu-sfpp-dashboard:latest

The dashboard will then be available on port 8766 of the Docker host.

## Advanced SSH Telemetry

To enable advanced monitoring, provide SSH connection details for the ONT:

    docker run -d \
      --name x-onu-dashboard \
      --restart unless-stopped \
      -p 8766:8080 \
      -e ONT_URL="https://192.168.11.1/cgi-bin/luci/8311/metrics" \
      -e POLL_SECONDS="10" \
      -e REQUEST_TIMEOUT="5" \
      -e DATA_DIR="/data" \
      -e SSH_ENABLED="true" \
      -e SSH_HOST="192.168.11.1" \
      -e SSH_PORT="22" \
      -e SSH_USER="root" \
      -e SSH_PASSWORD="your-password" \
      -e SSH_POLL_SECONDS="30" \
      -e SSH_TIMEOUT="10" \
      -e SSH_COMMAND_TIMEOUT="30" \
      -v ./data:/data \
      ghcr.io/jpetovello/x-onu-sfpp-dashboard:latest

SSH telemetry is collected independently from the core JSON metrics collector.

A failed SSH login or unavailable SSH service does not make the ONT appear offline if the JSON metrics endpoint is still reachable.

## Security Note

`SSH_PASSWORD` is supplied to the container as a Docker environment variable.

Docker environment variables can be inspected by users with access to Docker or the Unraid host. Masking the password field in the Unraid interface only hides it visually; it does not provide secret storage.

Alert and notification configuration is stored in the dashboard's persistent SQLite database. This includes a Gmail App Password when Email notifications are configured. Treat the persistent `/data` directory as sensitive if notification credentials or private notification endpoint URLs have been configured.

Do not expose this dashboard or the ONT management interface directly to the public Internet.

## Configuration

Core telemetry and optional advanced SSH monitoring are
configured using Docker environment variables.

For complete variable descriptions, defaults, TLS settings,
and SSH host-key verification, see the
[Configuration Reference](docs/configuration.md).

## Persistent Data

Historical samples, alert configuration, notification configuration, retention configuration, and alert events are stored in an SQLite database at:

    /data/metrics.db

The `/data` directory should be mapped to persistent storage so history and configuration survive container upgrades and recreation.

For Unraid, the recommended mapping is:

    /mnt/user/appdata/x-onu-dashboard -> /data

The dashboard continues to use the existing core `samples` and `advanced_samples` telemetry tables and automatically adds the database structures required for alert history and configuration.

Existing telemetry history is preserved during upgrade. Enabling browser authentication creates a `browser_sessions` table in the same persistent SQLite database.

## Upgrading Existing Installations

Existing installations can retain their persistent `/data`
directory, including telemetry history and saved settings.

Before upgrading, back up the SQLite database and review
the relevant migration and permissions requirements.

See the [Upgrade and Rollback Guide](docs/upgrading.md)
for detailed instructions.

## Web Interface

The dashboard provides five coordinated pages:

- **Dashboard** — operational health, optical telemetry,
  temperatures, traffic, and recent alerts.
- **Advanced** — detailed PON and system monitoring.
- **Diagnostics** — on-demand troubleshooting.
- **Alerts & Notifications** — alert thresholds,
  notification providers, and data retention.
- **Alert History** — recorded events and pagination.

When browser authentication is enabled, **Login** and **Trusted Browsers** are also available.

Trusted Browsers follows the redesigned dashboard layout, including the
standard header, navigation, and System/Dark/Light theme selector.
On narrow screens, browser-session details and revoke buttons stack
vertically for easier interaction.

For detailed descriptions of each page, see the
[Web Interface Guide](docs/web-interface.md).

## PLOAM State

A PLOAM state of 51 represents O5.1 Associated and is the default operational PLOAM state used by the alert system.

The operational state can be configured from **Alert Settings**.

## Optical Health

The dashboard displays optical quality classifications for RX and TX signal levels.

The dashboard and server-side alert engine use the same persisted threshold policy. Warning and alarm classifications therefore affect overall PON health as well as alert generation. The browser loads that policy from the backend rather than carrying separate hard-coded TX thresholds.

The Legacy TX profile may display GREAT within part of its healthy range. GREAT is cosmetic only and maps to the same healthy operational level as GOOD or NORMAL.

Alert thresholds and the active TX profile are configurable through **Alert Settings**.

## Unraid

X-ONU-SFPP Dashboard is designed to run as a Docker container on Unraid.

Recommended configuration:

    Container WebUI Port: 8080
    Default Host Port:    8766
    Container Data Path:  /data
    Default Appdata Path: /mnt/user/appdata/x-onu-dashboard

Advanced SSH telemetry is optional and can be enabled from the container settings.

Alert configuration and notification provider settings are managed from within the dashboard.

## Development

Developer documentation, architecture, and local build instructions are available in [DEVELOPMENT.md](DEVELOPMENT.md).

## Source

Project repository:

    https://github.com/JPetovello/x-onu-sfpp-dashboard

Issues and bug reports:

    https://github.com/JPetovello/x-onu-sfpp-dashboard/issues

## Development Note

This project was developed with substantial assistance from AI-based coding tools. Project direction, design decisions, hardware testing, validation, deployment, and ongoing maintenance are performed by the project maintainer.

## License

X-ONU-SFPP Dashboard is licensed under the GNU Affero General Public License version 3 or later (AGPL-3.0-or-later).

Copyright (c) 2026 Jeff Petovello
