# ClickHouse Dialect 表达式

## 概述

ClickHouse 有一些特定的 SQL 语法和函数，本节介绍常用的 ClickHouse 特有表达式。

## DDL 语句

### CREATE TABLE ... LIKE

ClickHouse 支持使用 `LIKE` 子句复制表结构。这对于创建具有相同结构的表备份或测试表非常有用。

```python
from rhosocial.activerecord.backend.expression import CreateTableExpression
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

# 基本用法 - 复制表结构
create_expr = CreateTableExpression(
    dialect=ClickHouseDialect(),
    table_name="users_copy",
    columns=[],
    dialect_options={'like_table': 'users'}
)
# 生成: CREATE TABLE `users_copy` LIKE `users`

# 带模式限定的源表
create_expr = CreateTableExpression(
    dialect=ClickHouseDialect(),
    table_name="users_copy",
    columns=[],
    dialect_options={'like_table': ('production', 'users')}
)
# 生成: CREATE TABLE `users_copy` LIKE `production`.`users`

# 带临时表和 IF NOT EXISTS
create_expr = CreateTableExpression(
    dialect=ClickHouseDialect(),
    table_name="temp_users",
    columns=[],
    temporary=True,
    if_not_exists=True,
    dialect_options={'like_table': 'users'}
)
# 生成: CREATE TABLE TEMPORARY IF NOT EXISTS `temp_users` LIKE `users`
```

**重要说明：**
- 当 `dialect_options` 中指定 `like_table` 时，具有最高优先级
- 所有其他参数（columns、indexes、constraints 等）都会被忽略
- 只有 `temporary` 和 `if_not_exists` 标志会被考虑
- ClickHouse 的 LIKE 会复制：列、索引、约束、默认值、auto_increment 设置

### 语句级常量与 DEFAULT 值

ClickHouse DDL 中的 `DEFAULT` 子句经常需要使用 SQL 语句级常量（statement-level constants），如 `CURRENT_TIMESTAMP`、`NOW()`、`CURRENT_DATE` 等。这些是 SQL 关键字或函数调用，**不是字符串字面量**，因此必须使用表达式实例传入，而非 Python 字符串。

```python
from rhosocial.activerecord.backend.expression.functions.datetime import (
    current_timestamp, now,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition, ColumnConstraint, ColumnConstraintType,
)

# 正确：使用工厂函数传递 SQL:2003 零元函数
ColumnDefinition(
    name='created_at',
    data_type='TIMESTAMP',
    constraints=[
        ColumnConstraint(ColumnConstraintType.DEFAULT,
                         default_value=current_timestamp(dialect)),
        # 生成: `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        # （无括号 — SQL:2003 零元形式）
    ],
)

# 正确：使用 NOW() 函数（非零元函数，始终带括号）
ColumnDefinition(
    name='updated_at',
    data_type='DATETIME',
    constraints=[
        ColumnConstraint(ColumnConstraintType.DEFAULT,
                         default_value=now(dialect)),
        # 生成: `updated_at` DATETIME DEFAULT NOW()
    ],
)

# 正确：数字字面量直接传入 Python 原生类型
ColumnDefinition(
    name='is_active',
    data_type='TINYINT(1)',
    constraints=[
        ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1),
        # 生成: `is_active` TINYINT(1) DEFAULT 1
    ],
)

# 正确：字符串字面量传入 Python 字符串（会自动加引号）
ColumnDefinition(
    name='status',
    data_type='VARCHAR(20)',
    constraints=[
        ColumnConstraint(ColumnConstraintType.DEFAULT, default_value='active'),
        # 生成: `status` VARCHAR(20) DEFAULT 'active'
    ],
)
```

**错误做法：**

```python
# 错误：将 SQL 关键字作为 Python 字符串传入
# 这会导致生成 DEFAULT 'CURRENT_TIMESTAMP'（被引号包裹，变成字符串字面量）
ColumnConstraint(ColumnConstraintType.DEFAULT, default_value='CURRENT_TIMESTAMP')
```

**常见语句级常量对照表：**

| SQL 常量 | Expression API | 说明 |
| ---------- | ---------------------------------------------- | ------ |
| `CURRENT_TIMESTAMP` | `current_timestamp(dialect)` | 当前时间戳（SQL:2003 零元函数，无括号） |
| `CURRENT_TIMESTAMP(6)` | `current_timestamp(dialect, 6)` | 带精度的时间戳（有括号） |
| `NOW()` | `now(dialect)` | 当前日期时间（普通函数） |
| `CURRENT_DATE` | `current_date(dialect)` | 当前日期（SQL:2003 零元函数） |
| `CURRENT_TIME` | `current_time(dialect)` | 当前时间（SQL:2003 零元函数） |
| `UUID()` | `FunctionCall(dialect, 'UUID')` | 生成 UUID（ClickHouse 8.0+） |

> **核心规则**：SQL:2003 零元函数（`CURRENT_TIMESTAMP`、`CURRENT_DATE`、`CURRENT_TIME`、`CURRENT_USER` 等）使用专用工厂函数，自动生成不带括号的标准形式。其他 SQL 中的关键字、函数、常量（不需要引号包裹的），使用 `FunctionCall`；需要引号包裹的字面量值，使用 Python 原生类型（字符串、数字、布尔值）。

## 特有的运算符

### LIKE 表达式

```python
# 搜索以指定字符开头的记录
User.query().where(User.c.name.like('%test%'))

