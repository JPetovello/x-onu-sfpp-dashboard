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
SETUP_CONFIRMED="NO"
ONT_INTERFACE=""

# Management address to keep on the gateway side of the ONT management subnet.
# Example setup:
#   ONT:     192.168.11.1/24
#   Gateway: 192.168.11.2/24
MANAGEMENT_CIDR=""

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
