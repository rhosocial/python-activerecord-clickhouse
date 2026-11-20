# Chapter 4 — Modeling

[`models.py`](models.py) defines two models and runs a small CRUD flow against
the declared tables.

What the script demonstrates:

- **`UseSqlType`** attaches ClickHouse-native `DataType` instances to fields
  through `Annotated`, e.g. `ClickHouseStringType()`, `ClickHouseInt64Type()`,
  `ClickHouseArrayType(element_type=ClickHouseStringType())`. The declaration
  states the column type instead of leaving it to inference.
- **Mixins**: a plain `IdentifiedMixin` adds shared behaviour (an `identity`
  property) with no persisted fields, while a local `ContentMixin` (itself an
  `ActiveRecord` subclass) contributes the `title`/`body` fields and a derived
  `summary` property.
- **`table_name()`**: each model declares the table it maps to as a class
  method.
- **`FieldProxy`**: `c: ClassVar[FieldProxy] = FieldProxy()` enables typed
  conditions such as `User.c.username == "alice"`.
- **Client-side IDs**: `id` is `Optional[int]` and backfilled with a generated
  `Int64` on `save()` — ClickHouse has no auto-increment.

The DDL in `create_tables()` mirrors the declared column types. A column holding
an optional value would be declared `Nullable(T)`; the fields here are all
required (with defaults), so their columns are plain types.

Related docs: [Field type mapping](../../en_US/modeling/field_types.md),
[Nullable & optional fields](../../en_US/modeling/nullable.md),
[Client-side snowflake IDs](../../en_US/capabilities/snowflake_ids.md).
