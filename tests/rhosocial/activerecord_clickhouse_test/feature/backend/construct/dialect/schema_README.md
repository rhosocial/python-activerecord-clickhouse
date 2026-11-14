# tests/.../feature/backend/schema/

Name-space capability tests (pure expression-level).

- `test_schema_support.py` — the namespace switches on ClickHouseDialect:
  `supports_catalog()` and `supports_catalog_qualification()` are True (the
  database is real and is rendered), and `supports_schema_qualification()` is
  False, so a name carrying an inner schema is reported instead of being
  rendered as a namespace ClickHouse does not have.