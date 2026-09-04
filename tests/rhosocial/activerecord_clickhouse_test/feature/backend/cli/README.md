# tests/.../feature/backend/cli/

Black-box tests for the ClickHouse backend's CLI entry point
(``python -m rhosocial.activerecord.backend.impl.clickhouse``).

- `test_cli_blackbox.py` — runs the CLI in-process via `main(argv)` and
  asserts on stdout (`-o json` for clean structured data): `info`, `query`,
  `introspect`, `status`, and the named-* inventory commands. **Requires a
  live ClickHouse server** (scenarios from `tests/config/clickhouse_scenarios.yaml`).
