# 数据库内省

ClickHouse 后端提供完整的数据库内省功能，使用 `information_schema` 系统表和 `SHOW` 命令查询数据库结构元数据。

## 概述

ClickHouse 内省系统位于 `backend.introspector` 属性中，提供：

- **数据库信息**：名称、版本、字符集、排序规则
- **表信息**：表列表、表详情、存储引擎、表注释
- **列信息**：列名、数据类型、是否可空、默认值、字符集
- **索引信息**：索引名、列、唯一性、索引类型（BTREE、FULLTEXT 等）
- **外键信息**：引用表、列映射、更新/删除行为
- **视图信息**：视图定义 SQL
- **触发器信息**：触发事件、执行时机

## 基本用法

### 访问内省器

```python
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

backend = ClickHouseBackend(
    host="localhost",
    port=3306,
    database="mydb",
    user="root",
    password="password"
)
backend.connect()

# 通过 introspector 属性访问
introspector = backend.introspector
```

### 获取数据库信息

```python
# 获取数据库基本信息
db_info = backend.introspector.get_database_info()
print(f"数据库名称: {db_info.name}")
print(f"版本: {db_info.version}")
print(f"字符集: {db_info.encoding}")
print(f"排序规则: {db_info.collation}")
```

### 列出表

```python
# 列出所有用户表
tables = backend.introspector.list_tables()
for table in tables:
    print(f"表: {table.name}, 类型: {table.table_type.value}")
    if table.comment:
        print(f"  注释: {table.comment}")

# 包含系统数据库的表（通常不需要）
all_tables = backend.introspector.list_tables(include_system=True)

# 过滤特定类型
base_tables = backend.introspector.list_tables(table_type="BASE TABLE")
views = backend.introspector.list_tables(table_type="VIEW")

# 检查表是否存在
if backend.introspector.table_exists("users"):
    print("users 表存在")

# 获取表详情
table_info = backend.introspector.get_table_info("users")
if table_info:
    print(f"表名: {table_info.name}")
    print(f"存储引擎: {table_info.extra.get('engine', 'InnoDB')}")
```

### 查询列信息

```python
# 列出表的所有列
columns = backend.introspector.list_columns("users")
for col in columns:
    nullable = "NOT NULL" if col.nullable.value == "NOT_NULL" else "NULLABLE"
    pk = " [PK]" if col.is_primary_key else ""
    charset = f" ({col.character_set})" if col.character_set else ""
    print(f"{col.name}: {col.data_type}{charset} {nullable}{pk}")
    if col.comment:
        print(f"  注释: {col.comment}")

# 获取主键信息
pk = backend.introspector.get_primary_key("users")
if pk:
    print(f"主键: {[c.name for c in pk.columns]}")

# 获取单列信息
col_info = backend.introspector.get_column_info("users", "email")
```

### 查询索引

```python
# 列出表的所有索引
indexes = backend.introspector.list_indexes("users")
for idx in indexes:
    idx_type = idx.index_type.value if idx.index_type else "BTREE"
    unique = "UNIQUE " if idx.is_unique else ""
    print(f"{unique}索引: {idx.name} ({idx_type})")
    for col in idx.columns:
        print(f"  - {col.name}")
```

### 查询外键

```python
# 列出表的外键
foreign_keys = backend.introspector.list_foreign_keys("posts")
for fk in foreign_keys:
    print(f"外键: {fk.name}")
    print(f"  列: {fk.columns} -> {fk.referenced_table}.{fk.referenced_columns}")
    print(f"  ON DELETE: {fk.on_delete.value}")
    print(f"  ON UPDATE: {fk.on_update.value}")
```

### 查询视图

```python
# 列出所有视图
views = backend.introspector.list_views()
for view in views:
    print(f"视图: {view.name}")

# 获取视图详情
view_info = backend.introspector.get_view_info("user_posts_summary")
if view_info:
    print(f"定义: {view_info.definition}")
```

