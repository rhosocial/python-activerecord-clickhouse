# 第一个 CRUD 应用

本节给出一个完整的建表—插入—查询—更新—删除流程，比 [快速开始](quick_start.md) 更详尽。

前置条件：已启动 ClickHouse 实例（见 [安装指南](../installation/installation.md#启动本地-clickhouse可选用于测试)），已安装核心库与本后端。

> 📐 **设计哲学**：`ActiveQuery` 是只读查询（类比 DQL），**没有** `delete()`/`update()` 方法。变更（DML）只能通过 ActiveRecord 实例方法（`instance.save()`/`instance.delete()`）或类方法（`Model.bulk_delete([...])`）进行。

## 1. 定义模型与配置

```python
from datetime import datetime
from typing import Optional, ClassVar
from pydantic import Field
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend
from rhosocial.activerecord.backend.impl.clickhouse.config import ClickHouseConnectionConfig

class User(ActiveRecord):
    __table_name__ = "users"
    __primary_key__ = "id"
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    username: str = Field(min_length=3, max_length=50)
    email: str
    age: Optional[int] = None
    created_at: Optional[datetime] = None

config = ClickHouseConnectionConfig(
    host="localhost", port=8123,
    database="test_db", username="root", password="password",
)
User.configure(config, ClickHouseBackend)
```

## 2. 建表（DDL 表达式 vs 原始 SQL 对照）

ClickHouse 不自动建表。本后端**继承并扩展**了核心库的 DDL 表达式，能用 `CreateTableExpression` 生成完整 ClickHouse 原生 DDL。两种方式等价：

### 方式 A：DDL 表达式（推荐，类型安全、可序列化）

```python
from rhosocial.activerecord.backend.expression.statements import (
    CreateTableExpression, ColumnDefinition, DropTableExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseInt64Type, ClickHouseStringType, ClickHouseInt32Type,
    ClickHouseNullableType, ClickHouseDateTime64Type,
)

# 通过 storage_options 声明 ENGINE / ORDER BY / PARTITION BY / TTL / SETTINGS
expr = CreateTableExpression(
    dialect=User.__dialect__,
    table="users",
    columns=[
        ColumnDefinition(name="id", data_type=ClickHouseInt64Type()),
        ColumnDefinition(name="username", data_type=ClickHouseStringType()),
        ColumnDefinition(name="age", data_type=ClickHouseNullableType(ClickHouseInt32Type())),
        ColumnDefinition(name="created_at", data_type=ClickHouseDateTime64Type(6)),
    ],
    storage_options={
        "ENGINE": "MergeTree",
        "ORDER BY": ["id", "username"],
        # 见下方"UPDATE/DELETE 前置设置"说明
        "SETTINGS": "enable_block_number_column = 1, enable_block_offset_column = 1",
    },
    if_not_exists=True,
)
sql, _ = expr.to_sql()
User.__backend__.execute(sql)   # 执行建表
```

`storage_options` 接受的 key（大小写/下划线不敏感）：`ENGINE`、`ORDER BY`、`PARTITION BY`、`PRIMARY KEY`、`SAMPLE BY`、`TTL`、`SETTINGS`。值原样插入 SQL。

### 方式 B：原始 SQL（等价，便于对照理解）

```sql
CREATE TABLE IF NOT EXISTS users (
    id         Int64,
    username   String,
    age        Nullable(Int32),
    created_at DateTime64(6, 'UTC')
) ENGINE = MergeTree
ORDER BY (id, username)
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
```

两种方式生成**完全相同**的 DDL，证明本后端的 SQL 语义全覆盖——每个 ClickHouse DDL 子句都能通过表达式生成，无需手写 SQL。

### ⚠️ UPDATE/DELETE 前置设置

ClickHouse 26.x 默认**拒绝**轻量级 UPDATE/DELETE（`Code: 48 NOT_IMPLEMENTED`）。要启用本后端的 `save()`（UPDATE 路径）与 `delete()`，建表时**必须**加：

```
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
```

或建表后 `ALTER TABLE users MODIFY SETTING enable_block_number_column = 1, enable_block_offset_column = 1`。详见 [变更（UPDATE/DELETE）](../capabilities/mutations.md)。

## 3. Create（插入）

```python
alice = User(username="alice", email="alice@example.com", age=28)
alice.save()
print(alice.id)            # 客户端生成的雪花 Int64，save() 后已回填

bob = User(username="bob", email="bob@example.com")
bob.save()
```

`save()` 走 INSERT，主键由 [客户端雪花 ID](../capabilities/snowflake_ids.md) 生成。批量插入用 `Model.bulk_insert([...])`，后端一次性生成连续 id 序列。

> 注意：ClickHouse 不报告 INSERT 的行数，故 INSERT 的 `affected_rows` 始终为 `0`（与 UPDATE/DELETE 不同）。

## 4. Read（查询）

`ActiveQuery` 只读（DQL），支持过滤/排序/分页/聚合：

```python
# 单行按主键
u = User.query().where(User.c.id == alice.id).one()

# 过滤 + 排序 + 分页
young = (User.query()
         .where(User.c.age < 30)
         .order_by(User.c.username)
         .limit(20)
         .offset(0)
         .all())

# 聚合
total = User.query().count()
```

## 5. Update（实例变更）

```python
alice.age = 31
alice.save()      # UPDATE users SET age=31 WHERE id=?  (lightweight update, 同步)
```

变更以轻量级 UPDATE 同步执行。`affected_rows` 是 WHERE 匹配行的预计数。详见 [变更](../capabilities/mutations.md)。

> ⚠️ 排序键列（`id`/`username`）**不可更新**，否则抛错。

## 6. Delete（实例删除 + 批量删除）

```python
# 单个实例删除
alice.delete()

# 批量删除：先查询得到实例列表，再走类方法 bulk_delete
to_delete = User.query().where(User.c.age < 18).all()
User.bulk_delete(to_delete)
```

> ActiveQuery 没有 `delete()` 方法（DQL 只读）。批量删除走 `Model.bulk_delete([...])` 类方法，逐个实例 `delete()` 则用于单条。

## 7. 事务：不存在

```python
with User.transaction():
    bob.save()
    alice.delete()
# 任一步失败，另一步不会回滚
```

`transaction()` 是空操作上下文管理器，仅为让通用代码路径可运行，**没有** 跨语句事务保证。详见 [能力边界](../introduction/capability_boundaries.md)。

## 8. 不支持的操作会快速失败

```python
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

# UPSERT 不支持
try:
    # ...走 upsert 路径...
    pass
except UnsupportedFeatureError:
    # 改走 INSERT + ReplacingMergeTree
    ...
```

调用前用 `dialect.supports_*()` 显式探测能力，跨后端切换更清晰。

## 下一步

- [字段类型映射](../modeling/field_types.md)
- [表引擎与排序键](../ddl/table_engine.md)
- [变更（UPDATE/DELETE）](../capabilities/mutations.md)
