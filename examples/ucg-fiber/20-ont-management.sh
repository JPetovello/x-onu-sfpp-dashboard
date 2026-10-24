#!/bin/sh

###############################################################################
# WARNING — USE AT YOUR OWN RISK
#
# This boot script modifies a WAN-side network interface and installs/restarts a
# systemd service on a UniFi gateway. Incorrect values can disrupt Internet
# access, PPPoE, ONT management access, or other network services.
#
# This is an UNOFFICIAL community example. It is not supported by Ubiquiti,
# EXEN, the 8311 community, or the X-ONU-SFPP Dashboard project.
#
# REVIEW AND ADAPT THIS SCRIPT FOR YOUR OWN ENVIRONMENT BEFORE RUNNING IT.
# YOU ARE RESPONSIBLE FOR ANY CHANGES YOU MAKE TO YOUR GATEWAY.
###############################################################################

set -u

# -----------------------------------------------------------------------------
# USER CONFIGURATION — CHANGE THESE VALUES FOR YOUR ENVIRONMENT
# -----------------------------------------------------------------------------

SETUP_CONFIRMED="NO"
ONT_INTERFACE=""
MANAGEMENT_CIDR=""

WATCH_SCRIPT="/data/ont-management-watch.sh"
SERVICE_NAME="ont-management-watch.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
LOG_TAG="ont-management"

log() {
    logger -t "$LOG_TAG" -- "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

validate_configuration() {
    if [ "$SETUP_CONFIRMED" != "YES" ]; then
        die 'Not configured. Review this script and set SETUP_CONFIRMED="YES"'
    fi

    case "$ONT_INTERFACE" in
        ""|*[!a-zA-Z0-9_.:-]*)
            die "Invalid ONT_INTERFACE"
            ;;
        lo|ppp*|docker*|tailscale*)
            die "ONT_INTERFACE must be the physical ONT/SFP+ interface"
            ;;
    esac

    printf '%s\n' "$MANAGEMENT_CIDR" | awk -F/ '
        NF != 2 { exit 1 }
        $2 !~ /^[0-9]+$/ { exit 1 }
        $2 + 0 < 1 || $2 + 0 > 32 { exit 1 }
        {
            n = split($1, octets, ".")
            if (n != 4) exit 1

            for (i = 1; i <= 4; i++) {
                if (octets[i] !~ /^[0-9]+$/) exit 1
                if (length(octets[i]) > 3) exit 1
                if (length(octets[i]) > 1 &&
                    substr(octets[i], 1, 1) == "0") exit 1
                if (octets[i] + 0 > 255) exit 1
            }

            if (octets[1] < 1 || octets[1] > 223) exit 1
        }
    ' || die "Invalid MANAGEMENT_CIDR"

    [ "$(id -u)" -eq 0 ] ||
        die "This helper must run as root"
}

validate_configuration

# The watcher is expected to be stored persistently under /data.
if [ ! -x "$WATCH_SCRIPT" ]; then
    log "ERROR: watcher not found or not executable: $WATCH_SCRIPT"
    exit 1
fi

# Never overwrite an unrelated systemd service.
SERVICE_MARKER="# Managed by X-ONU-SFPP UCG Fiber example"

if [ -L "$SERVICE_FILE" ]; then
    die "Service unit path is a symlink: $SERVICE_FILE"
fi

if [ -e "$SERVICE_FILE" ]; then
    if ! grep -Fqx "$SERVICE_MARKER" "$SERVICE_FILE"; then
        die "Existing service is not managed by this helper: $SERVICE_FILE"
    fi
elif systemctl cat "$SERVICE_NAME" >/dev/null 2>&1; then
    die "Service name is already defined elsewhere: $SERVICE_NAME"
fi

# Wait briefly for the physical interface to appear during boot.
count=0
while ! ip link show dev "$ONT_INTERFACE" >/dev/null 2>&1; do
    count=$((count + 1))
    if [ "$count" -ge 60 ]; then
        log "ERROR: interface $ONT_INTERFACE did not appear within 60 seconds"
        exit 1
    fi
    sleep 1
done

# Restore the management address immediately. This adds an address to the
# physical interface; it does not intentionally replace the PPPoE interface or
# default route. Incorrect configuration can still disrupt networking.
if ! ip -4 -o addr show dev "$ONT_INTERFACE" \
    | awk '{print $4}' \
    | grep -Fqx "$MANAGEMENT_CIDR"; then
    log "Restoring $MANAGEMENT_CIDR on $ONT_INTERFACE at boot"
    if ! ip addr replace "$MANAGEMENT_CIDR" dev "$ONT_INTERFACE"; then
        log "ERROR: Failed to restore $MANAGEMENT_CIDR on $ONT_INTERFACE"
        exit 1
    fi
fi

# /etc may be rebuilt across UniFi OS boots/updates, so recreate the unit from
# persistent /data each time this boot hook runs.
SERVICE_TMP=$(mktemp "${SERVICE_FILE}.tmp.XXXXXXXX") ||
    die "Cannot create temporary service file"

trap 'rm -f "$SERVICE_TMP"' EXIT

if ! cat > "$SERVICE_TMP" <<EOF_SERVICE
$SERVICE_MARKER
[Unit]
Description=Keep ONT management address present on WAN interface
After=network.target

[Service]
Type=simple
ExecStart=$WATCH_SCRIPT
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF_SERVICE
then
    die "Failed to write temporary service file"
fi

chmod 0644 "$SERVICE_TMP" ||
    die "Cannot set temporary service permissions"

mv -f "$SERVICE_TMP" "$SERVICE_FILE" ||
    die "Cannot install service file"

trap - EXIT

if ! systemctl daemon-reload; then
    log "ERROR: Failed to reload systemd"
    exit 1
fi

if ! systemctl enable "$SERVICE_NAME"; then
    log "ERROR: Failed to enable $SERVICE_NAME"
    exit 1
fi

if ! systemctl restart "$SERVICE_NAME"; then
    log "ERROR: Failed to start $SERVICE_NAME"
    exit 1
fi

log "ONT management persistence active: $MANAGEMENT_CIDR on $ONT_INTERFACE"