### 查询触发器

```python
# 列出所有触发器
triggers = backend.introspector.list_triggers()
for trigger in triggers:
    print(f"触发器: {trigger.name} on {trigger.table_name}")

# 列出特定表的触发器
table_triggers = backend.introspector.list_triggers("users")
```

## ClickHouse 专属：ShowIntrospector

ClickHouse 提供独特的 `SHOW` 命令支持，可通过 `backend.introspector.show` 访问：

```python
# 访问 ShowIntrospector
show = backend.introspector.show

# SHOW CREATE TABLE
create_table = show.show_create_table("users")
print(f"建表语句:\n{create_table.create_statement}")

# SHOW CREATE VIEW
create_view = show.show_create_view("user_posts_summary")
print(f"建视图语句:\n{create_view.create_statement}")

# SHOW COLUMNS
columns = show.show_columns("users")
for col in columns:
    print(f"{col.field}: {col.type} {col.null} {col.key} {col.default}")

# SHOW INDEX
indexes = show.show_index("users")
for idx in indexes:
    print(f"索引: {idx.index_name}, 列: {idx.column_name}")

# SHOW TABLE STATUS
table_status = show.show_table_status("users")
print(f"引擎: {table_status.engine}")
print(f"行数: {table_status.rows}")
print(f"自增: {table_status.auto_increment}")

# SHOW TABLES
tables = show.show_tables()
for table in tables:
    print(f"表: {table}")

# SHOW DATABASES
databases = show.show_databases()
for db in databases:
    print(f"数据库: {db}")

# SHOW TRIGGERS
triggers = show.show_triggers("users")
for trigger in triggers:
    print(f"触发器: {trigger.trigger}, 事件: {trigger.event}")

# SHOW VARIABLES
variables = show.show_variables("character_set_server")
for var in variables:
    print(f"{var.variable_name}: {var.value}")

# SHOW STATUS
status = show.show_status("Threads_connected")
for s in status:
    print(f"{s.variable_name}: {s.value}")

# SHOW PROCESSLIST
processes = show.show_processlist()
for proc in processes:
    print(f"ID: {proc.id}, 用户: {proc.user}, 状态: {proc.state}")

# SHOW ENGINES
engines = show.show_engines()
for engine in engines:
    print(f"{engine.engine}: {'支持' if engine.support == 'YES' else '不支持'}")

# SHOW CHARSET
charsets = show.show_charset()
for charset in charsets:
    print(f"{charset.charset}: {charset.description}")

# SHOW COLLATION
collations = show.show_collation("utf8mb4")
for collation in collations:
    print(f"{collation.collation}: {collation.charset}")
```

## 异步 API

异步后端提供相同的内省方法，方法名与同步版本相同：

```python
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend

backend = AsyncClickHouseBackend(
    host="localhost",
    port=3306,
    database="mydb",
    user="root",
    password="password"
)
await backend.connect()

# 异步内省方法（方法名与同步版本相同）
db_info = await backend.introspector.get_database_info()
tables = await backend.introspector.list_tables()
columns = await backend.introspector.list_columns("users")

# 异步 SHOW 命令
create_table = await backend.introspector.show.show_create_table("users")
```

## 缓存管理

内省结果默认会被缓存以提高性能：

```python
# 清除所有内省缓存
backend.introspector.clear_cache()

# 使特定作用域的缓存失效
from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

# 使所有表相关缓存失效
backend.introspector.invalidate_cache(scope=IntrospectionScope.TABLE)

# 使特定表的缓存失效
backend.introspector.invalidate_cache(
    scope=IntrospectionScope.TABLE,
    name="users"
)
```

## ClickHouse 特定行为

### 系统数据库

ClickHouse 默认排除以下系统数据库：

- `information_schema` — 元数据信息
- `performance_schema` — 性能监控
- `clickhouse` — 系统用户和权限
- `sys` — 系统视图和存储过程

如需包含这些数据库，使用 `include_system=True` 参数。

