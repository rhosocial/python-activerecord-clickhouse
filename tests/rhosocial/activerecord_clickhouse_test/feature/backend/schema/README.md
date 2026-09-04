# tests/.../feature/backend/schema/

Database/schema catalog capability tests (pure expression-level).

- `test_schema_support.py` — `SchemaSupport` protocol declaration on
  ClickHouseDialect: CREATE/DROP DATABASE capability flags, schema DDL
  qualifiers, and the fact that named schemas inside a server are not
  addressable as PostgreSQL-style schemas.
