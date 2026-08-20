# 自动重试与死锁处理

## 概述

ClickHouse 死锁是两个或多个事务相互等待对方释放锁导致的僵局。后端提供了自动重试机制来处理临时性错误。

## 死锁处理策略

### 1. 使用事务重试装饰器

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
    # 转账逻辑
    pass
```

### 2. 捕获死锁错误

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
        print("发生死锁，将重试")
        # 重试逻辑
    else:
        raise
finally:
    backend.disconnect()
```

## 避免死锁的建议

1. **固定顺序访问资源**：始终以相同顺序访问表和行
2. **尽量使用索引**：减少锁定的行数
3. **减小事务大小**：减少锁定时间
4. **使用较低的隔离级别**：在必要时使用 READ COMMITTED

💡 *AI 提示词：* "什么是数据库死锁？如何避免死锁？"
