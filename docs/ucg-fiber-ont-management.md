# UCG Fiber and Persistent ONT Management Access

> [!CAUTION]
> # ⚠️ HUGE WARNING: USE AT YOUR OWN RISK
>
> The optional UCG Fiber helper scripts modify a **WAN-side interface on the
> gateway**. A wrong interface name, IP address, subnet, or other configuration
> choice can break Internet connectivity, PPPoE, ONT management access, or other
> network services.
>
> They are **unofficial community examples**, provided for reference only.
> Review and adapt them for your own environment. **You are solely responsible
> for any changes made to your gateway.**

## The dashboard does not require a UCG Fiber script

X-ONU-SFPP Dashboard has one networking requirement: the Docker/container host
must be able to reach the ONT management IP.

If that connectivity is already stable, no gateway helper is needed.

## Standalone use without X-ONU-SFPP Dashboard

These helper scripts do **not** depend on X-ONU-SFPP Dashboard, Docker, or the
dashboard container.

They may be used independently by a UCG Fiber owner who simply wants persistent
access to an ONT management interface for purposes such as:

- Logging in to the ONT web interface
- Accessing the ONT over SSH
- Running diagnostic or administrative tools
- Maintaining a reliable management path to the ONT

The same warnings and configuration requirements apply. The interface name,
management subnet, and gateway-side management address must be verified for the
specific installation before using the scripts.

## Why a helper may be useful on UCG Fiber

A UCG Fiber can use the physical SFP+ interface for the optical module while the
Internet session itself operates over PPPoE. An additional local address on the
physical interface can provide access to the ONT management subnet.

In the tested reference environment, UniFi provisioning sometimes removed that
additional address. The dashboard then lost access to the ONT even though the
PPPoE Internet connection continued to exist.

The optional helper under `examples/ucg-fiber/` demonstrates one way to recover
that address automatically:

1. A persistent boot hook adds/restores the gateway-side ONT management address.
2. The boot hook recreates and starts a systemd watcher service.
3. The watcher listens for interface-address changes with `ip monitor`.
4. If the configured management address disappears, it is restored.

The reference design is intentionally narrow: it restores one configured local
address. It does not intentionally manipulate PPPoE credentials, the PPPoE
interface, the default route, or firewall policy.

## Reference values from the tested setup

| Setting | Tested value |
| --- | --- |
| Gateway | UniFi Cloud Gateway Fiber |
| Physical ONT interface | `eth6` |
| ONT management address | `192.168.11.1/24` |
| Gateway management address | `192.168.11.2/24` |
| WAN session | PPPoE |

These values are included only to explain the original topology. They must not
be assumed to match another installation.

## Files

See [`../examples/ucg-fiber/README.md`](../examples/ucg-fiber/README.md) for the
full warning, configuration, installation, verification, and removal procedure.
