# X-ONU Dashboard

A lightweight monitoring dashboard for the EXEN X-ONU-SFPP and compatible ONTs running 8311 community firmware.

The dashboard provides live and historical XGS-PON telemetry using the 8311 JSON metrics endpoint, with optional SSH-based advanced monitoring.

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

Number of days of historical samples to retain.

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

Historical samples are stored in an SQLite database at:

    /data/metrics.db

The /data directory should be mapped to persistent storage so historical data survives container upgrades and recreation.

For Unraid, the recommended mapping is:

    /mnt/user/appdata/x-onu-dashboard -> /data

V2 uses the existing core `samples` table and adds an `advanced_samples` table for SSH telemetry.

Existing V1 history is preserved during upgrade.

## Upgrading to the Non-Root Runtime

The container now runs as the unprivileged Unraid user `nobody:users` (UID 99 / GID 100) instead of root.

Fresh Unraid installations require no additional permission changes.

Existing installations created by earlier versions may have `/data/metrics.db` owned by `root:root`. Before starting the updated container, run this one-time command on the Unraid host if using the default appdata path:

    chown -R 99:100 /mnt/user/appdata/x-onu-dashboard

This preserves the existing SQLite database and historical data while allowing the non-root container to continue writing new samples.

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

Advanced sections automatically show a disabled or unavailable state when SSH telemetry is not active.

## PLOAM State

A PLOAM state of 51 represents O5.1 Associated and indicates that the ONT has reached its normal operational state.

## Optical Health

The dashboard displays optical quality classifications for RX and TX signal levels.

Overall PON health is evaluated separately from the cosmetic signal-quality label so that a valid operating level does not automatically create a warning merely because it falls outside a preferred signal-quality band.

## Unraid

X-ONU Dashboard is designed to run as a Docker container on Unraid.

Recommended configuration:

    Container WebUI Port: 8080
    Default Host Port:    8766
    Container Data Path:  /data
    Default Appdata Path: /mnt/user/appdata/x-onu-dashboard

Advanced SSH telemetry is optional and can be enabled from the container settings.

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
