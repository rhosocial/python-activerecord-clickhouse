# tests/.../feature/backend/adapters/

Type-adapter and column-mapping tests for the ClickHouse backend.

- `test_adapters_table_mixins.py` — core type adapters (BLOB, JSON, UUID,
  Boolean, Decimal, date/time, Vector, Enum) and the table mixins
  (`validate_data_type`, table-engine metadata helpers). Pure unit tests.
- `test_column_mapping.py` — end-to-end column mapping through the backend:
  INSERT/FETCH round-trips with combined adapters. **Requires a live
  ClickHouse server** (skipped/erroring when unreachable).
