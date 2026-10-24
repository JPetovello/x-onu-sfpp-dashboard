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
