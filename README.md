# X-ONU Dashboard

A lightweight monitoring dashboard for the EXEN X-ONU-SFPP and compatible ONTs running 8311 community firmware.

The dashboard provides live and historical XGS-PON telemetry using the 8311 JSON metrics endpoint, with optional SSH-based advanced monitoring, configurable alerting, alert history, and Discord notifications.

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
- 1 hour, 6 hour, 24 hour, 7 day, and 30 day history
- Persistent history-range selection

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

Alert thresholds, severities, debounce behavior, minimum counter deltas, and counter cooldowns can be configured from **Alert Settings** in the dashboard.

Warning conditions can require multiple consecutive samples before an alert is generated. Critical conditions can be reported immediately.

Counter alerts are based on increases rather than simply whether a lifetime counter is non-zero. This helps distinguish new errors from historical errors already recorded by the ONT.

### Alert Settings Reference

The **Alert Settings** panel controls when alert events are generated and what severity is assigned to them.

Changing an alert severity does not change when the condition is detected. It changes how the resulting event is classified. Available severities are **Info**, **Warning**, and **Critical**.

The defaults are intended to provide useful monitoring without generating an alert for every small fluctuation. They can be adjusted for the optical levels and behavior normally seen on a particular ONT or network.

#### Warning Debounce

**Warning debounce** is the number of consecutive warning-level samples that must be observed before a signal-quality warning is generated.

Default:

    3 samples

For example, with the default value of `3`, a warning condition must be present for three consecutive samples before the dashboard records a warning.

This helps prevent a brief optical or temperature fluctuation from creating an unnecessary alert.

Poor or critical conditions are not delayed by the warning debounce and can generate an alert immediately.

If a warning condition disappears before the required number of consecutive samples is reached, the pending warning is cleared.

#### RX Power Thresholds

The RX power settings define the receive optical-power ranges used by the alert system.

Defaults:

    Poor low:   -27 dBm
    Fair low:   -24 dBm
    Great low:  -20 dBm
    Great high: -14 dBm
    Poor high:   -8 dBm

The settings exposed in the dashboard define the important boundaries used to decide whether received optical power is normal, warning-level, or poor.

**Poor low** defines the lower extreme. RX power at or beyond the poor range is treated as a critical-quality condition.

**Fair low** defines the transition into the lower warning range.

**Poor high** defines the upper extreme where excessive receive power is considered poor.

The internal **Great** range is used for signal-quality classification and is not normally something that needs to be adjusted.

Because optical power is expressed in negative dBm values, a value such as `-27 dBm` represents less received optical power than `-20 dBm`.

Warning-level RX conditions are subject to **Warning debounce**. Poor conditions can alert immediately. When an active RX warning or critical condition returns to the normal range, a recovery event is generated.

#### TX Power Thresholds

The TX power settings define the transmit optical-power ranges used by the alert system.

Defaults:

    Poor low:   1 dBm
    Fair low:   2 dBm
    Great low:  4 dBm
    Great high: 5 dBm
    Fair high:  7 dBm
    Poor high:  8 dBm

**Poor low** and **Poor high** define the outer transmit-power limits.

**Fair low** and **Fair high** define the warning ranges approaching those limits.

The internal **Great** range is used for signal-quality classification.

Warning-level TX conditions are subject to **Warning debounce**. Poor conditions can alert immediately. When an active TX warning or critical condition returns to the normal range, a recovery event is generated.

#### Thermal Thresholds

Thermal alerts monitor ONT temperature readings.

Defaults:

    Warm: 75 °C
    Hot:  85 °C

**Warm** is a warning-level condition and is subject to **Warning debounce**.

**Hot** is a critical-quality condition and can generate an alert immediately.

When an active thermal warning or critical condition returns to the normal range, a recovery event is generated.

#### GEM Key Errors

GEM key errors are monitored as a counter increase rather than simply checking whether the counter is non-zero.

