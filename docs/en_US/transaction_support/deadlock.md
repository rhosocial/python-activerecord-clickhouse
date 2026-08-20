# Auto-Retry and Deadlock Handling

## Overview

A ClickHouse deadlock is a situation where two or more transactions are waiting for each other to release locks. The backend provides an automatic retry mechanism to handle transient errors.

## Deadlock Handling Strategies

### 1. Using Transaction Retry Decorator

```python
from functools import wraps
import time


def retry_on_deadlock(max_retries=3, delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if "Deadlock" in str(e):
                        time.sleep(delay * (attempt + 1))
                        continue
                    raise
            raise last_exception
        return wrapper
    return decorator


@retry_on_deadlock(max_retries=3)
def transfer_money(from_account, to_account, amount):
    # Transfer logic
    pass
```

### 2. Catching Deadlock Errors

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend


backend = ClickHouseBackend(
    host='localhost',
    database='myapp',
    username='user',
    password='password',
)
backend.connect()

try:
    with backend.get_connection().cursor() as cursor:
        cursor.execute("START TRANSACTION")
        cursor.execute("UPDATE accounts SET balance = balance - 100 WHERE id = 1")
        cursor.execute("UPDATE accounts SET balance = balance + 100 WHERE id = 2")
        cursor.execute("COMMIT")
except Exception as e:
    if "Deadlock" in str(e):
        print("Deadlock occurred, will retry")
        # Retry logic
    else:
        raise
finally:
    backend.disconnect()
```

## Recommendations for Avoiding Deadlocks

1. **Access resources in a fixed order**: Always access tables and rows in the same order
2. **Use indexes whenever possible**: Reduce the number of rows locked
3. **Keep transactions small**: Reduce lock duration
4. **Use lower isolation levels when needed**: Use READ COMMITTED when appropriate

💡 *AI Prompt:* "What is a database deadlock? How can deadlocks be avoided?"
