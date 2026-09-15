# UCG Fiber ONT Management Persistence Example

> [!CAUTION]
> # ⚠️ USE AT YOUR OWN RISK — READ THIS FIRST
>
> These scripts modify a **WAN-side network interface on your UniFi gateway**.
> Incorrect configuration can interrupt your Internet connection, PPPoE session,
> ONT management access, or other network services.
>
> These files are **unofficial community examples**. They are **not supported or
> endorsed by Ubiquiti, EXEN, the 8311 community, or the X-ONU-SFPP Dashboard
> project**. UniFi OS behavior can change between releases.
>
> **Do not copy and run these scripts blindly.** Verify the interface name,
> management subnet, ONT address, and gateway-side management address for your
> own installation first. Keep local/console recovery access available whenever
> possible.
>
> **You assume all risk for using or adapting these scripts.**

## What problem do these scripts solve?

The X-ONU-SFPP Dashboard only requires that the machine running it can reach the
ONT management interface. The dashboard itself does not require these scripts.

These scripts also do **not** require X-ONU-SFPP Dashboard. They may be used as
a standalone UCG Fiber helper to preserve direct access to an ONT web interface,
SSH service, or other management tools. No Dashboard container or Docker
installation is required for that use case.

On some UniFi gateway configurations, a management IP manually added to the
physical WAN/SFP+ interface can disappear when UniFi reapplies interface
configuration. This can happen around provisioning or other network
reconfiguration events.

The example solution consists of two parts:

- `20-ont-management.sh` — a boot hook that restores the configured management
  address and recreates/restarts the watcher service.
- `ont-management-watch.sh` — an event-driven watcher using `ip monitor` that
  checks the address whenever the kernel reports an address change and restores
  it only if it is missing.

The watcher does **not** continuously poll the ONT, intentionally bounce the WAN
interface, replace the PPPoE interface, or deliberately modify the default
route.

## Tested reference setup

The original setup this example was derived from used:

- Gateway: UniFi Cloud Gateway Fiber (UCG Fiber)
- ONT/SFP+ physical interface: `eth6`
- ONT management IP: `192.168.11.1/24`
- Gateway-side management IP: `192.168.11.2/24`
- WAN authentication: PPPoE

Those values are **examples, not universal defaults**.

## Prerequisites

This example assumes:

1. You have shell/root access to the UniFi gateway.
2. You know which physical interface contains the ONT/SFP+ module.
3. You know the ONT management subnet.
4. You have selected a free gateway-side IP in that subnet.
5. A persistent boot-script mechanism such as `udm-boot` is already available.
6. The gateway's `/data` directory persists across reboots.

## Configure before installation

Open **both scripts** and verify these values match each other and your network:

```sh
ONT_INTERFACE="eth6"
MANAGEMENT_CIDR="192.168.11.2/24"
```

For an ONT at `192.168.11.1/24`, `192.168.11.2/24` is one possible gateway-side
address if it is otherwise unused.

Do not assume your UCG Fiber uses `eth6`. Verify it on your own device.

## Installation

> [!WARNING]
> The commands below ultimately change the gateway. Review the scripts first.
> Have a recovery path available before proceeding.

The `.sh` files do **not** run on Windows, macOS, or the Linux workstation used
to install them. They run on the UCG Fiber itself.

The administrator's computer is only used to copy the files to the gateway and
open an SSH session.

<details>
<summary><strong>Linux / macOS</strong></summary>

Open a terminal in the `examples/ucg-fiber/` directory.

Set the LAN address of your UCG Fiber:

```sh
UCG_IP="YOUR_UCG_FIBER_IP"
```

Create a temporary staging directory on the gateway:

```sh
ssh root@"$UCG_IP" 'mkdir -p /tmp/ucg-fiber-helper'
```

Copy the two scripts:

```sh
scp ont-management-watch.sh root@"$UCG_IP":/tmp/ucg-fiber-helper/
scp 20-ont-management.sh root@"$UCG_IP":/tmp/ucg-fiber-helper/
```