### 存储引擎信息

表信息中的 `extra` 字段包含 ClickHouse 特有信息：

```python
table_info = backend.introspector.get_table_info("users")
print(f"存储引擎: {table_info.extra.get('engine')}")
print(f"自增值: {table_info.extra.get('auto_increment')}")
print(f"创建时间: {table_info.extra.get('create_time')}")
print(f"更新时间: {table_info.extra.get('update_time')}")
```

### 字符集和排序规则

ClickHouse 列信息包含字符集和排序规则：

```python
columns = backend.introspector.list_columns("users")
for col in columns:
    if col.character_set:
        print(f"{col.name}: 字符集={col.character_set}, 排序规则={col.collation}")
```

### 索引类型

ClickHouse 支持多种索引类型：

| 索引类型 | 说明 |
|---------|------|
| `BTREE` | 默认索引类型 |
| `HASH` | 仅 Memory 引擎支持 |
| `FULLTEXT` | 全文索引 |
| `RTREE` | 空间索引 |
| `SPATIAL` | 空间索引（别名） |

```python
indexes = backend.introspector.list_indexes("articles")
for idx in indexes:
    if idx.index_type == IndexType.FULLTEXT:
        print(f"全文索引: {idx.name}")
```

## 版本兼容性

不同 ClickHouse 版本的内省行为差异：

| 功能 | ClickHouse 5.7 | ClickHouse 8.0+ |
|------|-----------|------------|
| `information_schema` | 完整支持 | 完整支持 |
| 不可见列 | 不支持 | 支持 |
| 隐藏主键 | 不支持 | 支持 |
| JSON 表达式提取 | 有限支持 | 完整支持 |

## 最佳实践

### 1. 使用缓存

内省操作涉及复杂的 `information_schema` 查询，建议利用缓存：

```python
# 首次查询会缓存结果
tables = backend.introspector.list_tables()

# 后续查询直接从缓存返回
tables_again = backend.introspector.list_tables()

# 只有在表结构变更后才需要清除缓存
backend.introspector.invalidate_cache(scope=IntrospectionScope.TABLE, name="users")
```

### 2. 使用 SHOW 命令获取详细信息

当需要完整的建表语句时，使用 `SHOW CREATE TABLE`：

```python
# 获取完整建表语句（包含所有选项）
create_table = backend.introspector.show.show_create_table("users")
print(create_table.create_statement)
```

### 3. 批量操作

尽可能使用批量查询方法：

```python
# 好：一次查询获取所有列
columns = backend.introspector.list_columns("users")

# 避免：多次查询单列
for col_name in column_names:
    col = backend.introspector.get_column_info("users", col_name)  # 每次 I/O
```

## API 参考

### 核心方法

| 方法 | 说明 | 参数 |
|------|------|------|
| `get_database_info()` | 获取数据库信息 | 无 |
| `list_tables()` | 列出表 | `include_system`, `table_type`, `schema` |
| `get_table_info(name)` | 获取表详情 | `name`, `schema` |
| `table_exists(name)` | 检查表存在 | `name`, `schema` |
| `list_columns(table_name)` | 列出列 | `table_name`, `schema` |
| `get_column_info(table_name, column_name)` | 获取列详情 | `table_name`, `column_name`, `schema` |
| `get_primary_key(table_name)` | 获取主键 | `table_name`, `schema` |
| `list_indexes(table_name)` | 列出索引 | `table_name`, `schema` |
| `list_foreign_keys(table_name)` | 列出外键 | `table_name`, `schema` |
| `list_views()` | 列出视图 | `schema` |
| `get_view_info(name)` | 获取视图详情 | `name`, `schema` |
| `list_triggers(table_name)` | 列出触发器 | `table_name`, `schema` |
| `clear_cache()` | 清除缓存 | 无 |
| `invalidate_cache(scope, ...)` | 使缓存失效 | `scope`, `name`, `table_name` |

### SHOW 命令方法

