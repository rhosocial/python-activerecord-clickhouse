# Transaction Isolation Levels

## Overview

ClickHouse supports multiple transaction isolation levels, and different isolation levels determine the visibility between concurrent transactions.

## Isolation Level Comparison

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read |
|-----------------|------------|---------------------|--------------|
| READ UNCOMMITTED | Possible | Possible | Possible |
| READ COMMITTED | Impossible | Possible | Possible |
| REPEATABLE READ (Default) | Impossible | Impossible | Possible |
| SERIALIZABLE | Impossible | Impossible | Impossible |

## Setting Isolation Level

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

# Set isolation level
with backend.get_connection().cursor() as cursor:
    cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
    cursor.execute("START TRANSACTION")
    # Perform transaction operations
    cursor.execute("COMMIT")

backend.disconnect()
```

## Isolation Level Details

### READ COMMITTED

Each read fetches only committed data:

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

Suitable for most application scenarios, balancing concurrency and data consistency.

### REPEATABLE READ (Default)

Multiple reads of the same data within a transaction return consistent results:

```sql
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

ClickHouse's default isolation level, implemented using MVCC mechanism.

### SERIALIZABLE

The highest isolation level, enforces sequential transaction execution:

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

Suitable for scenarios requiring extreme data consistency, but with poorer concurrency performance.

💡 *AI Prompt:* "What are dirty reads, non-repeatable reads, and phantom reads?"
