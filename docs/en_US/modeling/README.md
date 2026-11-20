# Modeling

This section covers defining ActiveRecord models on the ClickHouse backend.

- [Field type mapping](field_types.md): Python types ↔ ClickHouse column types
- [Nullable & optional fields](nullable.md): Optional model fields map to `Nullable(T)`

Runnable example:
[Chapter 4 — Modeling](../../examples/chapter_04_modeling/README.md) —
declarative models using `UseSqlType` with ClickHouse-native types, mixins, a
`table_name()` class method and `FieldProxy`.
