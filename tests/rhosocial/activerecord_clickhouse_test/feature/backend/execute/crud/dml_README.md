# tests/.../feature/backend/dml/

DML behavior tests through the backend object.

- `test_crud_backend.py` — minimal insert/fetch cycle through the backend
  object, plus transaction-as-noop semantics. **Requires a live ClickHouse**.

## Pending (Tier-2 fill)

- `test_execute_many.py` — see plan §6 matrix (`python-activerecord/.claude/plan/2026-09-03/cross-backend-test-taxonomy.md`).
