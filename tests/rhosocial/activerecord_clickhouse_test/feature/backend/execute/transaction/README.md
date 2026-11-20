# tests/.../feature/backend/transactions/

Transaction semantics (ClickHouse has none — documented no-op behavior).

- `test_transaction_backend.py` — transaction context manager is a no-op,
  BEGIN/COMMIT/ROLLBACK raise, dialect reports
  `supports_transactions() == False`, and normal DML keeps working outside
  transactions. **Requires a live ClickHouse**.
