# Connection Configuration

## Basic Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| host | str | localhost | ClickHouse server address |
| port | int | 3306 | ClickHouse port |
| database | str | - | Database name |
| username | str | root | Username |
| password | str | - | Password |
| charset | str | utf8mb4 | Character set |
| collation | str | utf8mb4_unicode_ci | Collation |
| autocommit | bool | True | Auto commit |

## Advanced Configuration Options

```python
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

config = ClickHouseConnectionConfig(
    # Basic configuration
    host='localhost',
    port=3306,
    database='myapp',
    username='myuser',
    password='mypassword',
    
    # Character set configuration
    charset='utf8mb4',
    collation='utf8mb4_unicode_ci',
    
    # Connection options
    autocommit=True,
    connect_timeout=10,
    read_timeout=30,
    write_timeout=30,
    
    # SSL configuration
    ssl_ca='/path/to/ca.pem',
    ssl_cert='/path/to/client-cert.pem',
    ssl_key='/path/to/client-key.pem',
    ssl_verify_cert=False,
)
```

## Using YAML Configuration

```yaml
# clickhouse_scenarios.yaml
scenarios:
  production:
    host: db.example.com
    port: 3306
    database: myapp_prod
    username: app_user
    password: ${CLICKHOUSE_PASSWORD}
    charset: utf8mb4
    autocommit: true
    ssl_verify_cert: true
    
  development:
    host: localhost
    port: 3306
    database: myapp_dev
    username: dev_user
    password: dev_password
    charset: utf8mb4
    autocommit: true
```

💡 *AI Prompt:* "What is the difference between character set and collation? What is the difference between utf8mb4 and utf8?"
