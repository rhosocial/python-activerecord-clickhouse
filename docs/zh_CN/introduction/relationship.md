# 与核心库的关系

## 架构概述

rhosocial-activerecord 采用模块化设计，核心库（`rhosocial-activerecord`）提供与数据库无关的 ActiveRecord 实现，各数据库后端作为独立扩展包存在。

ClickHouse 后端的命名空间位于 `rhosocial.activerecord.backend.impl.clickhouse` 之下，与其他后端（如 `sqlite`、`dummy`）处于同一层级。这意味着：

- 后端不参与 ActiveRecord 层面的变化
- 后端严格遵守后端接口协议
- 后端的更新与核心库的 ActiveRecord 功能解耦

```
rhosocial.activerecord
├── backend.impl.sqlite   # SQLite 后端
├── backend.impl.dummy   # 测试用 Dummy 后端
└── backend.impl.clickhouse   # ClickHouse 后端（本包）
    ├── ClickHouseBackend
    ├── AsyncClickHouseBackend
    └── ...
```

## 后端职责

ClickHouse 后端负责以下职责：

### 1. SQL 方言生成

将通用的查询构建器转换为 ClickHouse 特定的 SQL 语句：

```python
# 核心库：通用的查询构建
query = User.query().where(User.c.age >= 18).order_by(User.c.created_at)

# ClickHouse 后端：转换为 ClickHouse SQL
# SELECT * FROM users WHERE age >= 18 ORDER BY created_at
```

### 2. 数据类型映射

处理 ClickHouse 特定的数据类型，包括：

- TINYINT, SMALLINT, MEDIUMINT, INT, BIGINT
- FLOAT, DOUBLE, DECIMAL
- CHAR, VARCHAR, TEXT, TINYTEXT, MEDIUMTEXT, LONGTEXT
- DATE, TIME, DATETIME, TIMESTAMP, YEAR
- BINARY, VARBINARY, BLOB
- JSON (ClickHouse 5.7+)
- ENUM, SET

### 3. 连接管理

提供 ClickHouse 连接建立、断开等底层操作。

### 4. 事务控制

实现 ClickHouse 事务的 BEGIN、COMMIT、ROLLBACK 逻辑。

## 快速开始

### 1. 安装

```bash
pip install rhosocial-activerecord
pip install rhosocial-activerecord-clickhouse
```

### 2. 定义模型

```python
import uuid
from typing import ClassVar
from pydantic import Field
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, TimestampMixin


class User(UUIDMixin, TimestampMixin, ActiveRecord):
    username: str = Field(..., max_length=50)
    email: str

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'users'
```

### 3. 配置后端

```python
from rhosocial.activerecord.backend.impl.clickhouse import (
    ClickHouseBackend,
    ClickHouseConnectionConfig,
)

# 配置 ClickHouse 连接
config = ClickHouseConnectionConfig(
    host='localhost',
    port=3306,
    database='myapp',
    username='user',
    password='password',
)

# 为模型配置后端
User.configure(config, ClickHouseBackend)
```

### 4. 增删改查

```python
# 创建记录
user = User(username='tom', email='tom@example.com')
user.save()

# 查询记录
user = User.query().where(User.c.username == 'tom').first()

# 更新记录
user.email = 'tom.new@example.com'
user.save()

# 删除记录
user.delete()
```

💡 *AI 提示词：* "什么是 ActiveRecord 模式？它的优缺点是什么？"
