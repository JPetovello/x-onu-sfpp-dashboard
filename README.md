# X-ONU Dashboard

A lightweight monitoring dashboard for the EXEN X-ONU-SFPP and compatible ONTs running 8311 community firmware.

The dashboard polls the 8311 JSON metrics endpoint and provides live and historical monitoring of:

- RX optical power
- TX optical power
- TX bias current
- Module voltage
- Optical temperature
- CPU temperatures
- PLOAM state
- ONT connectivity
- Historical min/average/max statistics

## Requirements

An ONT running compatible 8311 community firmware with the metrics endpoint available at:

    /cgi-bin/luci/8311/metrics

The default endpoint is:

    https://192.168.11.1/cgi-bin/luci/8311/metrics

The Docker host must be able to reach the management IP of the ONT.

## Docker Image

The published Docker image is:

    ghcr.io/jpetovello/x-onu-sfpp-dashboard:latest

## Docker Installation

Example Docker command:

    docker run -d \
      --name x-onu-dashboard \
      --restart unless-stopped \
      -p 8766:8080 \
      -e ONT_URL="https://192.168.11.1/cgi-bin/luci/8311/metrics" \
      -e POLL_SECONDS="10" \
      -e RETENTION_DAYS="30" \
      -e REQUEST_TIMEOUT="5" \
      -e DATA_DIR="/data" \
      -v ./data:/data \
      ghcr.io/jpetovello/x-onu-sfpp-dashboard:latest

The dashboard will then be available on port 8766 of the Docker host.

## Configuration

The following environment variables are supported:

### ONT_URL

Default:

    https://192.168.11.1/cgi-bin/luci/8311/metrics

URL of the 8311 metrics endpoint.

### POLL_SECONDS

Default:

    10

Number of seconds between ONT metric requests.

### RETENTION_DAYS

Default:

    30

Number of days of historical samples to retain in the SQLite database.

### REQUEST_TIMEOUT

Default:

    5

Timeout in seconds when requesting metrics from the ONT.

### DATA_DIR

Default:

    /data

Directory used for persistent dashboard data.

## Persistent Data

Historical samples are stored in an SQLite database at:

    /data/metrics.db

The /data directory should be mapped to persistent storage so historical data survives container upgrades and recreation.

For Unraid, the recommended mapping is:

    /mnt/user/appdata/x-onu-dashboard -> /data

## Dashboard

The dashboard displays current values for:

- RX optical power
- TX optical power
- TX bias current
- Module voltage
- Optical temperature
- CPU 1 temperature
- CPU 2 temperature
- PLOAM state
- ONT reachability

Historical charts are available for:

- 1 hour
- 6 hours
- 24 hours
- 7 days
- 30 days

The dashboard also provides minimum, average, and maximum statistics for optical signal levels and temperatures.

## PLOAM State

A PLOAM state of 51 represents O5.1 Associated, indicating that the ONT has reached its normal operational state.

## Unraid

X-ONU Dashboard is designed to run as a Docker container on Unraid.

The intended Unraid configuration is:

    Container WebUI Port: 8080
    Default Host Port:    8766
    Container Data Path:  /data
    Default Appdata Path: /mnt/user/appdata/x-onu-dashboard

An Unraid Community Applications template will be included in this repository.

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

## License

X-ONU Dashboard is licensed under the GNU Affero General Public License
version 3 or later (AGPL-3.0-or-later).

Copyright (c) 2026 Jeff Petovello
