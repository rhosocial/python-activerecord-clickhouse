# docs/en_US/clickhouse_specific_features/schema_namespace.md

# Schema names in the ClickHouse backend

> ClickHouse has no schema layer. `schema_name` is still accepted, and on this
> backend it names a **database**. This page leads with that because it is the
> one point where a reader's assumption about "schema" is most likely to be
> wrong.

## What `schema_name` means here

`supports_schema()` returns `True` and the value is usable — but there is no
schema layer underneath it. The ClickHouse dialect implements the core
`SchemaSupport` protocol, and every one of the schema DDL flags on it is
`False`:

| Capability | Value |
|---|---|
| `supports_schema()` | `True` |
| `supports_create_schema()` | `False` |
| `supports_drop_schema()` | `False` |
| `supports_schema_if_not_exists()` | `False` |
| `supports_schema_if_exists()` | `False` |

Those two groups answer different questions, which is why they can disagree.
`supports_schema()` asks whether a `schema_name` reaches the server as a
qualifier; the rest ask whether the dialect can *create* a namespace. On
ClickHouse the answer to the first is yes and to the second is no. Being able to
qualify a reference is not the same as being able to create a namespace to
qualify into.

| | PostgreSQL | ClickHouse |
|---|---|---|
| `supports_schema()` | `True` | `True` |
| `schema_name` names | a schema | a **database** |
| `CREATE SCHEMA` | works | **syntax error** |
| `SHOW SCHEMAS` | works | **syntax error** |
| current-namespace function | `current_schema()` | `currentDatabase()` |
| renders as | `"app"."orders"` | `` `app`.`orders` `` |

`` `db`.`orders` `` is how ClickHouse itself writes a qualified reference, so
`schema_name="app"` renders exactly that and the server accepts it.

MySQL and MariaDB arrive at the same place by a different route. They keep the
word "schema" in the language and use it as a synonym for `database`, so
`CREATE SCHEMA` and `SHOW SCHEMAS` both work there and both operate on
databases. ClickHouse dropped the synonym and kept the concept, which is why the
same `schema_name` value produces the same SQL on all three but a different
answer to "what is this called". The core guide's support matrix records the
MySQL and MariaDB entries.

## Declaring the database on a model

`__schema_name__` carries the database name. `__table_name__` and
`__schema_name__` are separate attributes, and folding them together does not
work — the identifier would be quoted as a single name containing a dot.

```python
from typing import ClassVar, Optional
from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.model import ActiveRecord

class Order(ActiveRecord):
    __table_name__ = "orders"
    __schema_name__ = "app"        # this is the database
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
```

```sql
-- generated
SELECT `orders`.`id` FROM `app`.`orders`
```

Leave `__schema_name__` unset and the table renders unqualified, which resolves
against the session's current database:

```sql
SELECT `orders`.`id` FROM `orders`
```

Both renderings above, and every other SQL block on this page, were produced with
`ClickHouseDialect((26, 7, 0))` — `ClickHouseDialect((25, 8, 0))` and
`ClickHouseDialect((26, 3, 0))` for the version-dependent `UPDATE` below — running
against the core library on this branch:

```
PYTHONPATH=/mnt/i/GitHubRepositories/rhosocial/.worktrees/core-schema-name/src \
  .venv3.14-ubuntu26.04/bin/python
```

