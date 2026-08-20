# ClickHouse Connection Pool Examples

This directory contains examples for testing the ClickHouse connection pool.

## Available Examples

- **connection_pool_stress_test_sync.py** - Synchronous stress test for ClickHouse connection pool
- **connection_pool_stress_test_async.py** - Asynchronous stress test for ClickHouse connection pool

## Usage

Run in ClickHouse virtual environment:

```bash
# Activate virtual environment
.venv_clickhouse\Scripts\activate

# Install dependencies
pip install clickhouse-connector-python

# Run sync stress test
python docs\examples\chapter_02_connection_pool\connection_pool_stress_test_sync.py

# Run async stress test
python docs\examples\chapter_02_connection_pool\connection_pool_stress_test_async.py
```

## Test Parameters

| Parameter | Value |
|-----------|-------|
| min_size | 10 |
| max_size | 50 |
| workers | 20 |
| iterations | 50 |
| total queries | 1000 |

## Expected Results

- **threadsafety**: 1 (clickhouse.connector - only supports SQL)
- **connection_mode**: `persistent` (auto-detected from threadsafety=1, async mode)
- All 1000 queries should execute successfully
- Pool should close cleanly