# REGEXP 正则表达式
User.query().where(User.c.name.regexp('^A.*'))
```

## 特有的函数

### GROUP_CONCAT

```python
# 连接分组中的字符串
# SELECT GROUP_CONCAT(name SEPARATOR ',') FROM users GROUP BY role
from rhosocial.activerecord.backend.expression import FunctionExpression


class GroupConcat(FunctionExpression):
    def __init__(self, column, separator=','):
        super().__init__(
            'GROUP_CONCAT',
            column,
            separator=f"SEPARATOR '{separator}'"
        )
```

### ON DUPLICATE KEY UPDATE

```python
# 插入或更新
# INSERT INTO users (id, name) VALUES (1, 'Tom') ON DUPLICATE KEY UPDATE name = 'Tom'
```

### REPLACE INTO

```python
# 替换插入（先删除再插入）
# REPLACE INTO users (id, name) VALUES (1, 'Tom')
```

💡 *AI 提示词：* "ClickHouse 的 REPLACE INTO 和 INSERT ... ON DUPLICATE KEY UPDATE 有什么区别？"

## 表达式级 COLLATE 支持

ClickHouse 支持为列表达式指定排序规则：

```python
from rhosocial.activerecord.backend.expression.collation import collate

# 为列指定排序规则
expr = collate(Column(dialect, "name"), "utf8mb4_general_ci")
# 生成: `name` COLLATE `utf8mb4_general_ci`

# 在 WHERE 条件中使用
query = User.query().where(
    collate(User.c.name, "utf8mb4_unicode_ci") == "alice"
)
```

排序规则名称会根据 ClickHouse 版本进行验证。例如 `utf8mb4_0900_*` 系列需要 ClickHouse 8.0+。

```python
# 检查 COLLATE 支持
if dialect.supports_collate_expression():
    # 可以使用 COLLATE 表达式
    pass
```

## 日期时间间隔表达式

ClickHouse 方言支持标准化的日期时间间隔表达式：

```python
from rhosocial.activerecord.backend.expression.datetime import (
    ExtractExpression, DateTimeField, IntervalExpression, IntervalUnit,
    DateTimeAddExpression, DateTimeSubtractExpression, DateTimeDiffExpression,
)

# EXTRACT
expr = ExtractExpression(dialect, DateTimeField.YEAR, Column(dialect, "created_at"))
# 生成: EXTRACT(YEAR FROM `created_at`)

# 间隔值
interval = IntervalExpression(dialect, 7, IntervalUnit.DAY)
# 生成: INTERVAL 7 DAY

# 日期加法
expr = DateTimeAddExpression(dialect, Column(dialect, "created_at"),
                             IntervalExpression(dialect, 30, IntervalUnit.DAY))
# 生成: DATE_ADD(`created_at`, INTERVAL 30 DAY)

# 日期减法
expr = DateTimeSubtractExpression(dialect, Column(dialect, "created_at"),
                                  IntervalExpression(dialect, 7, IntervalUnit.DAY))
# 生成: DATE_SUB(`created_at`, INTERVAL 7 DAY)

# 日期差
expr = DateTimeDiffExpression(dialect, DateTimeField.DAY,
                              Column(dialect, "start"), Column(dialect, "end"))
# 生成: TIMESTAMPDIFF(DAY, `start`, `end`)
```

## 查询优化器提示 (Optimizer Hints)

ClickHouse 支持 SET_VAR 优化器提示，ClickHouse 9.7+ 还支持超图优化器：

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.optimizer_hint import (
    ClickHouseOptimizerHintExpression, SetVarHint,
)

# 设置优化器开关
hint = ClickHouseOptimizerHintExpression(dialect, [
    SetVarHint("optimizer_switch", "hypergraph_optimizer=on"),
])
# 生成: /*+ SET_VAR(optimizer_switch='hypergraph_optimizer=on') */

# 检查支持
if dialect.supports_optimizer_hint():
    pass

if dialect.supports_hypergraph_optimizer():
    # ClickHouse 9.7+ 超图优化器
    pass
```

