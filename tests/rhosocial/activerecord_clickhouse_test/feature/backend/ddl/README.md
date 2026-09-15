# tests/.../feature/backend/ddl/

DDL statement and expression-level tests (no live server needed).

- `test_create_table_expression_diff.py` — `CreateTableExpression.diff()`
  for the ClickHouse dialect: hook overrides (`MODIFY COLUMN` type changes,
  property/index/constraint changes → rebuild), DiffPlan/RebuildPlan shapes,
  rendered SQL, and regressions for the pre-override behaviors.
- `test_create_table_like.py` — ClickHouse structure copy via
  `CreateTableLikeExpression` rendered as `CREATE TABLE ... AS <source>`
  (ClickHouse has no `LIKE` keyword): IF NOT EXISTS / TEMPORARY combinations,
  schema-qualified sources, and the explicit-schema form.
- `test_ddl_generation.py` — `format_create_table_statement` output: type
  mapping to native ClickHouse types (Int32, String, Decimal, DateTime,
  Bool), ENGINE/ORDER BY/PARTITION BY storage clauses, inline skip-index
  rendering.
- `test_ddl_coverage.py` — rename-table (single/multi, empty raises) and
  TRUNCATE TABLE rendering with unsupported qualifier flags.
