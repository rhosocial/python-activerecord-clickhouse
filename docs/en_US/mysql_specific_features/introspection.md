# Database Introspection

The ClickHouse backend provides complete database introspection capabilities using `information_schema` system tables and `SHOW` commands for querying database structure metadata.

## Overview

The ClickHouse introspection system is accessible via `backend.introspector` and provides:

- **Database Information**: Name, version, character set, collation
- **Table Information**: Table list, table details, storage engine, table comments
- **Column Information**: Column name, data type, nullability, default value, character set
- **Index Information**: Index name, columns, uniqueness, index type (BTREE, FULLTEXT, etc.)
- **Foreign Key Information**: Referenced table, column mapping, update/delete actions
- **View Information**: View definition SQL
- **Trigger Information**: Trigger event, execution timing

## Basic Usage

### Accessing the Introspector

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

# Access via introspector attribute
introspector = backend.introspector
```

### Getting Database Information

```python
# Get basic database information
db_info = backend.introspector.get_database_info()
print(f"Database name: {db_info.name}")
print(f"Version: {db_info.version}")
print(f"Character set: {db_info.encoding}")
print(f"Collation: {db_info.collation}")
```

### Listing Tables

```python
# List all user tables
tables = backend.introspector.list_tables()
for table in tables:
    print(f"Table: {table.name}, Type: {table.table_type.value}")
    if table.comment:
        print(f"  Comment: {table.comment}")

# Include system database tables (usually not needed)
all_tables = backend.introspector.list_tables(include_system=True)

# Filter by specific type
base_tables = backend.introspector.list_tables(table_type="BASE TABLE")
views = backend.introspector.list_tables(table_type="VIEW")

# Check if table exists
if backend.introspector.table_exists("users"):
    print("users table exists")

# Get table details
table_info = backend.introspector.get_table_info("users")
if table_info:
    print(f"Table name: {table_info.name}")
    print(f"Storage engine: {table_info.extra.get('engine', 'InnoDB')}")
```

### Querying Column Information

```python
# List all columns of a table
columns = backend.introspector.list_columns("users")
for col in columns:
    nullable = "NOT NULL" if col.nullable.value == "NOT_NULL" else "NULLABLE"
    pk = " [PK]" if col.is_primary_key else ""
    charset = f" ({col.character_set})" if col.character_set else ""
    print(f"{col.name}: {col.data_type}{charset} {nullable}{pk}")
    if col.comment:
        print(f"  Comment: {col.comment}")

# Get primary key information
pk = backend.introspector.get_primary_key("users")
if pk:
    print(f"Primary key: {[c.name for c in pk.columns]}")

# Get single column information
col_info = backend.introspector.get_column_info("users", "email")
```

### Querying Indexes

```python
# List all indexes of a table
indexes = backend.introspector.list_indexes("users")
for idx in indexes:
    idx_type = idx.index_type.value if idx.index_type else "BTREE"
    unique = "UNIQUE " if idx.is_unique else ""
    print(f"{unique}Index: {idx.name} ({idx_type})")
    for col in idx.columns:
        print(f"  - {col.name}")
```

### Querying Foreign Keys

```python
# List foreign keys of a table
foreign_keys = backend.introspector.list_foreign_keys("posts")
for fk in foreign_keys:
    print(f"FK: {fk.name}")
    print(f"  Columns: {fk.columns} -> {fk.referenced_table}.{fk.referenced_columns}")
    print(f"  ON DELETE: {fk.on_delete.value}")
    print(f"  ON UPDATE: {fk.on_update.value}")
```

### Querying Views

```python
# List all views
views = backend.introspector.list_views()
for view in views:
    print(f"View: {view.name}")

# Get view details
view_info = backend.introspector.get_view_info("user_posts_summary")
if view_info:
    print(f"Definition: {view_info.definition}")
```

### Querying Triggers

```python
# List all triggers
triggers = backend.introspector.list_triggers()
for trigger in triggers:
    print(f"Trigger: {trigger.name} on {trigger.table_name}")

# List triggers for a specific table
table_triggers = backend.introspector.list_triggers("users")
```

## ClickHouse-Specific: ShowIntrospector

ClickHouse provides unique `SHOW` command support, accessible via `backend.introspector.show`:

```python
# Access ShowIntrospector
show = backend.introspector.show

# SHOW CREATE TABLE
create_table = show.show_create_table("users")
print(f"Create statement:\n{create_table.create_statement}")

# SHOW CREATE VIEW
create_view = show.show_create_view("user_posts_summary")
print(f"Create view statement:\n{create_view.create_statement}")

# SHOW COLUMNS
columns = show.show_columns("users")
for col in columns:
    print(f"{col.field}: {col.type} {col.null} {col.key} {col.default}")

# SHOW INDEX
indexes = show.show_index("users")
for idx in indexes:
    print(f"Index: {idx.index_name}, Column: {idx.column_name}")

