# tests/.../feature/backend/introspection/

Schema introspection against a real ClickHouse server.

- `test_introspection.py` — list_tables, get_table_info (ClickHouse column
  metadata, native data types), list_columns, fail-fast foreign-key
  introspection, nonexistent-table handling, introspection capability
  flags. **Requires a live ClickHouse**.
