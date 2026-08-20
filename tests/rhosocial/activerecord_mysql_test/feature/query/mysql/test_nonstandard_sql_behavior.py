# tests/rhosocial/activerecord_clickhouse_test/feature/query/clickhouse/test_nonstandard_sql_behavior.py
"""
ClickHouse-specific tests for non-standard SQL behavior.

This module contains tests that verify ClickHouse's lenient handling of SQL statements
that violate the SQL standard. These tests are intentionally placed in the
backend-specific directory (feature/query/clickhouse/) rather than in the testsuite
because the behavior being tested is NOT SQL-standard compliant.

## Why These Tests Are Backend-Specific

The testsuite package is designed to contain only SQL-standard compliant tests
that should pass on all backends. However, different database backends have
different levels of strictness when handling non-standard SQL:

- PostgreSQL: Strictly enforces SQL standard, rejects invalid aggregate queries
- ClickHouse: Lenient, allows non-standard SQL in many cases
- SQLite: Very lenient, allows many non-standard SQL constructs

These tests specifically verify ClickHouse's lenient behavior, which differs from
the SQL standard. Therefore, they cannot be placed in the testsuite as they
would fail on PostgreSQL (which correctly rejects the invalid SQL).
"""

import pytest
from decimal import Decimal



@pytest.mark.asyncio
async def test_aggregate_with_order_by_no_group_by(async_order_fixtures):
    """
    Test that ClickHouse allows ORDER BY in aggregate queries without GROUP BY.

    ## Why This Test Is Backend-Specific (Not In Testsuite)

    This test verifies behavior that violates the SQL standard:

    ```sql
    SELECT COUNT(*) FROM orders ORDER BY order_number
    ```

    According to SQL standard, when using aggregate functions (COUNT, SUM, etc.)
    without a GROUP BY clause, the ORDER BY columns must either:
    1. Appear in the GROUP BY clause, or
    2. Be used in an aggregate function

    Since COUNT(*) returns a single row, ORDER BY is semantically meaningless.
    PostgreSQL correctly rejects this as a GroupingError.

    ClickHouse, however, allows this non-standard behavior without error.
    This test verifies ClickHouse's lenient handling, which is backend-specific.

    ## Expected Behavior

    - PostgreSQL: Raises GroupingError (SQL standard compliant)
    - ClickHouse: Executes without error (lenient) <-- This test
    - SQLite: Executes without error (lenient)
    """
    AsyncUser, AsyncOrder, AsyncOrderItem = async_order_fixtures

    user = AsyncUser(username="clickhouse_agg_user", email="clickhouseagg@example.com", age=30)
    await user.save()

    order = AsyncOrder(user_id=user.id, order_number="CLICKHOUSE-AGG-001", total_amount=Decimal("100.00"))
    await order.save()

    # This query reuses the same query object after order_by()
    # ClickHouse allows this non-standard behavior
    async_query = AsyncOrder.query()
    async_query = async_query.order_by(AsyncOrder.c.order_number)

    # Execute aggregate on query with ORDER BY (non-standard SQL)
    # ClickHouse should handle this without error
    count = await async_query.where(AsyncOrder.c.user_id == user.id).count()
    assert count == 1


@pytest.mark.asyncio
async def test_exists_with_retained_order_by(async_order_fixtures):
    """
    Test that ClickHouse allows exists() on a query with retained ORDER BY.

    ## Why This Test Is Backend-Specific (Not In Testsuite)

    This test demonstrates query object reuse where ORDER BY is retained
    across different operations, leading to non-standard SQL:

    ```sql
    -- First operation (valid)
    SELECT * FROM orders ORDER BY order_number LIMIT 1

    -- Second operation (invalid in standard SQL)
    SELECT COUNT(*) FROM orders WHERE ... ORDER BY order_number
    ```

    The second query is invalid because COUNT(*) returns one row,
    making ORDER BY meaningless. PostgreSQL raises GroupingError.

    This test verifies that ClickHouse handles this gracefully without error.

    ## Expected Behavior

    - PostgreSQL: Raises GroupingError (SQL standard compliant)
    - ClickHouse: Executes without error (lenient) <-- This test
    - SQLite: Executes without error (lenient)

    ## Note on Test Design

    The standard-compliant approach (as implemented in testsuite) is to use
    fresh query objects for semantically different operations. This test
    intentionally tests the non-standard behavior for ClickHouse compatibility.
    """
    AsyncUser, AsyncOrder, AsyncOrderItem = async_order_fixtures

    user = AsyncUser(username="clickhouse_exists_user", email="clickhouseexists@example.com", age=30)
    await user.save()

    order = AsyncOrder(user_id=user.id, order_number="CLICKHOUSE-EXISTS-001", total_amount=Decimal("50.00"))
    await order.save()

    # Reuse query object with order_by for exists()
    async_query = AsyncOrder.query()

    # First use: order_by + one (valid)
    _ = await async_query.order_by(AsyncOrder.c.order_number).one()

    # Second use: exists() on same query (ORDER BY retained, non-standard)
    # ClickHouse allows this non-standard behavior
    exists = await async_query.where(AsyncOrder.c.order_number == "CLICKHOUSE-EXISTS-001").exists()
    assert exists is True


def test_group_by_select_star_non_standard(order_fixtures):
    """
    Test that ClickHouse allows SELECT * with incomplete GROUP BY columns.

    ## Why This Test Is Backend-Specific (Not In Testsuite)

    This test verifies ClickHouse's lenient handling of non-standard GROUP BY:

    ```sql
    SELECT * FROM orders GROUP BY user_id, order_number
    ```

    According to SQL standard, when using GROUP BY, all columns in SELECT * must:
    1. Appear in the GROUP BY clause, or
    2. Be used in an aggregate function

    ClickHouse (in default mode) allows this non-standard behavior and returns
    arbitrary values from the grouped rows. PostgreSQL correctly rejects this
    as it violates the SQL standard.

    This is documented in ClickHouse docs:
    https://dev.clickhouse.com/doc/refman/8.0/en/group-by-handling.html

    ClickHouse's behavior: "The server is free to return any value from the group"
    """
    User, Order, OrderItem = order_fixtures

    user = User(username="test_user", email="test@example.com", age=30)
    user.save()

    for i in range(3):
        Order(user_id=user.id, order_number=f"ORD-{i:03d}", total_amount=Decimal(f"{(i + 1) * 100.00}")).save()

    # ClickHouse allows SELECT * with incomplete GROUP BY columns
    # This is non-standard SQL but works in ClickHouse's default mode
    results = Order.query().group_by(Order.c.user_id).group_by(Order.c.order_number).all()
    assert len(results) == 3


@pytest.mark.asyncio
async def test_group_by_select_star_non_standard_async(async_order_fixtures):
    """
    Async version: Test that ClickHouse allows SELECT * with incomplete GROUP BY columns.

    See sync version for explanation of non-standard behavior.
    """
    AsyncUser, AsyncOrder, AsyncOrderItem = async_order_fixtures

    user = AsyncUser(username="test_user", email="test@example.com", age=30)
    await user.save()

    for i in range(3):
        order = AsyncOrder(user_id=user.id, order_number=f"ORD-{i:03d}", total_amount=Decimal(f"{(i + 1) * 100.00}"))
        await order.save()

    # ClickHouse allows SELECT * with incomplete GROUP BY columns
    results = await AsyncOrder.query().group_by(AsyncOrder.c.user_id).group_by(AsyncOrder.c.order_number).all()
    assert len(results) == 3