Defaults:

    Minimum delta: 1
    Severity:      Warning

**Minimum delta** is the minimum increase required before an alert is generated.

For example, with a Minimum Delta of `1`, a GEM key-error counter increasing from `100` to `101` can generate an alert. A counter that remains at `100` does not repeatedly alert merely because its lifetime value is non-zero.

**Severity** controls whether a generated GEM key-error event is recorded as Info, Warning, or Critical.

#### PLOAM State

The alert system monitors whether the ONT is in its configured operational PLOAM state.

Default operational state:

    51 = O5.1 - Associated

The PLOAM settings control the severity assigned to two events:

**Not operational** is used when the ONT is observed outside the configured operational PLOAM state.

Default severity:

    Critical

**Recovered** is used when the ONT returns to the configured operational state.

Default severity:

    Info

If the dashboard starts while the ONT is already in a non-operational PLOAM state, that condition can also generate an alert rather than requiring a transition to occur after startup.

#### Active Alarms

The dashboard monitors the number of active alarms reported by the ONT.

Three severity settings control how changes are reported:

**Increased** is used when the active alarm count rises.

Default severity:

    Critical

**Decreased** is used when the active alarm count falls but remains above zero.

Default severity:

    Info

**Cleared** is used when the active alarm count returns to zero.

Default severity:

    Info

The first observed alarm count establishes the initial baseline and does not by itself generate a change event.

#### ONT Reachability

ONT reachability monitors the core JSON telemetry connection independently from optional SSH telemetry.

**Unreachable** controls the severity used when the core metrics endpoint becomes unreachable.

Default severity:

    Critical

**Recovered** controls the severity used when the core telemetry connection becomes reachable again.

Default severity:

    Info

If the dashboard starts and the core telemetry endpoint is already unreachable, an initial unreachable event can be generated.

A failure of optional SSH telemetry does not by itself cause a core reachability alert.

#### Error Counter Alerts

Advanced SSH telemetry provides several cumulative XGS-PON error counters. These alerts are based on **new counter increases**, not on the lifetime value already stored by the ONT.

Each counter rule can contain:

**Minimum delta** — the amount the counter must increase before an alert is generated.

**Cooldown** — the minimum number of seconds after an alert before another alert of the same type may be generated.

**Severity** — whether the generated event is classified as Info, Warning, or Critical.

Counter increases can accumulate across multiple collection cycles until Minimum Delta is reached.

For example, with:

    Minimum delta: 10

three successive increases of `+3`, `+4`, and `+3` accumulate to `+10` and can generate an alert.

If a counter decreases, the dashboard assumes that the ONT rebooted or the counter was reset. Any pending accumulated increase for that counter is discarded rather than treating the reset as an error event.

A cooldown does not mean counter monitoring stops. Increases can continue to be observed while the cooldown is active, and a pending alert can be emitted after the cooldown expires once its configured conditions are satisfied.

The default counter rules are:

| Counter | Minimum Delta | Cooldown | Severity |
| --- | ---: | ---: | --- |
| BIP errors | 10 | 300 seconds | Warning |
| Corrected FEC codewords | 100 | 300 seconds | Warning |
| Uncorrected FEC codewords | 1 | 0 seconds | Critical |
| Corrected PSBd HEC errors | 10 | 300 seconds | Warning |
| Uncorrected PSBd HEC errors | 1 | 0 seconds | Critical |
| Corrected FS HEC errors | 10 | 300 seconds | Warning |
| Uncorrected FS HEC errors | 1 | 0 seconds | Critical |
| PLOAM MIC errors | 1 | 0 seconds | Critical |

A cooldown of `0` means there is no cooldown period.

The higher default thresholds and cooldowns on corrected-error counters help avoid excessive notifications from small bursts of errors that the link successfully corrected.

