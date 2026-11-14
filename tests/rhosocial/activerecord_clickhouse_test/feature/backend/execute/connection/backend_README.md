# tests/.../feature/backend/backend/

Backend-object behavior tests (connection lifecycle, CRUD execution,
dialect attachment) against a real ClickHouse server.

- `test_backend_ops.py` — `execute`/`execute_many`, ping/reconnect,
  fetch-all/one, invalid-SQL error mapping, server-version reporting,
  `ClickHouseConnectionConfig` defaults. The config-only cases run without a
  server; the rest **require a live ClickHouse**.

Note: CRUD execution moved to `../dml/test_crud_backend.py`; dialect-on-live-
backend tests moved to `../dialect/test_dialect.py`.