| 方法 | 说明 |
|------|------|
| `show_create_table(table_name)` | 获取建表语句 |
| `show_create_view(view_name)` | 获取建视图语句 |
| `show_columns(table_name)` | 显示列信息 |
| `show_index(table_name)` | 显示索引信息 |
| `show_tables()` | 显示表列表 |
| `show_databases()` | 显示数据库列表 |
| `show_table_status(table_name)` | 显示表状态 |
| `show_triggers(table_name)` | 显示触发器 |
| `show_variables(pattern)` | 显示系统变量 |
| `show_status(pattern)` | 显示状态变量 |
| `show_processlist()` | 显示进程列表 |
| `show_engines()` | 显示存储引擎 |
| `show_charset()` | 显示字符集 |
| `show_collation(pattern)` | 显示排序规则 |

## 命令行内省命令

ClickHouse 后端提供命令行内省命令，无需编写代码即可查询数据库元数据。

### 基本用法

```bash
# 列出所有表
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --host localhost --port 3306 --database mydb --user root --password

# 列出所有视图
python -m rhosocial.activerecord.backend.impl.clickhouse introspect views \
  --database mydb --user root

# 获取数据库信息
python -m rhosocial.activerecord.backend.impl.clickhouse introspect database \
  --database mydb --user root

# 包含系统表
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --include-system
```

### 连接参数

支持通过命令行参数或环境变量配置连接：

| 参数 | 环境变量 | 说明 |
|------|----------|------|
| `--host` | `CLICKHOUSE_HOST` | 数据库主机（默认 localhost） |
| `--port` | `CLICKHOUSE_PORT` | 数据库端口（默认 3306） |
| `--database` | `CLICKHOUSE_DATABASE` | 数据库名称（必需） |
| `--user` | `CLICKHOUSE_USER` | 用户名（默认 root） |
| `--password` | `CLICKHOUSE_PASSWORD` | 密码 |
| `--charset` | `CLICKHOUSE_CHARSET` | 字符集（默认 utf8mb4） |

### 查询表详情

```bash
# 获取表的完整信息（列、索引、外键）
python -m rhosocial.activerecord.backend.impl.clickhouse introspect table users \
  --database mydb --user root

# 仅查询列信息
python -m rhosocial.activerecord.backend.impl.clickhouse introspect columns users \
  --database mydb --user root

# 仅查询索引信息
python -m rhosocial.activerecord.backend.impl.clickhouse introspect indexes users \
  --database mydb --user root

# 仅查询外键信息
python -m rhosocial.activerecord.backend.impl.clickhouse introspect foreign-keys posts \
  --database mydb --user root

# 查询触发器
python -m rhosocial.activerecord.backend.impl.clickhouse introspect triggers \
  --database mydb --user root

# 查询特定表的触发器
python -m rhosocial.activerecord.backend.impl.clickhouse introspect triggers users \
  --database mydb --user root
```

### 内省类型

| 类型 | 说明 | 是否需要表名 |
|------|------|-------------|
| `tables` | 列出所有表 | 否 |
| `views` | 列出所有视图 | 否 |
| `database` | 数据库信息 | 否 |
| `table` | 表完整详情（列、索引、外键） | 是 |
| `columns` | 列信息 | 是 |
| `indexes` | 索引信息 | 是 |
| `foreign-keys` | 外键信息 | 是 |
| `triggers` | 触发器信息 | 可选 |

### 输出格式

```bash
# 表格格式（默认，需要 rich 库）
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root

# JSON 格式
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --output json

# CSV 格式
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --output csv

# TSV 格式
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --output tsv
```

### 使用异步后端

```bash
# 使用 --use-async 参数启用异步模式
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --use-async
```

### 环境变量配置

可以在环境中设置连接参数，简化命令行调用：

```bash
# 设置环境变量
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=3306
export CLICKHOUSE_DATABASE=mydb
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=secret

# 直接使用命令
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables
```
