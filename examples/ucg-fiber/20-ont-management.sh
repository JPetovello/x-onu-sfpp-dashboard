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

ONT_INTERFACE="eth6"
MANAGEMENT_CIDR="192.168.11.2/24"

WATCH_SCRIPT="/data/ont-management-watch.sh"
SERVICE_NAME="ont-management-watch.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
LOG_TAG="ont-management"

log() {
    logger -t "$LOG_TAG" -- "$*"
}

# The watcher is expected to be stored persistently under /data.
if [ ! -x "$WATCH_SCRIPT" ]; then
    log "ERROR: watcher not found or not executable: $WATCH_SCRIPT"
    exit 1
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
    ip addr replace "$MANAGEMENT_CIDR" dev "$ONT_INTERFACE"
fi

# /etc may be rebuilt across UniFi OS boots/updates, so recreate the unit from
# persistent /data each time this boot hook runs.
cat > "$SERVICE_FILE" <<EOF_SERVICE
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

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"

log "ONT management persistence active: $MANAGEMENT_CIDR on $ONT_INTERFACE"