# SHOW TABLE STATUS
table_status = show.show_table_status("users")
print(f"Engine: {table_status.engine}")
print(f"Rows: {table_status.rows}")
print(f"Auto increment: {table_status.auto_increment}")

# SHOW TABLES
tables = show.show_tables()
for table in tables:
    print(f"Table: {table}")

# SHOW DATABASES
databases = show.show_databases()
for db in databases:
    print(f"Database: {db}")

# SHOW TRIGGERS
triggers = show.show_triggers("users")
for trigger in triggers:
    print(f"Trigger: {trigger.trigger}, Event: {trigger.event}")

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
    print(f"ID: {proc.id}, User: {proc.user}, State: {proc.state}")

# SHOW ENGINES
engines = show.show_engines()
for engine in engines:
    supported = "supported" if engine.support == "YES" else "not supported"
    print(f"{engine.engine}: {supported}")

# SHOW CHARSET
charsets = show.show_charset()
for charset in charsets:
    print(f"{charset.charset}: {charset.description}")

# SHOW COLLATION
collations = show.show_collation("utf8mb4")
for collation in collations:
    print(f"{collation.collation}: {collation.charset}")
```

## Async API

The async backend provides identical introspection methods with the same names as the sync version:

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

# Async introspection methods (same names as sync version)
db_info = await backend.introspector.get_database_info()
tables = await backend.introspector.list_tables()
columns = await backend.introspector.list_columns("users")

# Async SHOW commands
create_table = await backend.introspector.show.show_create_table("users")
```

## Cache Management

Introspection results are cached by default for performance:

```python
# Clear all introspection cache
backend.introspector.clear_cache()

# Invalidate specific scope
from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

# Invalidate all table-related cache
backend.introspector.invalidate_cache(scope=IntrospectionScope.TABLE)

# Invalidate cache for a specific table
backend.introspector.invalidate_cache(
    scope=IntrospectionScope.TABLE,
    name="users"
)
```

## ClickHouse-Specific Behaviors

### System Databases

ClickHouse excludes the following system databases by default:

- `information_schema` — Metadata information
- `performance_schema` — Performance monitoring
- `clickhouse` — System users and permissions
- `sys` — System views and stored procedures

To include these databases, use `include_system=True` parameter.

### Storage Engine Information

The `extra` field in table information contains ClickHouse-specific details:

```python
table_info = backend.introspector.get_table_info("users")
print(f"Storage engine: {table_info.extra.get('engine')}")
print(f"Auto increment: {table_info.extra.get('auto_increment')}")
print(f"Create time: {table_info.extra.get('create_time')}")
print(f"Update time: {table_info.extra.get('update_time')}")
```

### Character Set and Collation

ClickHouse column information includes character set and collation:

```python
columns = backend.introspector.list_columns("users")
for col in columns:
    if col.character_set:
        print(f"{col.name}: charset={col.character_set}, collation={col.collation}")
```

### Index Types

ClickHouse supports multiple index types:

| Index Type | Description |
|------------|-------------|
| `BTREE` | Default index type |
| `HASH` | Memory engine only |
| `FULLTEXT` | Full-text index |
| `RTREE` | Spatial index |
| `SPATIAL` | Spatial index (alias) |

```python
indexes = backend.introspector.list_indexes("articles")
for idx in indexes:
    if idx.index_type == IndexType.FULLTEXT:
        print(f"Full-text index: {idx.name}")
```

## Version Compatibility

Introspection behavior differences across ClickHouse versions:

| Feature | ClickHouse 5.7 | ClickHouse 8.0+ |
|---------|-----------|------------|
| `information_schema` | Full support | Full support |
| Invisible columns | Not supported | Supported |
| Hidden primary key | Not supported | Supported |
| JSON expression extraction | Limited support | Full support |

## Best Practices

### 1. Use Caching

Introspection operations involve complex `information_schema` queries. Leverage caching:

```python
# First query caches the result
tables = backend.introspector.list_tables()

# Subsequent queries return from cache
tables_again = backend.introspector.list_tables()

# Only clear cache when table structure changes
backend.introspector.invalidate_cache(scope=IntrospectionScope.TABLE, name="users")
```

### 2. Use SHOW Commands for Detailed Information

When you need the complete CREATE TABLE statement, use `SHOW CREATE TABLE`:

```python
# Get complete CREATE TABLE statement (including all options)
create_table = backend.introspector.show.show_create_table("users")
print(create_table.create_statement)
```

### 3. Batch Operations

Prefer batch query methods when possible:

```python
# Good: One query for all columns
columns = backend.introspector.list_columns("users")

# Avoid: Multiple single-column queries
for col_name in column_names:
    col = backend.introspector.get_column_info("users", col_name)  # I/O each time
```

## API Reference

