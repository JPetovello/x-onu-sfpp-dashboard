# Web Interface

The dashboard provides five primary telemetry and administration pages:

- **Dashboard** (`/`) — health overview, thermal gauges, optical and traffic monitoring, and recent alerts.
- **Advanced** (`/advanced`) — detailed system and PON telemetry and historical charts.
- **Diagnostics** (`/diagnostics`) — explicitly requested, allowlisted troubleshooting profiles.
- **Alerts & Notifications** (`/alerts-settings`) — thresholds, notification providers, and retention settings.
- **Alert History** (`/alert-history`) — recorded events and pagination.

The interface uses self-hosted HTML, CSS, and JavaScript. Historical charts retain their time-range controls, including the 60-minute view.


## Optional Browser Authentication

When `DASHBOARD_AUTH_MODE=browser`, visits without a valid session are
redirected to **Login** (`/login`). The login page offers **Remember This
Browser**, with 1-, 3-, 7-, 14- and 30-day durations (default: 7 days).

Authenticated users can open **Trusted Browsers** (`/trusted-browsers`) to
review their active sessions and expiration dates or revoke browser access.
The current browser is marked. Revoking it or using **Sign out** requires a
new login.

Trusted Browsers uses the same redesigned 1376px maximum page width,
compact header, navigation styling, and theme controls as the main
dashboard pages. Session cards adapt to narrow screens, placing
full-width revoke buttons beneath their corresponding session details.

These controls are not shown in HTTP Basic mode. Browser mode requires a
server-configured HTTPS origin and a trusted HTTPS reverse proxy.

## Dashboard

The main Dashboard at `/` is intended to answer:

> Is my ONT healthy?

It provides the at-a-glance operational view:

- Overall ONT status
- PLOAM state
- Overall PON health
- RX and TX optical levels
- TX bias and module voltage
- Live download and upload rate
- Recent alerts

The core Dashboard continues to operate when optional SSH telemetry is disabled or temporarily unavailable.

## Advanced

The Advanced page at `/advanced` is intended to answer:

> What exactly is my ONT doing?

It contains the more detailed monitoring views:

- Optical and CPU temperatures
- ONT uptime
- Memory usage and system load
- FEC status
- PON error counters
- Active alarms and GEM key-error counters
- Historical optical charts
- Historical temperature charts
- Historical traffic charts
- Optical module information
- Ethernet GEM and allocation information

Advanced telemetry depends on optional SSH access to the ONT. When SSH telemetry is disabled or unavailable, the affected values show an unavailable state without causing the core Dashboard to report the ONT itself as offline.

## Diagnostics

The Diagnostics page at `/diagnostics` is intended for explicit troubleshooting:

> What is going on at the ONT?

Diagnostics are **on-demand only**. Opening the page does not run SSH commands.

Standard Diagnostics profiles are:

- **Overview** — ONT status, capability/configuration, LAN interface status and counters, active alarms, optical interface status, and optical interface information.
- **Counters** — allocation counters and upstream/downstream PLOAM counters.

Expert Diagnostics profiles expose deeper troubleshooting pages:

- **Datapath** — raw CQM offload, CQM queue-map, Datapath Ports, and Datapath QoS views.
- **PPv4** — raw buffer-manager, queue-rate, queue-statistics, tree, and QStats views.
- **Burst Profile** — raw Debug Burst Profile output.

Expert output is intentionally presented as raw technical information. The dashboard does not assign health grades or inferred alarm meanings to these undocumented fields.

The user explicitly selects a profile and chooses **Run Diagnostics** before a diagnostic request is made.

Diagnostic commands are fixed by the application. The browser cannot submit an arbitrary shell or `pontop` command.

Diagnostic output is returned to the requesting browser and is not added to telemetry history or fed into alert processing.

Only one diagnostic operation runs at a time per dashboard process. If another request is already active, the later request fails quickly with a non-fatal busy message instead of waiting or starting another SSH workload.

Diagnostics require optional SSH telemetry to be configured.

## Alerts & Notifications

Alert thresholds, notification providers, telemetry retention, and alert-history retention are managed from the separate **Alerts & Notifications** page.

The main Dashboard continues to show recent alerts without using space for configuration controls.
