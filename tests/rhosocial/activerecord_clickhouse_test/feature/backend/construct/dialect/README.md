# tests/.../feature/backend/dialect/

ClickHouseDialect capability and formatting tests (pure expression-level,
no live server needed).

- `test_dialect.py` — dialect formatting on a live backend: identifier
  quoting and parameter placeholder as exposed by the connected backend's
  dialect. **Requires a live ClickHouse** (async variants skip: no async
  ClickHouse backend).
- `test_dialect_capabilities.py` — capability switches: arrays, JSON, CTE,
  window functions, grouping sets, set operations, joins, views, RETURNING
  (insert-only), transactions/constraints/upsert unsupported.
- `test_dialect_security.py` — SQL-injection hardening: identifier escaping,
  JSON_TABLE path validation, string escaping in DDL contexts.
- `test_mixins_coverage.py` — MODIFY/CHANGE COLUMN mixin rendering
  (AFTER/FIRST variants), partition capability stubs, EXPLAIN result models.
- `test_unsupported_features.py` — stubbed feature families (triggers,
  spatial, vector, optimizer hints, …) must raise `UnsupportedFeatureError`
  rather than render silently-wrong SQL.