## JSON 二象性视图 (ClickHouse 9.7+)

ClickHouse 9.7+ 支持 JSON 二象性视图（JSON Duality View）：

```python
from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
    CreateJsonDualityViewExpression, DropJsonDualityViewExpression,
    DualityObjectSpec, DualityDMLTag, DualityColumnMapping,
)

# 创建 JSON 二象性视图
create = CreateJsonDualityViewExpression(
    dialect,
    view_name="user_details",
    root_spec=DualityObjectSpec(
        tags=[DualityDMLTag.INSERT, DualityDMLTag.UPDATE, DualityDMLTag.DELETE],
        columns=[
            DualityColumnMapping("id", Column(dialect, "id", "users")),
        ],
        from_table="users",
    ),
    replace=True,
)
# sql: 'CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW "user_details" AS ...'

# 检查支持
if dialect.supports_json_duality_view():
    # ClickHouse 9.7+
    pass
```

## 查询运行时函数与常量

ClickHouse 支持不涉及数据源的纯函数查询，如 `SELECT CURRENT_TIMESTAMP`、`SELECT NOW()`、`SELECT VERSION()` 等。使用 `QueryExpression` 不指定 `from_` 子句即可实现。

```python
from rhosocial.activerecord.backend.expression import QueryExpression
from rhosocial.activerecord.backend.expression.core import FunctionCall, Literal
from rhosocial.activerecord.backend.expression.functions.datetime import (
    current_timestamp, now, current_date, current_time,
)

# SELECT CURRENT_TIMESTAMP（零元函数 — 无括号）
query = QueryExpression(
    dialect=dialect,
    select=[current_timestamp(dialect)],
)
sql, params = query.to_sql()
# 生成: SELECT CURRENT_TIMESTAMP

# SELECT NOW()
query = QueryExpression(
    dialect=dialect,
    select=[now(dialect)],
)
# 生成: SELECT NOW()

# SELECT CURRENT_DATE, CURRENT_TIME（零元函数 — 无括号）
query = QueryExpression(
    dialect=dialect,
    select=[
        current_date(dialect),
        current_time(dialect),
    ],
)
# 生成: SELECT CURRENT_DATE, CURRENT_TIME

# 带别名的多函数查询
query = QueryExpression(
    dialect=dialect,
    select=[
        now(dialect).as_('current_time'),
        FunctionCall(dialect, 'DATABASE').as_('db_name'),
        FunctionCall(dialect, 'VERSION').as_('db_version'),
    ],
)
# 生成: SELECT NOW() AS `current_time`, DATABASE() AS `db_name`, VERSION() AS `db_version`

# 带参数的函数调用
query = QueryExpression(
    dialect=dialect,
    select=[
        FunctionCall(dialect, 'DATE_FORMAT',
                     now(dialect),
                     Literal(dialect, '%Y-%m-%d')).as_('formatted_date'),
    ],
)
# 生成: SELECT DATE_FORMAT(NOW(), %s) AS `formatted_date`
```

**常用 ClickHouse 信息函数：**

| 函数 | Expression API | 返回值 |
| ------ | ---------------------------------------------- | ------ |
| `CURRENT_TIMESTAMP` | `current_timestamp(dialect)` | 当前时间戳（零元函数） |
| `CURRENT_TIMESTAMP(6)` | `current_timestamp(dialect, 6)` | 带精度的时间戳 |
| `NOW()` | `now(dialect)` | 当前日期时间 |
| `CURRENT_DATE` | `current_date(dialect)` | 当前日期（零元函数） |
| `CURRENT_TIME` | `current_time(dialect)` | 当前时间（零元函数） |
| `DATABASE()` | `FunctionCall(dialect, 'DATABASE')` | 当前数据库名 |
| `VERSION()` | `FunctionCall(dialect, 'VERSION')` | ClickHouse 版本号 |
| `USER()` | `FunctionCall(dialect, 'USER')` | 当前用户 |
| `UUID()` | `FunctionCall(dialect, 'UUID')` | 生成 UUID（8.0+） |
| `CONNECTION_ID()` | `FunctionCall(dialect, 'CONNECTION_ID')` | 连接 ID |

> **注意**：SQL:2003 零元函数（`CURRENT_TIMESTAMP`、`CURRENT_DATE`、`CURRENT_TIME` 等）在无参数调用时生成不带括号的标准形式。ClickHouse 也接受带括号的形式（如 `CURRENT_TIMESTAMP()`）——两种形式在 DDL DEFAULT 和 SELECT 上下文中均合法。推荐使用专用工厂函数（`current_timestamp()`、`current_date()` 等），它们会自动处理零元形式。
