# concurrency

ConcurrencyAware protocol conformance for the ClickHouse backend.

## Files
- `test_concurrency_protocol.py` — ConcurrencyAware isinstance check and
  `get_concurrency_hint()` outcome (None or ConcurrencyHint bounded by
  `max_concurrent_queries` / pool size).