### Core Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `get_database_info()` | Get database information | None |
| `list_tables()` | List tables | `include_system`, `table_type`, `schema` |
| `get_table_info(name)` | Get table details | `name`, `schema` |
| `table_exists(name)` | Check table exists | `name`, `schema` |
| `list_columns(table_name)` | List columns | `table_name`, `schema` |
| `get_column_info(table_name, column_name)` | Get column details | `table_name`, `column_name`, `schema` |
| `get_primary_key(table_name)` | Get primary key | `table_name`, `schema` |
| `list_indexes(table_name)` | List indexes | `table_name`, `schema` |
| `list_foreign_keys(table_name)` | List foreign keys | `table_name`, `schema` |
| `list_views()` | List views | `schema` |
| `get_view_info(name)` | Get view details | `name`, `schema` |
| `list_triggers(table_name)` | List triggers | `table_name`, `schema` |
| `clear_cache()` | Clear cache | None |
| `invalidate_cache(scope, ...)` | Invalidate cache | `scope`, `name`, `table_name` |

### SHOW Command Methods

| Method | Description |
|--------|-------------|
| `show_create_table(table_name)` | Get CREATE TABLE statement |
| `show_create_view(view_name)` | Get CREATE VIEW statement |
| `show_columns(table_name)` | Show column information |
| `show_index(table_name)` | Show index information |
| `show_tables()` | Show table list |
| `show_databases()` | Show database list |
| `show_table_status(table_name)` | Show table status |
| `show_triggers(table_name)` | Show triggers |
| `show_variables(pattern)` | Show system variables |
| `show_status(pattern)` | Show status variables |
| `show_processlist()` | Show process list |
| `show_engines()` | Show storage engines |
| `show_charset()` | Show character sets |
| `show_collation(pattern)` | Show collations |

## Command Line Introspection

The ClickHouse backend provides command-line introspection commands to query database metadata without writing code.

### Basic Usage

```bash
# List all tables
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --host localhost --port 3306 --database mydb --user root --password

# List all views
python -m rhosocial.activerecord.backend.impl.clickhouse introspect views \
  --database mydb --user root

# Get database information
python -m rhosocial.activerecord.backend.impl.clickhouse introspect database \
  --database mydb --user root

# Include system tables
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --include-system
```

### Connection Parameters

Supports configuration via command-line arguments or environment variables:

| Parameter | Environment Variable | Description |
|-----------|---------------------|-------------|
| `--host` | `CLICKHOUSE_HOST` | Database host (default: localhost) |
| `--port` | `CLICKHOUSE_PORT` | Database port (default: 3306) |
| `--database` | `CLICKHOUSE_DATABASE` | Database name (required) |
| `--user` | `CLICKHOUSE_USER` | Username (default: root) |
| `--password` | `CLICKHOUSE_PASSWORD` | Password |
| `--charset` | `CLICKHOUSE_CHARSET` | Character set (default: utf8mb4) |

### Querying Table Details

```bash
# Get complete table info (columns, indexes, foreign keys)
python -m rhosocial.activerecord.backend.impl.clickhouse introspect table users \
  --database mydb --user root

# Query only column information
python -m rhosocial.activerecord.backend.impl.clickhouse introspect columns users \
  --database mydb --user root

# Query only index information
python -m rhosocial.activerecord.backend.impl.clickhouse introspect indexes users \
  --database mydb --user root

# Query only foreign key information
python -m rhosocial.activerecord.backend.impl.clickhouse introspect foreign-keys posts \
  --database mydb --user root

# Query triggers
python -m rhosocial.activerecord.backend.impl.clickhouse introspect triggers \
  --database mydb --user root

# Query triggers for a specific table
python -m rhosocial.activerecord.backend.impl.clickhouse introspect triggers users \
  --database mydb --user root
```

### Introspection Types

| Type | Description | Table Name Required |
|------|-------------|---------------------|
| `tables` | List all tables | No |
| `views` | List all views | No |
| `database` | Database information | No |
| `table` | Complete table details (columns, indexes, foreign keys) | Yes |
| `columns` | Column information | Yes |
| `indexes` | Index information | Yes |
| `foreign-keys` | Foreign key information | Yes |
| `triggers` | Trigger information | Optional |

### Output Formats

```bash
# Table format (default, requires rich library)
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root

# JSON format
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --output json

# CSV format
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --output csv

# TSV format
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --output tsv
```

### Using Async Backend

```bash
# Use --use-async flag to enable async mode
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables \
  --database mydb --user root --use-async
```

### Environment Variable Configuration

You can set connection parameters in the environment to simplify command-line calls:

```bash
# Set environment variables
export CLICKHOUSE_HOST=localhost
export CLICKHOUSE_PORT=3306
export CLICKHOUSE_DATABASE=mydb
export CLICKHOUSE_USER=root
export CLICKHOUSE_PASSWORD=secret

# Use command directly
python -m rhosocial.activerecord.backend.impl.clickhouse introspect tables
```
