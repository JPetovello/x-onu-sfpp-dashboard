# Upgrading Existing Installations

Existing installations can continue using the same persistent `/data` directory.

On startup, the dashboard creates the additional database structures required for alert events, alert configuration, notification configuration, and retention configuration if they do not already exist.

Existing core and advanced telemetry history is preserved. Existing installations also preserve their effective telemetry retention period when the retention configuration is created for the first time.

After upgrading, review **Alert Settings** before enabling external notifications so the configured thresholds and severities are appropriate for your ONT and environment.

## Phase 2 Upgrade and Rollback

Before applying a Phase 2 image update, create and verify a consistent SQLite backup of the existing persistent `/data/metrics.db`. Preserve the original container configuration and original image reference.

Phase 2 introduces alert configuration schema version 4 and independent thermal alerts. Existing telemetry and alert-history records are intended to remain intact. Restoring an older image after saving version 4 settings may require restoring a compatible pre-upgrade database backup. Restoring a database backup can discard samples and events collected after that backup was created.

The existing release process is:

1. Review and commit the approved source changes.
2. Merge the approved release into `main`.
3. Push an approved `v*` release tag.
4. Allow GitHub Actions to publish the versioned image and `latest` to GHCR.
5. Confirm successful publishing before selecting **Update All** in Unraid.

A push to `main` alone does not guarantee that the `latest` tag changes. Production is updated only when the operator chooses to apply the new image in Unraid.

Dashboard authentication requires separately configuring `DASHBOARD_AUTH_USERNAME` and `DASHBOARD_AUTH_PASSWORD` in the Unraid container settings. A Docker image update alone does not add these variables.

Optional Docker runtime restrictions such as a read-only root filesystem, dropped Linux capabilities, and `no-new-privileges` are also container settings, not properties automatically applied by an image update. A read-only root filesystem must still allow writable persistent `/data` and suitable temporary storage. Test these settings before applying them to an existing installation.

## LAN Authentication

HTTP Basic authentication is supported on the local network, but passwords are transmitted without transport encryption when the dashboard is accessed using ordinary HTTP. Use a strong, unique password, restrict network access, and use HTTPS wherever credential confidentiality is required.

Do not expose the dashboard directly to the public Internet.

## v3.9.0 — Remembered Browser Authentication

The v3.9.0 image adds optional HTTPS browser authentication. Existing
installations remain in HTTP Basic mode unless an administrator explicitly
sets `DASHBOARD_AUTH_MODE=browser`; a Docker image update alone does not
activate the new login experience.

Before enabling browser authentication:

1. Preserve the original container configuration and original Docker image.
2. Take and verify a consistent SQLite backup of `/data/metrics.db` using
   a separately approved procedure, without changing the normal Appdata
   Backup plugin settings.
3. Confirm that the intended hostname is served by a working, trusted HTTPS
   reverse proxy.
4. Preserve the existing `DASHBOARD_AUTH_USERNAME` and
   `DASHBOARD_AUTH_PASSWORD` values.
5. Set `DASHBOARD_AUTH_MODE=browser` and set `DASHBOARD_PUBLIC_ORIGIN`
   to the exact browser-facing HTTPS origin.
6. Recreate the container through its normal manager. Confirm the sign-in
   page, remembered sessions, Sign out, and telemetry pages work.

On Unraid, the two additional environment variables may need to be added
manually when they are not present in the installed template.

Browser authentication creates a `browser_sessions` table inside the same
persistent SQLite database. Telemetry tables and data are not replaced.

**Rollback:** Select the original image and restore Basic mode (remove
`DASHBOARD_AUTH_MODE` or set it to `basic`). Retain the prior username,
password, network, port binding and persistent `/data` path. Older images
ignore the new browser-session table. Avoid restoring an older database
unless a compatibility issue requires it: doing so loses telemetry written
after the backup.

`DASHBOARD_TRUSTED_PROXY_IPS` is optional. When unset, visitors through one
reverse proxy share a rate-limit identity.

## Upgrading to the Non-Root Runtime

The container runs as the unprivileged Unraid user `nobody:users` (UID 99 / GID 100) instead of root.

Fresh Unraid installations require no additional permission changes.

Existing installations created by earlier versions may have `/data/metrics.db` owned by `root:root`. Before starting the updated container, run this one-time command on the Unraid host if using the default appdata path:

    chown -R 99:100 /mnt/user/appdata/x-onu-dashboard

This preserves the existing SQLite database and historical data while allowing the non-root container to continue writing new samples, alerts, and configuration.
