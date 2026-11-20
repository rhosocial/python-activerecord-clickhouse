# tests/.../feature/backend/cli/

Black-box tests for the ClickHouse backend's CLI entry point
(``python -m rhosocial.activerecord.backend.impl.clickhouse``).

- `test_cli.py` — runs the CLI in-process via `main(argv)` and
  asserts on stdout (`-o json` for clean structured data): `info`, `query`,
  `introspect`, `status`, and the named-* inventory commands. **Requires a
  live ClickHouse server** (scenarios from `tests/config/clickhouse_scenarios.yaml`).
- `test_introspect_families_cli.py`, `test_catalog_families_cli.py` — offline
  wiring tests: type surface, NAME rules, capability gate, sync/async dispatch
  and JSON shape for the table-scoped and server-wide catalogue families.