Uncorrected errors and PLOAM MIC errors default to a Minimum Delta of `1`, Critical severity, and no cooldown because a newly observed uncorrected error is generally more significant than a corrected error.

#### Alert Recovery Events

Where recovery detection is supported, the dashboard records a separate event when an active problem returns to normal.

Examples include:

- RX or TX optical quality returning to normal
- Temperature returning to normal
- PLOAM returning to the operational state
- Core telemetry becoming reachable again

Active ONT alarm decreases and clearing are also recorded as separate alert events.

Recovery events default to **Info** where a separate recovery severity is available.

#### Alert Settings and Notifications

Alert generation and notification delivery are separate operations.

**Alert Settings** determine whether an event is generated and the severity assigned to it.

**Notification Settings** determine whether generated events are sent to an external notification provider.

This means alerts continue to be evaluated and stored in the dashboard database even when Discord notifications are disabled.

Enabling Discord does not change the alert thresholds. It simply allows generated alert events to be delivered to the configured Discord webhook.

### Recent Alerts

Generated alerts are stored in the dashboard SQLite database and displayed in the **Recent Alerts** section.

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

## Discord Notifications

V3 supports optional Discord webhook notifications.

Discord notifications are generated server-side, so the dashboard does not need to remain open in a browser.

To enable Discord notifications:

1. Create a webhook for the desired Discord channel.
2. Open **Notification Settings** in the dashboard.
3. Enter the Discord webhook URL.
4. Enable Discord notifications.
5. Save the settings.

Alert notifications include the alert severity and message, along with the affected metric when applicable.

Discord is currently the only implemented notification provider.

Notification delivery is intentionally isolated from telemetry collection and alert storage. A failed Discord request does not stop telemetry collection or prevent the alert event from being stored.

### Discord Webhook Security

A Discord webhook URL should be treated as a secret.

Anyone with the webhook URL may be able to post messages to the associated Discord channel. Do not publish webhook URLs in screenshots, logs, Git repositories, support posts, or other public locations.

If a webhook URL is accidentally exposed, rotate or delete the webhook in Discord and create a new one.

## Requirements

An ONT running compatible 8311 community firmware with the metrics endpoint available at:

    /cgi-bin/luci/8311/metrics

The default endpoint is:

    https://192.168.11.1/cgi-bin/luci/8311/metrics

The Docker host must be able to reach the management IP of the ONT.

For advanced monitoring, SSH access to the ONT is also required.

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
      -e RETENTION_DAYS="30" \
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
      -e RETENTION_DAYS="30" \
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

Alert and notification configuration is stored in the dashboard's persistent SQLite database. Treat the persistent `/data` directory as sensitive if notification credentials such as a Discord webhook URL have been configured.

Do not expose this dashboard or the ONT management interface directly to the public Internet.

## Configuration

### Core telemetry

#### ONT_URL

Default:

    https://192.168.11.1/cgi-bin/luci/8311/metrics

URL of the 8311 metrics endpoint.

#### POLL_SECONDS

Default:

    10

Number of seconds between core ONT metric requests.

#### RETENTION_DAYS

Default:

    30

Number of days of historical telemetry samples to retain.

#### REQUEST_TIMEOUT

Default:

    5

Timeout in seconds when requesting the JSON metrics endpoint.

#### DATA_DIR

Default:

    /data

Directory used for persistent dashboard data.

### Advanced SSH telemetry

#### SSH_ENABLED

Default:

    false

Enables or disables advanced SSH telemetry.

#### SSH_HOST

Default:

    192.168.11.1

SSH host or management IP of the ONT.

#### SSH_PORT

Default:

    22

SSH port.

#### SSH_USER

Default:

    root

SSH username.

#### SSH_PASSWORD

Default:

    empty

Password used for SSH authentication.

The password is not stored in the dashboard SQLite database and is not returned by the dashboard APIs.

#### SSH_POLL_SECONDS

Default:

    30

Number of seconds between advanced SSH collection cycles.

