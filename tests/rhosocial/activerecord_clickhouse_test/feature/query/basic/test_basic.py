# tests/rhosocial/activerecord_clickhouse_test/feature/query/test_basic.py
"""
Bridge file for basic tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""

from rhosocial.activerecord.testsuite.feature.query.basic.test_basic import *  # noqa: F403

import pytest  # noqa: E402


# The core query builder wraps a JOIN chain in a subquery when a second join
# is added; the outer scope still references qualified columns of the wrapped
# query (e.g. ``orders.user_id``). MySQL tolerates this scoping, ClickHouse
# does not (UNKNOWN_IDENTIFIER), so the test's generated SQL is not portable.
def _clickhouse_exists_with_joins(order_fixtures):
    pytest.skip("Core join chaining wraps joins in subqueries; ClickHouse cannot resolve outer qualified columns")


test_exists_with_joins = _clickhouse_exists_with_joins

