# tests/.../feature/backend/ddl/

DDL statement and expression-level tests (no live server needed).

- `test_create_table_expression_diff.py` — `CreateTableExpression.diff()`
  for the ClickHouse dialect: hook overrides (`MODIFY COLUMN` type changes,
  property/index/constraint changes → rebuild), DiffPlan/RebuildPlan shapes,
  rendered SQL, and regressions for the pre-override behaviors.
- `test_create_table_like.py` — ClickHouse `CREATE TABLE ... LIKE` syntax:
  IF NOT EXISTS / TEMPORARY combinations, schema-qualified sources,
  fallback when `like_table` is absent.
- `test_ddl_generation.py` — `format_create_table_statement` output: type
  mapping to native ClickHouse types (Int32, String, Decimal, DateTime,
  Bool), ENGINE/ORDER BY/PARTITION BY storage clauses, inline skip-index
  rendering.
- `test_ddl_coverage.py` — rename-table (single/multi, empty raises) and
  TRUNCATE TABLE rendering with unsupported qualifier flags.
