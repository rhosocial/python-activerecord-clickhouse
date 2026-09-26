# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_materialized_view_support.py
"""
ClickHouse materialized view support boundary.

ClickHouse *has* materialized views, but its DDL shares almost nothing with the
SQL-standard statement the generic ``CreateMaterializedViewExpression`` renders:

* without a ``TO`` clause an ``ENGINE`` is mandatory;
* there is no ``WITH DATA`` / ``WITH NO DATA`` clause (``POPULATE`` / ``EMPTY``);
* deletion uses ``DROP VIEW``, not ``DROP MATERIALIZED VIEW``;
* refreshable views add ``REFRESH EVERY|AFTER``, ``APPEND``, ``DEPENDS ON``;
* semantics are insert-trigger based, not query-result caching.

So the generic API must report the capability as unsupported and fail fast,
rather than emit SQL the server rejects. These tests lock that boundary; the
raw-SQL usage test lives in ``query/test_query_features.py``.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import Column, QueryExpression, TableExpression
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
    DropMaterializedViewExpression,
    RefreshMaterializedViewExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


def _source_query(clickhouse_dialect):
    return QueryExpression(
        dialect=clickhouse_dialect,
        select=[Column(clickhouse_dialect, "grp")],
        from_=TableExpression(clickhouse_dialect, "src"),
    )



class TestMaterializedViewCapabilityBoundary:
    """The capability must not be advertised while the DDL cannot be rendered."""

    def test_probe_reports_unsupported(self, clickhouse_dialect):
        assert clickhouse_dialect.supports_materialized_view() is False

    def test_refresh_probe_reports_unsupported(self, clickhouse_dialect):
        assert clickhouse_dialect.supports_refresh_materialized_view() is False

    def test_probe_is_stable(self, clickhouse_dialect):
        """Repeated calls must agree — a lying probe is worse than a missing one."""
        results = {clickhouse_dialect.supports_materialized_view() for _ in range(3)}
        assert results == {False}


class TestGenericMaterializedViewFailsFast:
    """Using the generic expressions must raise, not emit invalid SQL."""

    def test_create_raises(self, clickhouse_dialect):
        expression = CreateMaterializedViewExpression(
            dialect=clickhouse_dialect, view_name="mv_ch", query=_source_query(clickhouse_dialect)
        )
        with pytest.raises(UnsupportedFeatureError) as exc:
            expression.to_sql()
        assert "CREATE MATERIALIZED VIEW" in str(exc.value)

    def test_refresh_raises(self, clickhouse_dialect):
        expression = RefreshMaterializedViewExpression(dialect=clickhouse_dialect, view_name="mv_ch")
        with pytest.raises(UnsupportedFeatureError):
            expression.to_sql()

    def test_drop_raises(self, clickhouse_dialect):
        expression = DropMaterializedViewExpression(
            dialect=clickhouse_dialect, view_name="mv_ch", if_exists=True
        )
        with pytest.raises(UnsupportedFeatureError):
            expression.to_sql()

    def test_no_clickhouse_specific_with_data_clause_is_emitted(self, clickhouse_dialect):
        """Guard the exact regression: the generic form leaked ``WITH DATA``."""
        expression = CreateMaterializedViewExpression(
            dialect=clickhouse_dialect, view_name="mv_ch", query=_source_query(clickhouse_dialect)
        )
        try:
            sql, _ = expression.to_sql()
        except UnsupportedFeatureError:
            return
        pytest.fail(f"generic CREATE MATERIALIZED VIEW must not render, got {sql!r}")


class TestDialectInstantiation:
    """A freshly constructed dialect reports the same boundary."""

    def test_default_dialect_reports_unsupported(self):
        assert ClickHouseDialect().supports_materialized_view() is False
