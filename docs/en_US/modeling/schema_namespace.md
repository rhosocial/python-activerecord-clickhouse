# Schema names in the ClickHouse backend

> ClickHouse has no schema namespace. A `schema_name` is still accepted, and it
> names a **database**. This page exists because that is the one point where a
> reader's assumption about "schema" is most likely to be wrong.

## What `schema_name` means here

`supports_schema()` returns `True`, and the value is usable — but there is no
schema layer underneath it.

| | PostgreSQL | ClickHouse |
|---|---|---|
| `supports_schema()` | `True` | `True` |
| `schema_name` names | a schema | a **database** |
| `CREATE SCHEMA` | works | **syntax error** |
| `SHOW SCHEMAS` | works | not a thing |
| current schema function | `current_schema()` | `currentDatabase()` |
| renders as | `"app"."orders"` | `` `app`.`orders` `` |

A qualified reference `` `db`.`orders` `` is how ClickHouse itself writes it, so
passing `schema_name="app"` produces exactly that and the server accepts it.

## Declaring one

```python
class Order(ActiveRecord):
    __schema_name__ = "app"   # this is the database
    __tablename__ = "orders"
```

```sql
-- generated
SELECT * FROM `app`.`orders`
```

## The two things that will bite you

**`CREATE SCHEMA` does not exist.** Writing a migration that creates a schema
fails at the server. Create a database instead:

```sql
CREATE DATABASE app
```

**`schema` is not a synonym for `database` here.** MySQL and MariaDB accept
`CREATE SCHEMA` as an alias for `CREATE DATABASE`; ClickHouse has no such alias.
So a migration written for MySQL does not port.

## Asking the server which database is current

`get_current_schema()` returns the current database. The name is the shared
API; the thing it reads is a database.

```python
backend.get_current_schema()   # 'default'
```

Only the synchronous backend is provided. clickhouse-connect is a
synchronous-only library, so there is no async variant to call this on.

## Columns are never schema-qualified

Even though a table reference takes two parts here, a column reference takes at
most two as well, so the schema part is not repeated:

```sql
SELECT `orders`.`id` FROM `app`.`orders`
```

The table is qualified, the column is not. This is the same rule MySQL follows,
and for the same reason: a three-part column reference is a syntax error.

## When a schema is supplied but cannot be used

Nothing here refuses a `schema_name`, because a database is a real namespace
this dialect can express. If you connect to a server where the named database
does not exist, the error comes from the server when the statement runs, not
from the framework when it is built.

## See also

- [Unsupported features](capabilities/unsupported.md) — what ClickHouse refuses
  outright, and how that differs from this case
- Core guide: `docs/modeling/schema_namespace.md` in the core library, for the
  cross-backend matrix
