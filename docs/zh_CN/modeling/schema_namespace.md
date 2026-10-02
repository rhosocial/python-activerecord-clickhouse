# docs/zh_CN/modeling/schema_namespace.md

# ClickHouse 后端里的 schema 名称

> ClickHouse 没有 schema 这一层。`schema_name` 照样接受，但在本后端它指的是
> **database**。这一页把它放在开头，因为这是读者对「schema」最容易想错的一处。

## 这里的 `schema_name` 指的是 database

`supports_schema()` 返回 `True`，传进去的值也真能用——但底下并没有 schema 层。
ClickHouse dialect 实现了核心库的 `SchemaSupport` 协议，而它上面每一个 schema
DDL 开关都是 `False`：

| 能力 | 值 |
|---|---|
| `supports_schema()` | `True` |
| `supports_create_schema()` | `False` |
| `supports_drop_schema()` | `False` |
| `supports_schema_if_not_exists()` | `False` |
| `supports_schema_if_exists()` | `False` |

这两组开关回答的是不同的问题，所以它们本来就可以不一致。`supports_schema()`
问的是「`schema_name` 能不能作为限定符送到服务端」，其余几个问的是「这个
dialect 能不能**建**出一个命名空间」。在 ClickHouse 上，前者的答案是能，后者
是不能。能把引用限定住，和能建出一个供限定的命名空间，是两回事。

| | PostgreSQL | ClickHouse |
|---|---|---|
| `supports_schema()` | `True` | `True` |
| `schema_name` 指向 | schema | **database** |
| `CREATE SCHEMA` | 可用 | **语法错误** |
| `SHOW SCHEMAS` | 可用 | **语法错误** |
| 取当前值的函数 | `current_schema()` | `currentDatabase()` |
| 渲染结果 | `"app"."orders"` | `` `app`.`orders` `` |

ClickHouse 自己写限定引用就是 `` `db`.`orders` `` 这个形式，所以
`schema_name="app"` 生成出来的正是它，服务端也接受。

MySQL 和 MariaDB 落到同一个结果，走的是另一条路：它们把「schema」这个词留在
语言里，并让它作为 `database` 的同义词，所以 `CREATE SCHEMA` 和 `SHOW SCHEMAS`
在那里都能用，作用对象也都是 database。ClickHouse 去掉了同义词，留下了概念。
同一个 `schema_name` 值在三者上生成同样的 SQL，而「这层东西叫什么」在三者上
并不一致。MySQL 与 MariaDB 那两行记在核心库指南的对照表里。

## 在模型上声明 database

`__schema_name__` 放的是 database 名。`__table_name__` 与 `__schema_name__` 是
两个独立属性，不能合并——合并之后那个标识符会被当成一个整体加引号，里面带着
一个点。

```python
from typing import ClassVar, Optional
from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.model import ActiveRecord

class Order(ActiveRecord):
    __table_name__ = "orders"
    __schema_name__ = "app"        # 这是 database
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
```

```sql
-- 生成结果
SELECT `orders`.`id` FROM `app`.`orders`
```

不设 `__schema_name__` 时表就渲染成不带限定的形式，解析时落到会话的当前
database 上：

```sql
SELECT `orders`.`id` FROM `orders`
```

