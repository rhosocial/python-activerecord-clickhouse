# tests/rhosocial/activerecord_clickhouse_test/feature/backend/execute/clickhouse/dialect/conftest.py
"""No directory-specific fixtures: these tests use the backend-owned fixtures.

The database is derived from this directory's path by ``feature/backend/conftest.py``.
The directory owns one database per scenario, so its tests are declared a
parallel subset below (one worker per scenario).
"""

from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    parallel=True,
    purpose="Backend-owned ClickHouse tests for this execute area (directory-owned database).",
    passes_means="the backend behaves as specified for this area across the configured scenarios",
    fails_means="the backend diverges from the expected behaviour or loses data in this area",
)