#### SSH_TIMEOUT

Default:

    10

SSH connection timeout in seconds.

#### SSH_COMMAND_TIMEOUT

Default:

    30

Maximum time allowed for advanced telemetry commands.

## Persistent Data

Historical samples, alert configuration, notification configuration, and alert events are stored in an SQLite database at:

    /data/metrics.db

The `/data` directory should be mapped to persistent storage so history and configuration survive container upgrades and recreation.

For Unraid, the recommended mapping is:

    /mnt/user/appdata/x-onu-dashboard -> /data

V3 continues to use the existing core `samples` and `advanced_samples` telemetry tables and automatically adds the database structures required for alert history and configuration.

Existing telemetry history is preserved during upgrade.

## Upgrading Existing Installations

Existing installations can continue using the same persistent `/data` directory.

On startup, V3 creates the additional database structures required for alert events, alert configuration, and notification configuration if they do not already exist.

Existing core and advanced telemetry history is preserved.

After upgrading, review **Alert Settings** before enabling external notifications so the configured thresholds and severities are appropriate for your ONT and environment.

## Upgrading to the Non-Root Runtime

The container runs as the unprivileged Unraid user `nobody:users` (UID 99 / GID 100) instead of root.

Fresh Unraid installations require no additional permission changes.

Existing installations created by earlier versions may have `/data/metrics.db` owned by `root:root`. Before starting the updated container, run this one-time command on the Unraid host if using the default appdata path:

    chown -R 99:100 /mnt/user/appdata/x-onu-dashboard

This preserves the existing SQLite database and historical data while allowing the non-root container to continue writing new samples, alerts, and configuration.

## Dashboard

The dashboard displays:

- Overall ONT status
- PLOAM state
- PON health
- RX and TX optical levels
- TX bias and module voltage
- Optical and CPU temperatures
- ONT uptime
- Memory and load
- Live download and upload rate
- PON error and FEC counters
- Historical optical charts
- Historical temperature charts
- Historical traffic charts
- Optical module information
- Recent alert history
- Configurable alert settings
- Discord notification settings

Advanced sections automatically show a disabled or unavailable state when SSH telemetry is not active.

## PLOAM State

A PLOAM state of 51 represents O5.1 Associated and is the default operational PLOAM state used by the alert system.

The operational state can be configured from **Alert Settings**.

## Optical Health

The dashboard displays optical quality classifications for RX and TX signal levels.

Overall PON health is evaluated separately from the cosmetic signal-quality label so that a valid operating level does not automatically create a warning merely because it falls outside a preferred signal-quality band.

Alert thresholds are configurable independently through **Alert Settings**.

## Unraid

X-ONU Dashboard is designed to run as a Docker container on Unraid.

Recommended configuration:

    Container WebUI Port: 8080
    Default Host Port:    8766
    Container Data Path:  /data
    Default Appdata Path: /mnt/user/appdata/x-onu-dashboard

Advanced SSH telemetry is optional and can be enabled from the container settings.

Alert configuration and Discord notification configuration are managed from within the dashboard.

## Building Locally

Clone the repository and build the image with:

    docker build -t x-onu-dashboard .

Then run it with:

    docker run -d \
      --name x-onu-dashboard \
      --restart unless-stopped \
      -p 8766:8080 \
      -v ./data:/data \
      x-onu-dashboard

## Source

Project repository:

    https://github.com/JPetovello/x-onu-sfpp-dashboard

Issues and bug reports:

    https://github.com/JPetovello/x-onu-sfpp-dashboard/issues

## Development Note

This project was developed with substantial assistance from AI-based coding tools. Project direction, design decisions, hardware testing, validation, deployment, and ongoing maintenance are performed by the project maintainer.

## License

X-ONU Dashboard is licensed under the GNU Affero General Public License version 3 or later (AGPL-3.0-or-later).

Copyright (c) 2026 Jeff Petovello