上面两种渲染结果，以及本页其余所有 SQL，都由 `ClickHouseDialect((26, 7, 0))`
生成。同一条语句里列引用那一侧，见[列引用最多两段](#列引用最多两段)。

## DDL 自己带 `schema_name`

`__schema_name__` 决定的是 DML 用的命名空间，DDL 语句不读它，每条语句各自
接受自己的 `schema_name`。这是通用规则；下面三条语句是 ClickHouse 对「模型带
schema 时用得上的 DDL」所接受的形式。

建 database 本身用 `CREATE DATABASE`，由 `CreateDatabaseExpression` 渲染：

```python
from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    CreateDatabaseExpression,
)

CreateDatabaseExpression(dialect, "app")
# CREATE DATABASE `app`
```

`CREATE TABLE` 的目标位置收 `TableExpression`，database 就写在这里：

```python
from rhosocial.activerecord.backend.expression import (
    CreateTableExpression, TableExpression,
)

CreateTableExpression(
    dialect,
    TableExpression(dialect, "orders", schema_name="app"),
    columns=[...],
)
# CREATE TABLE `app`.`orders` (...) ENGINE = MergeTree() ORDER BY ...
```

`TRUNCATE` 用的是同一个关键字，类在
`rhosocial.activerecord.backend.expression.statements.ddl_truncate.TruncateExpression`：

```python
TruncateExpression(dialect, "orders", schema_name="app")
# TRUNCATE TABLE `app`.`orders`
```

`__schema_name__` 是 `app` 的模型，和建出未限定 `orders` 的迁移，并不会自动对上。
迁移必须自己写明它指的是哪个 database。

## 列引用最多两段

表引用在本后端是 `database.table`。列引用最多到 `table.column`，所以 database
不会出现第二次：

```sql
SELECT `orders`.`id` FROM `app`.`orders`
```

`format_column` 完全不理会 `schema_name`——它不是拒绝这个值，而是三段式的
`database.table.column` 并不是这个 dialect 会生成的写法。同时带表名和 schema
的 `Column` 渲染出来就是两段式：

```python
dialect.format_column(Column(dialect, "id", table="orders", schema_name="app"))
# ('`orders`.`id`', ())
```

带 schema 但没有表名的裸列是唯一会告警而不直接渲染的情况，因为列引用总要有
一张表才能限定：

```
UserWarning: ClickHouse: dropping schema_name='app' from column 'id' because no
table was given; a column reference needs a table to be qualified
```

一旦有了别名，就由别名标识这个范围，其它后端也是如此：

```sql
SELECT `o`.`id` FROM `app`.`orders` AS `o`
```

## join、集合操作与 CTE

join 的每一侧各自限定自己的 database，所以一条语句可以跨两个：

```sql
SELECT `orders`.`id` FROM `shop`.`orders` JOIN `crm`.`users` ON `orders`.`user_id` = `users`.`id`
```

集合操作合并的是查询而不是具名对象，所以每个分支各自保留自己的 database，
其余部分不变：

```sql
SELECT `id` FROM `shop`.`orders` UNION DISTINCT SELECT `id` FROM `crm`.`customers`
```

CTE 是给后面那条查询用的名字，所以它的名字保持裸名，被它包住的查询照常限定：

```sql
WITH `recent` AS (SELECT `id` FROM `shop`.`orders`)
SELECT `recent`.`id` FROM `recent`
```

## UPDATE 的过滤条件与版本有关

UPDATE 是本后端最容易写错的地方，因为正确的 SQL 会随服务端版本变。

ClickHouse 的 `UPDATE` 是一次 mutation：服务端把它改写成
`_CAST(if(<filter>, <new value>, <old value>), <type>)`，再拿这段表达式去对
被改写 part 的列求值。在 26.7 之下仍在维护的分支上——25.8 LTS 与 26.3 LTS——
这条解析路径没有表限定符的概念：它把 `tasks.id` 当成一个名叫 `tasks.id` 的
标识符，找不到这样的列，于是拒绝这条语句：

```
Missing columns: 'tasks.id' while processing:
'_CAST(if(tasks.id = 381195967974322176, ...), 'Nullable(String)')
```

ClickHouse 在 26.7 修了这个问题——PR #109491，关闭
[ClickHouse/ClickHouse#71760](https://github.com/ClickHouse/ClickHouse/issues/71760)。
所以 `ClickHouseUpdateMixin` 按版本做门控，分界点写成一个具名常量：

```python
from rhosocial.activerecord.backend.impl.clickhouse.mixins.update import (
    ClickHouseUpdateMixin,
)

ClickHouseUpdateMixin.QUALIFIED_MUTATION_COLUMN_VERSION   # (26, 7, 0)
```

`supports_update_column_qualification()` 报出 dialect 站在分界线的哪一侧：

| 服务端版本 | `supports_update_column_qualification()` | 过滤条件渲染成 |
|---|---|---|
| 25.8 | `False` | 裸列 |
| 26.3 | `False` | 裸列 |
| 26.7 | `True` | 带限定 |

版本取自 `dialect.version`，由 backend 从自己的 `version` 参数设置，或者由
`introspect_and_adapt()` 读 `SELECT version()` 得到。dialect 尚未 adapt 时，
门控会抛 `DialectNotAdaptedException`，而不是先猜一个。

所以同一个 `WHERE` 子句会渲染出两种形态：

```sql
-- 25.8 与 26.3
UPDATE `app`.`tasks` SET `deleted_at` = %s WHERE `id` = %s

-- 26.7 及之后
UPDATE `app`.`tasks` SET `deleted_at` = %s WHERE `tasks`.`id` = %s
```

注意哪些东西没有变。目标表在任何版本上都保留 database 限定，因为它才是点名
被改写的那张表。`SET` 子句和参数列表也完全一致。被去掉的只有过滤条件里的表
限定符，而且只在 26.7 以下才去掉。

关于门控的作用范围，还有三点：

- 它只作用于 `UPDATE`，别的语句一概不管。`ClickHouseUpdateMixin` 只覆盖了
  `format_update_statement`，没有覆盖别的 formatter，所以 `DELETE` 在所有版本
  上都保留列自带的限定符。
- 它重建过滤条件那棵树，而不是就地改写。遍历过程中被替换的是那些 `Column`
  节点，换成不带表名的等价物，因此同一个 `Column` 在别处被别的谓词共用时，
  那边的限定符仍然在。
- 过滤条件能构造出的各种谓词形态都覆盖到了——比较、`LIKE`、`IN`、`BETWEEN`、
  `AND`/`OR`/`NOT`、一元与二元表达式，以及嵌在函数调用里的列。

因此模型上的一条 `UPDATE` 在每条维护分支上都能原样运行。如果你要针对某个
具体版本手写过滤条件，先确认它落在 26.7 的哪一侧。

## 常见错误

**没有 `CREATE SCHEMA` 这条语句。** 迁移里写它会在服务端报语法错误；dialect
在语句发出之前就抛 `UnsupportedFeatureError`。改成建 database：

```sql
CREATE DATABASE app
```

`DROP SCHEMA` 同理。本后端也没有 `ShowSchemasExpression`——对应的列表语句是
`SHOW DATABASES`，其余自省走的是 `system.*` 表。

**没有 `currentSchema()` 这个函数。** 名字不存在，调用它的语句会在服务端失败，
而报错文本会提示 `currentSchemas`/`current_schemas`。这个提示不能直接照用：
ClickHouse 里的 `currentSchemas(bool)` 是为兼容 PostgreSQL 加的包装，返回的是
装着当前 database 名的一个 `Array(String)`，而不是单个字符串。要用的函数是
`currentDatabase()`。

**这里 `schema` 不是同义词。** 为 MySQL 或 MariaDB 写的迁移如果用了
`CREATE SCHEMA` 或 `SHOW SCHEMAS`，搬不过来，DDL 得改写成 `CREATE DATABASE`
和 `SHOW DATABASES`。

**26.7 以下的 `UPDATE` 里带限定的 `WHERE` 会失败。** 上一节讲过这个，症状是
`Missing columns: '<table>.<column>'`。

## 取当前 database

`get_current_schema()` 返回当前 database。方法名是跨后端统一的 API，读到的却是
database。它通过 `current_database(dialect)` 这个表达式工厂构造出调用
`currentDatabase` 函数的查询，再取结果行里的第一列：

```python
backend.get_current_schema()   # 'default'
```

这个值随会话变化，也就是说它取决于连接建立时打开的是哪个 database，也就是
`ClickHouseConnectionConfig` 上的 `database` 配置项——它会在连接时交给
clickhouse-connect。未限定的引用就按它解析。

只有同步版本。clickhouse-connect 只支持同步，没有对应的 async backend。

## 空 `schema_name` 在渲染阶段被拒绝

`schema_name=""` 不表示「不带限定」，`None` 才是。检查发生在渲染阶段，不在构造
阶段，因为表达式本身只负责收集参数：

```python
TableExpression(dialect, "orders", schema_name="")   # 构造时不报错
QueryExpression(dialect, select=[Column(dialect, "id")], from_=[that_table]).to_sql()
# ValueError: TableExpression.schema_name must be a non-empty string;
#             use None for an unqualified reference
```

渲染层把空串当作未限定，所以放它过去就意味着：调用方要的是 `app.orders`，拿到
的却是 `orders`。这个检查要防的正是这种情况，而且它在所有后端上都成立。

## database 不存在时

框架不会拦你。database 是 ClickHouse 自己就能表达的命名空间，所以传了照传；
等语句发过去，服务端发现没有这个 database，才会报错。这里校验的是取值形状，
不是是否存在，也不与连接的当前 database 作比较。一个指向别的 database 的
`schema_name`，指向的是另一张表，或者什么都不是。

## 相关

- [Mutation（UPDATE/DELETE）](../capabilities/mutations.md) —— UPDATE/DELETE
  的其余部分，包括轻量更新所要求的设置
- [不支持的功能](../capabilities/unsupported.md) —— 本后端直接拒绝的东西，
  以及它们和「接受但含义不同」这种情形的区别
- 核心库的 `docs/modeling/schema_namespace.md` —— 跨后端对照表，以及在各后端
  上都成立的那些规则
