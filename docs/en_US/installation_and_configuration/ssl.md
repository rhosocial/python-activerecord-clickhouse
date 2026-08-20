# SSL/TLS Configuration

## Overview

When the ClickHouse server has a valid CA-signed certificate, clients can connect without specifying SSL parameters - SSL is enabled by default.

## Basic Usage (No Additional Configuration Required)

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

# When server certificate is signed by a trusted CA and is valid, no additional config needed
backend = ClickHouseBackend(
    host='clickhouse.example.com',
    port=3306,
    database='myapp',
    username='user',
    password='password',
)
# SSL is enabled by default
backend.connect()
```

## SSL Configuration Parameters

To customize SSL behavior, use the following parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| ssl_ca | str | - | CA certificate path |
| ssl_cert | str | - | Client certificate path |
| ssl_key | str | - | Client private key path |
| ssl_verify_cert | bool | True | Whether to verify server certificate |
| ssl_verify_identity | bool | False | Whether to verify server identity |

## Self-Signed Certificates

For self-signed certificates, additional configuration is required:

```python
config = {
    'host': 'clickhouse.example.com',
    'ssl_ca': '/path/to/self-signed-ca.pem',
    'ssl_verify_cert': False,  # Disable certificate verification
}

backend = ClickHouseBackend(**config)
```

## Verify SSL Connection

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

backend = ClickHouseBackend(
    host='clickhouse.example.com',
    port=3306,
    database='myapp',
    username='user',
    password='password',
)
backend.connect()

# Check if connection uses SSL
connection = backend.get_connection()
print(f"SSL Status: {connection.is_ssl}")
print(f"Encryption: {connection.get_character_set_info()}")

backend.disconnect()
```

💡 *AI Prompt:* "What is the difference between SSL, TLS, and SSH? Why is SSL needed for database connections?"
