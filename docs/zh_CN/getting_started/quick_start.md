# 快速开始

下面是一个最小可运行示例。前置条件：已启动一个 ClickHouse 实例（见 [安装指南](../installation/installation.md#启动本地-clickhouse可选用于测试)），且已安装核心库与本后端。

## 完整示例

```python
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

    id: Optional[int] = None          # 雪花 id，save() 时由后端生成
    username: str = Field(min_length=3, max_length=50)
    email: str
    age: Optional[int] = None         # -> Nullable(Int32) 列

config = ClickHouseConnectionConfig(
    host="localhost", port=8123,
    database="test_db", username="root", password="password",
)

User.configure(config, ClickHouseBackend)

# CREATE — id 由客户端雪花算法生成并回填
user = User(username="alice", email="alice@example.com")
user.save()
print(user.id)            # 一个 Int64 雪花 id

# READ — ActiveQuery 是只读（DQL）
young = User.query().where(User.c.age < 30).order_by(User.c.username).all()

# UPDATE — 实例 save() 走 lightweight UPDATE
user.age = 31
user.save()

# DELETE — 实例 delete()
user.delete()
```

## 建表

ClickHouse 不会自动建表。运行上述代码前，需先建好 `MergeTree` 表（可选字段用 `Nullable(T)`）：

```sql
CREATE TABLE IF NOT EXISTS users (
    id        Int64,
    username  String,
    email     String,
    age       Nullable(Int32)
)
ENGINE = MergeTree
ORDER BY (id, username)
SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1;
```

> ⚠️ `SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1` 是 UPDATE/DELETE 的前置条件——ClickHouse 26.x 默认拒绝轻量级变更。详见 [变更（UPDATE/DELETE）](../capabilities/mutations.md)。
>
> 也可用 DDL 表达式（`CreateTableExpression` + `storage_options`）生成等价 DDL，见 [第一个 CRUD 应用](first_crud.md#2-建表ddl-表达式-vs-原始-sql-对照)。

## 关键点

1. **id 是客户端生成的**：ClickHouse 无 `AUTO_INCREMENT`，`save()` 时后端用雪花算法生成 `Int64` 并回填到模型。详见 [客户端雪花 ID](../capabilities/snowflake_ids.md)。
2. **可选字段 → `Nullable(T)`**：模型上的 `Optional[int]` 会映射到 `Nullable(Int32)` 列。详见 [Nullable 与可选字段](../modeling/nullable.md)。
3. **ActiveQuery 只读（DQL）**：查询用 `Model.query()`；变更（DML）只能走实例方法（`save()`/`delete()`）或类方法（`bulk_insert`/`bulk_delete`）。
4. **没有事务**：上面的 `save()` 各自独立，无跨语句事务保证。
5. **变更需表设置**：`UPDATE`/`DELETE` 是轻量级变更，需建表加 `enable_block_number_column`/`enable_block_offset_column`。

## 下一步

- [第一个 CRUD 应用](first_crud.md)：完整 CRUD 流程与 DDL 表达式对照
- [字段类型映射](../modeling/field_types.md)
