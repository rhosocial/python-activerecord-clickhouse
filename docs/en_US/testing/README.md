# Testing

This section covers how to run the ClickHouse backend tests locally and in CI.

## Test suite composition

The tests consist of two parts:

1. **Shared testsuite**: the feature tests (basic/events/interface/mixins/query/relation) of [python-activerecord-testsuite](https://github.com/rhosocial/python-activerecord-testsuite); this backend wires them in via bridge files under `tests/rhosocial/activerecord_clickhouse_test/feature/`.
2. **Backend's own tests**: `tests/rhosocial/activerecord_clickhouse_test/feature/backend/` (dialect/mixin/protocol contracts, DDL coverage, fail-fast contracts, etc.).

## Running locally

You need a reachable ClickHouse instance (see [Installation guide](../installation/installation.md#启动本地-clickhouse可选用于测试)).

```bash
export PYTHONPATH=src:tests
.venv3.14-ubuntu26.04/bin/python -m pytest tests/rhosocial -p no:logging -p no:cacheprovider
```

> `PYTHONPATH=tests` is required — it lets pytest find `tests/providers/registry.py` (which provides the provider implementation pointed to by `TESTSUITE_PROVIDER_REGISTRY`).

## Scenario configuration

Tests read connection scenarios from `tests/config/clickhouse_scenarios.yaml` by default; override with `CLICKHOUSE_SCENARIOS_CONFIG_PATH`:

```bash
export CLICKHOUSE_SCENARIOS_CONFIG_PATH=/path/to/scenarios.yaml
```

Scenario file format:

```yaml
scenarios:
  clickhouse_http:
    host: 127.0.0.1
    port: 8123
    database: test_db
    username: root
    password: password
    autocommit: true
```

## Skipping unsupported features

Capabilities ClickHouse does not support (transactions, UPSERT, foreign keys, etc.) are reasonably skipped via `pytest.skip` in the testsuite and will not fail. The test output shows `SKIPPED [N] ... ClickHouse does not support ...`.

## CI matrix

CI runs on push/PR to `main` (`.github/workflows/test.yml`):

```
Python 3.10 × ClickHouse 25.8
Python 3.11 × ClickHouse 25.8
Python 3.12 × ClickHouse 26.3
Python 3.13 × ClickHouse 26.3
Python 3.14 × ClickHouse 26.7   ← 同时收集覆盖率
```

CI checks out the core library and testsuite's `feature/parallel-testing` branches from source and installs them editable, so testing works **without** dev30 being on PyPI.

## Code style checks

```bash
.venv3.14-ubuntu26.04/bin/ruff check src/
```

CI does not currently gate on `ruff`, but `src/` should remain zero-error (pre-existing lint in `tests/` is out of scope for cleanup).

## Next steps

- [Supported versions](../introduction/supported_versions.md)
- [CLI usage](../cli/README.md)