Connect to the gateway:

```sh
ssh root@"$UCG_IP"
```

Then, on the UCG Fiber:

```sh
cd /tmp/ucg-fiber-helper
```

Continue with **Gateway installation** below.

</details>

<details>
<summary><strong>Windows PowerShell</strong></summary>

Windows is used only to transfer the files and connect to the UCG Fiber. The
helper scripts still execute on the gateway.

Open PowerShell in the directory containing the two `.sh` files.

First verify that the Windows OpenSSH client is available:

```powershell
Get-Command ssh
Get-Command scp
```

If either command is missing, open **PowerShell as Administrator** and check the
OpenSSH Client capability:

```powershell
Get-WindowsCapability -Online |
    Where-Object Name -like 'OpenSSH.Client*'
```

If its state is `NotPresent`, install it:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

Return to a normal PowerShell window and set the LAN address of the UCG Fiber:

```powershell
$UcgIp = "YOUR_UCG_FIBER_IP"
```

Create a temporary staging directory on the gateway:

```powershell
ssh "root@$UcgIp" "mkdir -p /tmp/ucg-fiber-helper"
```

Copy the scripts:

```powershell
scp .\ont-management-watch.sh "root@${UcgIp}:/tmp/ucg-fiber-helper/"
scp .\20-ont-management.sh "root@${UcgIp}:/tmp/ucg-fiber-helper/"
```

Connect to the gateway:

```powershell
ssh "root@$UcgIp"
```

Then, on the UCG Fiber:

```sh
cd /tmp/ucg-fiber-helper
```

Continue with **Gateway installation** below.

#### Windows line-ending warning

These are POSIX shell scripts and must use **Unix LF line endings**.

`scp` transfers the files as-is, but some Windows editors or Git configurations
may convert shell scripts to CRLF line endings.

If you edit either script on Windows, verify that your editor is using `LF`
before copying the file to the gateway.

A script damaged by CRLF conversion may fail with an error similar to a
`/bin/sh^M` or `bad interpreter` message.

</details>

### Gateway installation

From this point onward, the commands are the same regardless of whether the
administrator's computer is running Windows, Linux, or macOS.

Copy the watcher to persistent storage:

```sh
cp ont-management-watch.sh /data/ont-management-watch.sh
chmod 0755 /data/ont-management-watch.sh
```

Copy the boot script into the persistent boot-hook directory used by `udm-boot`:

```sh
cp 20-ont-management.sh /data/on_boot.d/20-ont-management.sh
chmod 0755 /data/on_boot.d/20-ont-management.sh
```

Run the boot script once manually only after confirming the configuration:

```sh
/data/on_boot.d/20-ont-management.sh
```

## Verification

Check the management address:

```sh
ip -4 addr show dev eth6
```

Check the watcher service:

```sh
systemctl status ont-management-watch.service --no-pager
```

Check recent watcher messages:

```sh
journalctl -t ont-management --no-pager -n 50
```

Test ONT reachability using the address appropriate for your installation:

```sh
ping -c 3 192.168.11.1
```

## Recovery / removal

If you need to remove this example configuration, stop and disable the watcher,
remove the generated service unit, and remove the persistent scripts:

```sh
systemctl disable --now ont-management-watch.service 2>/dev/null || true
rm -f /etc/systemd/system/ont-management-watch.service
systemctl daemon-reload
rm -f /data/ont-management-watch.sh
rm -f /data/on_boot.d/20-ont-management.sh
```

If you also want to remove the management address immediately, substitute your
actual configured values:

```sh
ip addr del 192.168.11.2/24 dev eth6
```

Removing the management address may immediately remove access to the ONT
management interface.

## Why this lives under `examples/`

This is not a required component of X-ONU-SFPP Dashboard and is not a universal
UniFi configuration method. It is included as a reference for users who have a
similar UCG Fiber topology and discover that UniFi repeatedly removes their ONT
management address.

Users with another router, a management VLAN, a directly routable ONT subnet,
or any setup where ONT management connectivity is already persistent do not
need these scripts.
