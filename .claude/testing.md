# Testing Guide - python-activerecord-clickhouse

> AI Assistant Note: This document covers ClickHouse backend-specific testing requirements.

## Project-Specific Information

| Item | Value |
|------|-------|
| **Python Version** | 3.8+ |
| **Database Driver** | clickhouse-connector-python |
| **Free-Threading Support** | ✅ Yes |

## Dependencies

```toml
dependencies = [
    "rhosocial-activerecord>=0.9.0,<2.0.0",
    "clickhouse-connector-python>=9.0.0"
]
```

## Quick Test Commands

```bash
# Activate virtual environment and set PYTHONPATH
cd /mnt/i/GitHubRepositories/rhosocial/python-activerecord-clickhouse
source .venv/bin/activate
export PYTHONPATH=src

# Run tests
pytest

# Run specific test directory
pytest tests/rhosocial/activerecord_clickhouse_test/feature/basic/
```

## Backend-Specific Test Markers

```python
markers = [
    "clickhouse_json: ClickHouse-specific JSON tests",
]
```

## Key Differences from Core

- Uses ClickHouse-specific dialect in `src/rhosocial/activerecord/backend/impl/clickhouse/dialect.py`
- Schema files in `tests/rhosocial/activerecord_clickhouse_test/feature/basic/schema/`
- Provider implementation in `tests/providers/`

## Reference

- [Core testing guide](../python-activerecord/.claude/testing.md)
- [ClickHouse backend development](../python-activerecord/.claude/backend_development.md)