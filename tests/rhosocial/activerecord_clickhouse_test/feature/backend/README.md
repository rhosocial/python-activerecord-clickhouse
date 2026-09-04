# tests/.../activerecord_clickhouse_test/feature/backend/

ClickHouse backend tests organized by common subject (taxonomy per
`python-activerecord/.claude/plan/2026-09-03/cross-backend-test-taxonomy.md` §5.7).

## Subjects present

| Directory | Files |
|-----------|-------|
| `adapters/` | value adapters, column mapping |
| `backend/` | backend-object lifecycle/ops |
| `cli/` | CLI blackbox |
| `ddl/` | DDL generation/coverage, CreateTableExpression diff |
| `dialect/` | dialect capabilities, security, mixins, unsupported features, live-backend dialect |
| `dml/` | CRUD via backend object |
| `expression/` | JSON, datetime-interval expressions |
| `functions/` | dialect function support, JSON functions |
| `introspection/` | introspection |
| `protocol/` | protocol conformance |
| `query/` | EXPLAIN, query features |
| `schema/` | schema support |
| `transactions/` | transaction (no-op) semantics |
| `types/` | native types |

## Sync/Async status: **Gap** (sync-only)

`clickhouse-connect` (the driver in `pyproject.toml`) is a synchronous-only
library. `AsyncClickHouseBackend`
(`src/rhosocial/activerecord/backend/impl/clickhouse/async_backend.py`) is a
fail-fast placeholder: instantiation raises `NotImplementedError`. No async
tests are provided; per plan §4.3 / §6 this is a **Gap**, not a Fill item.

## Pending (Tier-2 fill)

- `concurrency/test_concurrency_protocol.py` — plan §6 matrix marks `F`
  (driver/`AsyncClickHouseConcurrencyMixin` exist in src; protocol tests not
  yet written).
- `dml/test_execute_many.py` — plan §6 matrix marks `F`.
- `backend/test_error_handling.py` — plan §6 matrix marks `F`
  (async twin n/a: sync-only backend).

## Live-server tests

Several files require a live ClickHouse (see `tests/config/clickhouse_scenarios.yaml`).
Files needing a server are marked in their subject READMEs.
