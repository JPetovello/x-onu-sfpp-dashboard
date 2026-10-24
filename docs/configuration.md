# Configuration Reference

## Core telemetry

### ONT_URL

Default:

    https://192.168.11.1/cgi-bin/luci/8311/metrics

URL of the 8311 metrics endpoint.

### ONT_TLS_VERIFY

Default:

    false

Controls TLS certificate verification for the core ONT metrics request.

Set to `true` to require normal certificate-chain and hostname or IP
verification using the container's trusted CA certificates.

The default remains `false` for compatibility with ONTs that use
self-signed or locally issued certificates.

### ONT_TLS_CA_BUNDLE

Default: unset.

Optional path to a PEM CA bundle used to verify the ONT certificate.

Setting this variable enables verification using that CA bundle.
`ONT_TLS_VERIFY` may be left unset or set to `true`.

Configuring a CA bundle together with `ONT_TLS_VERIFY=false` is rejected
as contradictory.

A trusted CA does not disable hostname or IP identity checking. The ONT
certificate must also be valid for the hostname or IP address used in
`ONT_URL`.

### POLL_SECONDS

Default:

    10

Number of seconds between core ONT metric requests.

### RETENTION_DAYS

Legacy compatibility setting used when upgrading an existing installation that does not yet have a saved retention configuration.

The existing value is used to preserve the installation's effective telemetry retention period during migration.

For new installations, telemetry retention is configured from the dashboard and defaults to **90 days**. After a retention configuration has been saved in the dashboard database, use the **Data Retention** panel rather than this environment variable to manage retention.

### REQUEST_TIMEOUT

Default:

    5

Timeout in seconds when requesting the JSON metrics endpoint.

### DATA_DIR

Default:

    /data

Directory used for persistent dashboard data.

## Dashboard authentication

### DASHBOARD_AUTH_USERNAME and DASHBOARD_AUTH_PASSWORD

Default: both unset (dashboard authentication disabled).

Configure both to enable authentication. Partial configuration is rejected.
Docker or Unraid administrators may be able to inspect environment variables,
so use a strong, private password.

### DASHBOARD_AUTH_MODE

Default: `basic`.

Accepted values: `basic`, `browser`.

`basic` preserves the existing HTTP Basic authentication behaviour.
`browser` enables browser sessions and requires both credentials and an HTTPS
`DASHBOARD_PUBLIC_ORIGIN`.

### DASHBOARD_PUBLIC_ORIGIN

Default: unset.

Required for browser mode. Example:

```text
DASHBOARD_PUBLIC_ORIGIN=https://dashboard.example.com
```

Must match the exact public HTTPS origin, including any nonstandard port.
Paths, query strings, fragments and embedded credentials are invalid. A
trusted HTTPS reverse proxy must serve this browser-facing endpoint.

### DASHBOARD_TRUSTED_PROXY_IPS

Default: unset.

Optional comma-separated list of **exact** direct reverse-proxy IP addresses.
CIDR ranges are not supported. A forwarded client IP is considered only when
the direct peer matches an explicitly trusted proxy address and its
`X-Forwarded-For` header contains exactly one valid IP address. Ambiguous or
invalid values fall back to the direct peer's IP.

When unset, the reverse proxy is the rate-limiting client. Avoid hardcoding
transient Docker-assigned IPs. Trust only proxies that sanitize client-supplied
forwarding headers.

### Browser sessions

With Remember This Browser enabled, durations are 1, 3, 7, 14 or 30 days;
the default selection is 7 days. Without it, the cookie has no persistent
Max-Age and the server lifetime is 12 hours.

Bearer-token hashes, never raw bearer tokens, are stored in `/data/metrics.db`.
Sessions can be revoked using Trusted Browsers; the server retains at most
32 session records.

Browser-mode cookies use `__Host-xonu_session`, Secure, HttpOnly,
SameSite=Lax, and Path=/. This mode is designed for HTTPS only.

Five failed logins within five minutes trigger a temporary login lockout for
the apparent client address. Existing valid sessions continue to work.

## Advanced SSH telemetry

### SSH_ENABLED

Default:

    false

Enables or disables advanced SSH telemetry.

### SSH_HOST

Default:

    192.168.11.1

SSH host or management IP of the ONT.

### SSH_PORT

Default:

    22

SSH port.

### SSH_USER

Default:

    root

SSH username.

### SSH_PASSWORD

Default:

    empty

Password used for SSH authentication.

The password is not stored in the dashboard SQLite database and is not returned by the dashboard APIs.

### SSH Host Key Verification

SSH host keys use trust on first use (TOFU).

After the first successful SSH authentication, the dashboard stores the ONT host key in:

    /data/ssh_known_hosts

Future SSH connections require the ONT to present the same host key. If the host key changes, advanced SSH telemetry rejects the connection instead of automatically trusting the new key.

Because the initial connection uses TOFU, the first host key is not independently authenticated. The persistent `/data` directory must be preserved across container updates to retain host key verification.

### SSH_POLL_SECONDS

Default:

    30

Number of seconds between advanced SSH collection cycles.

### SSH_TIMEOUT

Default:

    10

SSH connection timeout in seconds.

### SSH_COMMAND_TIMEOUT

Default:

    30

Maximum time allowed for advanced telemetry commands.
