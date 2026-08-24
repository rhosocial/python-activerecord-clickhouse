# Nullable & optional fields

ClickHouse differs from traditional OLTP databases in NULL handling;
understanding this prevents data from being silently rewritten.

## Optional fields map to `Nullable(T)`

An `Optional[T]` field on the model maps to a ClickHouse `Nullable(T)` column:

```python
class User(ActiveRecord):
    age: Optional[int] = None      # -> Nullable(Int32)
    bio: Optional[str] = None      # -> Nullable(String)
```

Corresponding DDL:

```sql
CREATE TABLE users (
    age Nullable(Int32),
    bio Nullable(String)
) ENGINE = MergeTree ORDER BY ...
```

## ⚠️ Writing NULL into a non-Nullable column yields an empty value

This is ClickHouse semantics, **not** a backend bug: writing `None` into a
non-`Nullable` `String` column stores the empty string `''`; writing `None` into
a non-`Nullable` numeric column stores `0`.

```python
class User(ActiveRecord):
    username: str          # not Optional -> String (non-Nullable)

User(username=None).save()   # ClickHouse stores '' — no error!
```

If you need to distinguish "empty" from "not provided", you must declare the
column `Nullable` (i.e. use `Optional` on the model field).

## Why sorting-key columns should not be Nullable

`ORDER BY` sorting-key columns **should not** use `Nullable(T)`:

- `Nullable` columns sort NULLs to a specific position, behaving unexpectedly;
- `Nullable` slows MergeTree merges;
- sorting keys are non-updatable by nature; PK columns should be non-null stable values.

Modeling advice: make the primary key (`id`) and sorting-key columns non-null
`Int64`/`String`; only make secondary data columns `Nullable`.

## `LowCardinality(T)` vs `Nullable(T)`

For enum-style low-cardinality strings (status codes, categories), prefer
`LowCardinality(String)` over `Nullable(String)`:

- `LowCardinality` deduplicates storage and queries faster;
- don't add `Nullable` when you don't need the "not provided" semantic;
- the two can stack: `LowCardinality(Nullable(String))`, but usually unnecessary.

## The difference between defaults and `Optional`

Pydantic's `Field(default=...)` and `Optional` are orthogonal:

```python
class User(ActiveRecord):
    age: Optional[int] = None          # column Nullable(Int32), default NULL
    score: int = 0                     # column Int32, default 0 (non-NULL)
    status: str = "active"             # column String, default 'active'
```

`Optional` decides whether the column is `Nullable`; `default` decides the value
written when not provided.

## Next steps

- [Field type mapping](field_types.md)
- [Mutations (UPDATE/DELETE)](../capabilities/mutations.md)
