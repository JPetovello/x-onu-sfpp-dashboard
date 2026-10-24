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

Both scripts ship disabled, with blank network settings.

Before enabling them:

- Verify the physical ONT/SFP+ interface on your gateway.
- Verify the ONT management subnet and an unused gateway address.
- Check for conflicting routes, addresses, files and services.
- Confirm a compatible persistent boot-hook mechanism is installed.
- Have a local or console recovery method available.
- Inspect the gateway using read-only commands such as
  `ip -br link`, `ip -4 -br addr`, and `ip -4 route show default`.

Edit BOTH scripts with your verified values for
`ONT_INTERFACE` and `MANAGEMENT_CIDR`.

Only after completing these checks, change
`SETUP_CONFIRMED="NO"` to `SETUP_CONFIRMED="YES"`.

Do not assume the reference interface `eth6` or gateway address
`192.168.11.2/24` matches your installation.

If you cannot verify these settings, STOP.
Configuration validation does not guarantee network safety.

## Important: Existing installations

> [!WARNING]
> Do not copy these updated scripts over an existing installation
> without reviewing the migration first.

Earlier versions created a systemd service without the ownership
marker required by the hardened boot script.

The new boot script will refuse to replace that legacy service.
This prevents accidentally overwriting an unrelated service,
but also means an existing installation cannot be upgraded by
simply replacing its files.

Before planning a migration:

1. Record the current interface and management address.
2. Identify and inspect the installed watcher and boot script.
3. Identify the service unit and confirm its ownership.
4. Preserve backups of the existing working configuration.
5. Prepare and validate both replacement scripts offline.
6. Arrange a maintenance window and a recovery method.

Do not delete the existing service merely to bypass the
protection. A deliberate migration and rollback procedure
is required.

If the existing installation is working, leaving it unchanged
is safer than attempting an unplanned upgrade.

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

> [!CAUTION]
> **NEW INSTALLATIONS ONLY.**
>
> Do not use the following installation commands to
> upgrade an existing installation.
>
> Before copying files, verify these destinations
> do not already exist:
>
> - /data/ont-management-watch.sh
> - /data/on_boot.d/20-ont-management.sh
> - /etc/systemd/system/ont-management-watch.service
>
> Also check whether ont-management-watch.service
> is already registered with systemd.
>
> If any file or service exists, STOP.
> Do not overwrite or delete it.
>
> Existing installations require a controlled migration
> with verified backups and a rollback procedure.


From this point onward, the commands are the same regardless of whether the
administrator's computer is running Windows, Linux, or macOS.

For a new installation, install both scripts using this
single guarded command block on the UCG Fiber.
It refuses to overwrite an existing installation.

```sh
(
set -eu

for destination in \
    /data/ont-management-watch.sh \
    /data/on_boot.d/20-ont-management.sh \
    /etc/systemd/system/ont-management-watch.service
do
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        echo "STOP: Existing file: $destination" >&2
        exit 1
    fi
done

if systemctl cat ont-management-watch.service >/dev/null 2>&1; then
    echo "STOP: Service already registered" >&2
    exit 1
fi

if [ ! -d /data/on_boot.d ]; then
    echo "STOP: Boot-hook directory missing" >&2
    exit 1
fi

# Reject unconfigured or inconsistent examples.
for script in ont-management-watch.sh 20-ont-management.sh
do
    if [ ! -f "$script" ] || [ -L "$script" ]; then
        echo "STOP: Invalid script file: $script" >&2
        exit 1
    fi

    if ! grep -Fxq 'SETUP_CONFIRMED="YES"' "$script"; then
        echo "STOP: Setup not confirmed in $script" >&2
        exit 1
    fi

    if ! grep -Eq '^ONT_INTERFACE="[A-Za-z0-9_.:-]+"$' "$script"; then
        echo "STOP: Interface not configured in $script" >&2
        exit 1
    fi

    if ! grep -Eq '^MANAGEMENT_CIDR="[0-9.]+/[0-9]+"$' "$script"; then
        echo "STOP: Management address not configured in $script" >&2
        exit 1
    fi
done

for key in ONT_INTERFACE MANAGEMENT_CIDR
do
    boot_value=$(grep "^${key}=" 20-ont-management.sh)
    watch_value=$(grep "^${key}=" ont-management-watch.sh)

    if [ "$boot_value" != "$watch_value" ]; then
        echo "STOP: Conflicting $key settings" >&2
        exit 1
    fi
done

sh -n ont-management-watch.sh
sh -n 20-ont-management.sh

cp ont-management-watch.sh /data/ont-management-watch.sh
chmod 0755 /data/ont-management-watch.sh
cp 20-ont-management.sh /data/on_boot.d/20-ont-management.sh
chmod 0755 /data/on_boot.d/20-ont-management.sh
)
```

If any safety check fails, stop and investigate.
Do not bypass the checks to force an installation.
Run the boot script once manually only after confirming the configuration:

```sh
/data/on_boot.d/20-ont-management.sh
```

## Verification

Check the management address:

```sh
ip -4 addr show dev YOUR_VERIFIED_INTERFACE
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
ping -c 3 YOUR_ONT_MANAGEMENT_IP
```

## Recovery / removal

> [!CAUTION]
> These commands change gateway configuration. Confirm that the
> service and files belong to this example before removing them.
> Never remove an address unless you have independently confirmed
> that it is the address installed by these helpers.

If SSH access is lost, use your established local or console
recovery method. Do not reboot blindly or remove unrelated
network configuration.

All uppercase network values below are placeholders and MUST
be replaced with your own verified values.


The following removal procedure applies only to the hardened
helper installed from these examples. Legacy installations
require a separately reviewed removal procedure.

Verify ownership before stopping or removing anything:

```sh
(
set -eu

BOOT=/data/on_boot.d/20-ont-management.sh
WATCH=/data/ont-management-watch.sh
UNIT=/etc/systemd/system/ont-management-watch.service

for file in "$BOOT" "$WATCH" "$UNIT"; do
    test -f "$file" && test ! -L "$file" || {
        echo "STOP: Missing or unsafe file: $file" >&2
        exit 1
    }
done

grep -Fxq \
    "# Managed by X-ONU-SFPP UCG Fiber example" "$UNIT"

grep -Fxq \
    "ExecStart=/data/ont-management-watch.sh" "$UNIT"

grep -Fq 'WATCH_SCRIPT="/data/ont-management-watch.sh"' "$BOOT"

FRAGMENT=$(systemctl show ont-management-watch.service \
    -p FragmentPath --value)
test "$FRAGMENT" = "$UNIT"

echo "PASS: Hardened helper ownership verified"

systemctl disable --now ont-management-watch.service
rm -f "$UNIT"
systemctl daemon-reload
rm -f "$BOOT" "$WATCH"

echo "PASS: Hardened helper removed"
)
```

These commands do not remove the gateway management IP.
Confirm ONT management connectivity and network requirements
before considering a separate address removal.
If you also want to remove the management address immediately, substitute your
actual configured values:

```sh
ip addr del YOUR_VERIFIED_GATEWAY_IP_PREFIX dev YOUR_VERIFIED_INTERFACE
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
