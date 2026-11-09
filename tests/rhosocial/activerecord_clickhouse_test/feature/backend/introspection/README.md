# tests/.../feature/backend/introspection/

Schema introspection, both offline and against a real ClickHouse server.

- `test_introspection.py` — list_tables, get_table_info (ClickHouse column
  metadata, native data types), list_columns, fail-fast foreign-key
  introspection, nonexistent-table handling, introspection capability
  flags. **Requires a live ClickHouse**.
- `test_catalog_families.py` — the six server-wide catalogue families:
  statement rendering, name filters, parser normalisation and capability
  switches. **Offline**.
- `test_introspection_query_nodes.py`, `test_introspection_parsing.py` —
  offline format and parser checks for the table-scoped families.