The column side of the same statement is covered under
[Column references](#column-references-carry-at-most-two-parts).

## DDL takes a `TableExpression` of its own

`__schema_name__` selects the namespace for DML. DDL statements do not read it,
and a statement whose target is a table takes a `TableExpression` rather than a
`schema_name` of its own. That is the general rule; the statements below are what
ClickHouse accepts for the DDL a schema-bound model needs.

Every table-targeted statement refuses a bare string at construction:

```
TypeError: table must be a TableExpression, got str
```

That covers `CreateTableExpression`, `DropTableExpression`,
`TruncateExpression`, `AlterTableExpression`, `CreateIndexExpression`,
`DropIndexExpression`, `CreateFulltextIndexExpression`,
`DropFulltextIndexExpression`, `CreateTriggerExpression` and
`DropTriggerExpression`. On none of them is `schema_name` what qualifies the
table — the `TableExpression` is. `CREATE TABLE`, `DROP TABLE`, `TRUNCATE` and
`ALTER TABLE` have no `schema_name` parameter at all; the index and trigger
statements keep one for the index or trigger *name*, and this backend does accept
a qualified index name, so there both the name and the table end up qualified.

Objects that are not tables at all — a view, a sequence, a type, a function, a
domain — also keep a `schema_name`; the database a statement creates or drops is
spelled `CREATE DATABASE` / `DROP DATABASE`, which take the name as a plain
string.

Create the database itself with `CREATE DATABASE`, which is rendered by
`CreateDatabaseExpression`. It is not re-exported from the expression package, so
import it from its module:

```python
from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    CreateDatabaseExpression,
)

CreateDatabaseExpression(dialect, "app").to_sql()[0]
# CREATE DATABASE `app`
```

`CREATE TABLE` takes a `TableExpression` for its target, and that is where the
database goes:

```python
from rhosocial.activerecord.backend.expression import (
    CreateTableExpression, TableExpression,
)

CreateTableExpression(
    dialect,
    TableExpression(dialect, "orders", schema_name="app"),
    columns,
).to_sql()[0]
# CREATE TABLE `app`.`orders` (`id` Int32 PRIMARY KEY)
```

`TRUNCATE` takes the same keyword on
`rhosocial.activerecord.backend.expression.statements.ddl_truncate.TruncateExpression`:

```python
TruncateExpression(dialect, TableExpression(dialect, "orders", schema_name="app")).to_sql()[0]
# TRUNCATE TABLE `app`.`orders`
```

The model-level factories read `schema_name()` for you, so a model with
`__schema_name__ = "app"` produces the same qualified names:

```python
Order.build_create_table_statement(dialect, columns).to_sql()[0]
Order.build_truncate_statement(dialect).to_sql()[0]
Order.build_drop_table_statement(dialect, if_exists=True).to_sql()[0]
# CREATE TABLE `app`.`orders` (...) / TRUNCATE TABLE `app`.`orders`
# / DROP TABLE IF EXISTS `app`.`orders`
```

The index factory is the one that needs no workaround here, which is the opposite
of MySQL and MariaDB. `build_create_index_statement()` defaults the index's
namespace to the model's, and `None` means "inherit the model's" rather than
"unqualified"; because ClickHouse accepts a qualified index name
(`supports_index_schema_qualification()` is `True`), the index ends up qualified
along with the table:

```python
Order.build_create_index_statement(dialect, "idx_orders_id", ["id"]).to_sql()[0]
# CREATE INDEX `app`.`idx_orders_id` ON `app`.`orders` (`id`)
```

A model whose `__schema_name__` is `app` and a migration creating an
unqualified `orders` still do not agree automatically. The migration has to name
the database it means.

## Column references carry at most two parts

A table reference on this backend is `database.table`. A column reference is at
most `table.column`, so the database never appears a second time:

```sql
SELECT `orders`.`id` FROM `app`.`orders`
```

`format_column` drops `schema_name` — not because it rejects the value, but
because a three-part `database.table.column` reference is not a form this dialect
produces. A `Column` built with both a table and a schema renders the two-part
form:

```python
dialect.format_column(Column(dialect, "id", table="orders", schema_name="app"))
# ('`orders`.`id`', ())
```

A bare column with a schema and no table is the one case that warns rather than
renders, because a column reference needs a table to be qualified at all:

```
UserWarning: ClickHouse: dropping schema_name='app' from column 'id' because no
table was given; a column reference needs a table to be qualified
```

Once an alias is in effect the alias identifies the range, exactly as on the
other backends:

```sql
SELECT `o`.`id` FROM `app`.`orders` AS `o`
```

## Joins, set operations and CTEs

Each side of a join qualifies its own database, so one statement may span two:

```sql
SELECT `orders`.`id` FROM `shop`.`orders` JOIN `crm`.`users` ON `orders`.`user_id` = `users`.`id`
```

A set operation combines queries rather than naming an object, so each branch
keeps its own database and nothing else changes:

```sql
SELECT `id` FROM `shop`.`orders` UNION DISTINCT SELECT `id` FROM `crm`.`customers`
```

A CTE is named for the rest of the query, so its name stays bare while the query
inside it is qualified:

```sql
WITH `recent` AS (SELECT `id` FROM `shop`.`orders`)
SELECT `recent`.`id` FROM `recent`
```

## UPDATE filters are version-dependent

Getting this wrong is easy on this backend, because the correct SQL changes with
the server version.

A ClickHouse `UPDATE` is a mutation. The server rewrites it into
`_CAST(if(<filter>, <new value>, <old value>), <type>)` and evaluates that
expression against the columns of the part being mutated. On the maintained
lines below 26.7 — 25.8 LTS and 26.3 LTS — that resolver had no notion of a
table qualifier: it read `tasks.id` as one identifier named `tasks.id`, found no
such column, and refused the statement:

```
Missing columns: 'tasks.id' while processing:
'_CAST(if(tasks.id = 381195967974322176, ...), 'Nullable(String)')
```

ClickHouse fixed it in 26.7 — PR #109491, closing
[ClickHouse/ClickHouse#71760](https://github.com/ClickHouse/ClickHouse/issues/71760).
`ClickHouseUpdateMixin` therefore gates on the version, with the boundary
recorded as a named constant:

```python
from rhosocial.activerecord.backend.impl.clickhouse.mixins.update import (
    ClickHouseUpdateMixin,
)

ClickHouseUpdateMixin.QUALIFIED_MUTATION_COLUMN_VERSION   # (26, 7, 0)
```

`supports_update_column_qualification()` reports which side of the boundary the
dialect is on:

| Server version | `supports_update_column_qualification()` | Filter rendered |
|---|---|---|
| 25.8 | `False` | bare |
| 26.3 | `False` | bare |
| 26.7 | `True` | qualified |

The version comes from `dialect.version`, which the backend sets from its
`version` argument or from `introspect_and_adapt()` reading `SELECT version()`.
A dialect that has not been adapted raises `DialectNotAdaptedException` from the
gate rather than guessing.

The same `WHERE` clause therefore renders two ways:

```sql
-- 25.8 and 26.3
UPDATE `app`.`tasks` SET `deleted_at` = %s WHERE `id` = %s

-- 26.7 and later
UPDATE `app`.`tasks` SET `deleted_at` = %s WHERE `tasks`.`id` = %s
```

Note what does not change. The target table keeps its database qualification on
every version, because that is what names the table being mutated. The `SET`
clause and the parameter list are identical. Only the filter's table qualifier
is dropped, and only below 26.7.

Three further points on the gate's scope:

- It applies to `UPDATE` and to nothing else. `ClickHouseUpdateMixin` overrides
  `format_update_statement` and no other formatter, so `DELETE` keeps the
  qualifier its columns carry on every version.
- It rewrites the filter, not the expression in place. The tree is walked and
  the `Column` nodes are replaced with equivalents that carry no table, so a
  `Column` shared with another predicate elsewhere keeps its qualifier there.
- Every predicate shape a filter can be built from is covered — comparisons,
  `LIKE`, `IN`, `BETWEEN`, `AND`/`OR`/`NOT`, unary and binary expressions, and
  columns nested inside function calls.

An `UPDATE` on a model therefore runs unmodified on every maintained line. If you
write a filter by hand against a specific version, check which side of 26.7 it
targets.

## Common mistakes

**`CREATE SCHEMA` does not exist.** Writing it in a migration fails at the
server with a syntax error; the dialect raises `UnsupportedFeatureError` before
the statement is ever sent. Create a database instead:

```sql
CREATE DATABASE app
```

The same applies to `DROP SCHEMA`. There is also no `ShowSchemasExpression` on
this backend — the equivalent listing is `SHOW DATABASES`, and the rest of the
introspection surface reads `system.*` tables.

**`currentSchema()` does not exist.** There is no function by that name. A
statement that calls it fails at the server, and the error text suggests
`currentSchemas`/`current_schemas`. That suggestion is not a drop-in
replacement: ClickHouse added `currentSchemas(bool)` as a PostgreSQL-compatibility
wrapper, and it returns an `Array(String)` holding the current database name
rather than a plain string. The function to use is `currentDatabase()`.

**`schema` is not a synonym here.** A migration written for MySQL or MariaDB
that uses `CREATE SCHEMA` or `SHOW SCHEMAS` does not port. Its DDL has to be
rewritten against `CREATE DATABASE` and `SHOW DATABASES`.

**A qualified `WHERE` in an `UPDATE` fails below 26.7.** Covered above; the
symptom is `Missing columns: '<table>.<column>'`.

**Passing a table name as a string to DDL.** `CREATE TABLE`, `DROP TABLE`,
`TRUNCATE`, `ALTER TABLE`, the index statements and the trigger statements take a
`TableExpression`, so a bare string is a `TypeError` at construction rather than a
silently unqualified name:

```
TruncateExpression(dialect, "orders")
# TypeError: table must be a TableExpression, got str
```

## Reading the current database

`get_current_schema()` returns the current database. The method name is the
shared cross-backend API; what it reads is a database. It builds a query
around the `currentDatabase` function through the `current_database(dialect)`
expression factory and takes the first column of the row:

```python
backend.get_current_schema()   # 'default'
```

The value follows the session, so it changes with the database the connection
was opened against — the `database` option of `ClickHouseConnectionConfig`,
which is handed to clickhouse-connect on connect. Unqualified references resolve
against it.

Only the synchronous backend is provided. clickhouse-connect is a synchronous-only
library, so there is no async variant to call this on.

## An empty `schema_name` is rejected at render time

`schema_name=""` does not mean "unqualified"; `None` means that. The check runs
while the statement is rendered, not while the expression is built, because an
expression only collects its parameters:

```python
TableExpression(dialect, "orders", schema_name="")   # constructed without error
QueryExpression(dialect, select=[Column(dialect, "id")], from_=[that_table]).to_sql()
# ValueError: TableExpression.schema_name must be a non-empty string;
#             use None for an unqualified reference
```

The renderer treats an empty string as absent, so accepting one would mean a
caller who asked for `app.orders` silently gets `orders`. That is the failure
this check exists to prevent, and it applies on every backend. The message names
the expression that carried the value, so a model's columns produce the `Column`
wording instead:

```
ValueError: Column.schema_name must be a non-empty string;
            use None for an unqualified reference
```

## When the database does not exist

Nothing here refuses a `schema_name`, because a database is a real namespace this
dialect can express. If you connect to a server where the named database does
not exist, the error comes from the server when the statement runs — not from
the framework when it is built. The value is validated for shape, not for
existence, and it is not compared against the connection's current database. A
`schema_name` naming a different database addresses a different table, or none.

## See also

- [Mutations (UPDATE/DELETE)](../../capabilities/mutations.md) — the rest of the
  UPDATE/DELETE surface, including the settings lightweight updates require
- [Unsupported features](../../capabilities/unsupported.md) — what this backend
  refuses outright, and how that differs from a value it accepts
- [Field type mapping](../modeling/field_types.md) and
  [Nullable & optional fields](../modeling/nullable.md) — the rest of the
  model-level material
- Core guide: `docs/modeling/schema_namespace.md` in the core library, for the
  cross-backend support matrix and the rules that hold on every backend
