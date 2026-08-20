# Savepoint Support

## Overview

Savepoints allow creating intermediate checkpoints within a transaction, enabling partial rollbacks.

## Using Savepoints

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig


config = ClickHouseConnectionConfig(
    host='localhost',
    database='myapp',
    username='user',
    password='password',
)

backend = ClickHouseBackend(connection_config=config)
backend.connect()

try:
    with backend.get_connection().cursor() as cursor:
        cursor.execute("START TRANSACTION")
        
        # Operation 1
        cursor.execute("INSERT INTO users (name) VALUES ('Alice')")
        
        # Create savepoint
        cursor.execute("SAVEPOINT sp1")
        
        try:
            # Operation 2 (may fail)
            cursor.execute("INSERT INTO users (name) VALUES ('Bob')")
            cursor.execute("COMMIT")
        except Exception:
            # Rollback to savepoint
            cursor.execute("ROLLBACK TO SAVEPOINT sp1")
            cursor.execute("COMMIT")
            
finally:
    backend.disconnect()
```

## Named Savepoints

```python
cursor.execute("SAVEPOINT savepoint_name")
cursor.execute("ROLLBACK TO SAVEPOINT savepoint_name")
```

💡 *AI Prompt:* "What is a database savepoint? How does it differ from a full rollback?"
