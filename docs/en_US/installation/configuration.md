# Connection configuration

This backend uses `ClickHouseConnectionConfig` to describe connection parameters.
It is a subclass of the core `ConnectionConfig`, adding ClickHouse-specific options.

## Minimal configuration

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    host="localhost",
    port=8123,            # ClickHouse HTTP port
    database="test_db",
    username="root",
    password="password",
)
```

> ⚠️ The port is **8123** (HTTP), not 3306. `clickhouse-connect` talks to
> ClickHouse over HTTP.

## Full configuration fields

`ClickHouseConnectionConfig` inherits several mixins from the core library; the
usable fields are:

| Field | Source | Default | Description |
|-------|--------|---------|-------------|
| `host` | `ConnectionConfig` | — | ClickHouse host |
| `port` | `ConnectionConfig` | — | **8123** (HTTP) |
| `database` | `ConnectionConfig` | — | Database name |
| `username` | `ConnectionConfig` | — | Username |
| `password` | `ConnectionConfig` | — | Password |
| `autocommit` | ClickHouse-specific | `True` | `clickhouse-connect` autocommit mode |
| `connect_timeout` | ClickHouse-specific | `10` | Connect timeout (seconds) |
| `send_receive_timeout` | ClickHouse-specific | `30` | Send/receive timeout (seconds) |
| `compress` | ClickHouse-specific | `False` | Enable HTTP compression |
| `settings` | ClickHouse-specific | `None` | Session-level `settings` dict passed to ClickHouse (e.g. `{"mutations_sync": "1"}`) |

Inherited mixin fields (`SSLMixin`/`TimezoneMixin`/`LoggingMixin`/`VersionMixin`,
etc.) follow the core library's generic semantics. The `CharsetMixin` field
exists but ClickHouse does not use MySQL-style charset (utf-8 is the HTTP transport
default).

## Bind the configuration to a model

```python
from rhosocial.activerecord.model import ActiveRecord

class User(ActiveRecord):
    __table_name__ = "users"
    __primary_key__ = "id"
    ...

User.configure(config, ClickHouseBackend)
```

All subsequent `User` queries go through this backend.

## SSL/TLS

ClickHouse natively supports HTTPS (default 8443). This backend enables TLS via
`ssl_mode`:

| `ssl_mode` | Behavior | Use case |
|------------|----------|----------|
| `disabled` / `auto` / unset | Plain HTTP (default 8123) | Local dev, intranet |
| `require` | HTTPS encrypted, **no** cert validation | Encrypted transport, self-signed certs |
| `verify-ca` | HTTPS + validate server cert chain | Production (see limitation below) |
| `verify-full` | HTTPS + validate cert chain + hostname | Recommended for production |

Configuration example:

```python
config = ClickHouseConnectionConfig(
    host="clickhouse.example.com",
    port=8443,                 # remote HTTPS port
    database="test_db",
    username="root",
    password="password",
    ssl_mode="verify-full",     # enable HTTPS + validate cert + validate hostname
    # ssl_ca="/path/to/ca.pem", # optional: custom CA (omit when the system CA store
                                 # already contains public CAs like Let's Encrypt)
)
```

### Verified working

The following have all been tested against ClickHouse 26.7:

```bash
# HTTPS, no validation
python -m rhosocial.activerecord.backend.impl.clickhouse query "SELECT version()" \
    --host clickhouse.example.com --port 8443 --database test_db \
    --user root --password password --ssl require

# HTTPS + validate cert + hostname
python -m rhosocial.activerecord.backend.impl.clickhouse query "SELECT 1" \
    --host clickhouse.example.com --port 8443 --database test_db \
    --user root --password password --ssl verify-full

# HTTPS + validate cert (access via the cert's CN hostname)
python -m rhosocial.activerecord.backend.impl.clickhouse query "SELECT 1" \
    --host clickhouse.example.com --port 8443 --database test_db \
    --user root --password password --ssl verify-ca
```

### The verify-ca limitation

The underlying driver `clickhouse-connect` has a boolean cert validation switch
(`verify=True` validates both the CA chain **and the hostname**); it does
**not** natively support the standard `verify-ca` semantics of "validate CA but
not hostname". Therefore this backend's `verify-ca` behaves the same as
`verify-full`:

- Access via the **hostname in the certificate CN** (e.g.
  `clickhouse.example.com`) → hostname matches, validation passes.
- Access via `localhost` / IP when the cert CN is a different domain → hostname
  mismatch, validation fails.

For "encrypted but no validation at all", use `--ssl require`; for validation,
access via the certificate's hostname.

## Multi-backend isolation (SQLite in dev, ClickHouse in production)

The core library supports binding different backends per model class. Use SQLite
in development (zero-IO testing) and switch to ClickHouse in production:

```python
# dev
User.configure(sqlite_config, SQLiteBackend)
# prod
User.configure(clickhouse_config, ClickHouseBackend)
```

Probe capability differences via `dialect.supports_*()` before switching to avoid
calling unsupported features on ClickHouse.

## Configure via environment variables (testing)

Tests commonly override defaults via environment variables (see
[Test configuration](../testing/README.md)):

```bash
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=8123
export CLICKHOUSE_DATABASE=test_db
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=password
```

## Next steps

- [Quick start](../getting_started/quick_start.md)
- [Capability boundaries](../introduction/capability_boundaries.md)
