# tests/rhosocial/activerecord_clickhouse_test/feature/query/joins/test_active_query_join.py
"""
Bridge file for ActiveQuery join tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.joins.test_active_query_join import *  # noqa: F403

import pytest  # noqa: E402


# The core join-chain builder wraps each additional JOIN in a derived-table
# subquery (``FROM (SELECT * FROM a JOIN b) JOIN c``). ClickHouse 26.7+
# accepts that shape (with joined_subquery_requires_alias=0), while older
# maintained lines (25.8 LTS, 26.3 LTS) reject it at parse time. Runtime
# version probing is unreliable at collection time (an unadapted dialect
# carries no version), so the multi-join chain case is skipped
# unconditionally; single/double joins remain covered everywhere.
_MULTIPLE_JOIN_SKIP = pytest.mark.skip(
    reason="core join chaining emits nested JOIN subqueries; only ClickHouse 26.7+ parses them"
)


def _skip_multiple_joins(cls, name):
    if hasattr(cls, name):
        setattr(cls, name, _MULTIPLE_JOIN_SKIP(getattr(cls, name)))


_skip_multiple_joins(TestSyncActiveQueryJoin, "test_multiple_joins")
