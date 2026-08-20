# 时区处理

## 概述

ClickHouse 后端在处理日期时间类型时，保持数据库返回的原始形式，不进行额外的时区转换。

## DATETIME 与 TIMESTAMP 的区别

ClickHouse 中有两种日期时间类型：

- **DATETIME**：存储不带时区信息的日期时间，类似于「日历时间」
- **TIMESTAMP**：存储 UTC 时间戳，ClickHouse 会自动在服务器时区和 UTC 之间转换

```sql
-- 创建表时指定类型
CREATE TABLE events (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    created_at DATETIME,      -- 不带时区
    updated_at TIMESTAMP      -- 带时区，自动转换
);
```

## ClickHouse 服务器时区

ClickHouse 服务器的时区设置会影响 TIMESTAMP 类型的存储和读取：

```sql
-- 查看当前时区设置
SHOW VARIABLES LIKE 'time_zone';

-- 设置会话时区
SET time_zone = '+08:00';
```

## Python 端处理

建议在 Python 端统一使用 UTC 或本地时区处理：

```python
from datetime import datetime, timezone, timedelta


def to_utc(dt: datetime) -> datetime:
    """转换为 UTC 时间"""
    if dt.tzinfo is None:
        # 假设为本地时区
        local_tz = datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime) -> datetime:
    """转换为本地时间"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_tz = datetime.now().astimezone().tzinfo
    return dt.astimezone(local_tz)
```

## 最佳实践

1. **使用 UTC 存储**：建议在数据库中存储 UTC 时间
2. **前端转换**：在应用层或前端进行时区转换
3. **避免混用**：不要在同一系统中混用不同时区的时间

```python
from datetime import datetime, timezone


class Event(ActiveRecord):
    name: str
    created_at: datetime
    
    @property
    def created_at_utc(self) -> datetime:
        if self.created_at.tzinfo is None:
            return self.created_at.replace(tzinfo=timezone.utc)
        return self.created_at.astimezone(timezone.utc)
```

💡 *AI 提示词：* "为什么推荐使用 UTC 存储时间而不是本地时区？"
