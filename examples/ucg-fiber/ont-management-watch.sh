#!/bin/sh

###############################################################################
# WARNING — USE AT YOUR OWN RISK
#
# This script modifies a network interface on a UniFi gateway. A mistake in the
# interface name, IP address, subnet, or surrounding network configuration can
# disrupt WAN connectivity, ONT access, PPPoE, or other network services.
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

# Physical interface containing the ONT/SFP+ module.
ONT_INTERFACE="eth6"

# Management address to keep on the gateway side of the ONT management subnet.
# Example setup:
#   ONT:     192.168.11.1/24
#   Gateway: 192.168.11.2/24
MANAGEMENT_CIDR="192.168.11.2/24"

LOG_TAG="ont-management"

log() {
    logger -t "$LOG_TAG" -- "$*"
}

ensure_management_address() {
    if ! ip link show dev "$ONT_INTERFACE" >/dev/null 2>&1; then
        log "Interface $ONT_INTERFACE does not currently exist; cannot verify $MANAGEMENT_CIDR"
        return 1
    fi

    if ip -4 -o addr show dev "$ONT_INTERFACE" \
        | awk '{print $4}' \
        | grep -Fqx "$MANAGEMENT_CIDR"; then
        return 0
    fi

    log "Management address missing from $ONT_INTERFACE; restoring $MANAGEMENT_CIDR"

    if ! ip addr replace "$MANAGEMENT_CIDR" dev "$ONT_INTERFACE"; then
        log "ERROR: failed to restore $MANAGEMENT_CIDR on $ONT_INTERFACE"
        return 1
    fi

    return 0
}

# Ensure the address exists when the watcher starts.
ensure_management_address || true

# Watch address changes on the physical ONT interface. UniFi provisioning can
# remove a manually-added management address. Whenever the kernel reports an
# address change, re-check the interface and restore only if the configured
# address is actually missing.
#
# If ip monitor exits unexpectedly, restart it after a short delay.
while :; do
    ip monitor address dev "$ONT_INTERFACE" 2>/dev/null \
        | while IFS= read -r _event; do
            ensure_management_address || true
        done

    log "Address monitor for $ONT_INTERFACE exited; restarting"
    sleep 1
    ensure_management_address || true
done
