# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_datetime_interval_expressions.py
"""Tests for ClickHouse datetime interval expressions."""

import pytest

from rhosocial.activerecord.backend.expression import Column, Literal, QueryExpression
from rhosocial.activerecord.backend.expression.functions import (
    date_add,
    date_diff,
    date_part,
    date_sub,
    date_trunc,
    extract,
    interval,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


class TestClickHouseDateTimeIntervalExpressions:
    @pytest.mark.parametrize(
        "field",
        ["year", "month", "day", "hour", "minute", "second"],
    )
    def test_extract_datetime_fields(self, clickhouse_dialect: ClickHouseDialect, field: str):
        expr = extract(clickhouse_dialect, field, Column(clickhouse_dialect, "created_at"))

        sql, params = expr.to_sql()

        assert sql == f"EXTRACT({field.upper()} FROM `created_at`)"
        assert params == ()

    def test_date_part_uses_extract_mapping(self, clickhouse_dialect: ClickHouseDialect):
        expr = date_part(clickhouse_dialect, "day", Column(clickhouse_dialect, "created_at"))

        sql, params = expr.to_sql()

        assert sql == "EXTRACT(DAY FROM `created_at`)"
        assert params == ()

    @pytest.mark.parametrize(
        "field",
        ["year", "month", "day", "hour", "minute", "second"],
    )
    def test_date_trunc_datetime_fields(self, clickhouse_dialect: ClickHouseDialect, field: str):
        expr = date_trunc(clickhouse_dialect, field, Column(clickhouse_dialect, "created_at"))

        sql, params = expr.to_sql()

        assert sql == "date_trunc(%s, `created_at`)"
        assert params == (field.upper(),)

    @pytest.mark.parametrize(
        "field",
        ["week", "year"],
    )
    def test_date_trunc_additional_fields(self, clickhouse_dialect: ClickHouseDialect, field: str):
        expr = date_trunc(clickhouse_dialect, field, Column(clickhouse_dialect, "created_at"))

        sql, params = expr.to_sql()

        assert sql == "date_trunc(%s, `created_at`)"
        assert params == (field.upper(),)

    def test_interval_expression(self, clickhouse_dialect: ClickHouseDialect):
        expr = interval(clickhouse_dialect, 2, "hour")

        sql, params = expr.to_sql()

        assert sql == "INTERVAL %s HOUR"
        assert params == (2,)

    def test_date_add_column_source(self, clickhouse_dialect: ClickHouseDialect):
        expr = date_add(clickhouse_dialect, Column(clickhouse_dialect, "created_at"), 1, "day")

        sql, params = expr.to_sql()

        assert sql == "date_add(DAY, INTERVAL %s DAY, `created_at`)"
        assert params == (1,)

    def test_date_sub_interval_expression(self, clickhouse_dialect: ClickHouseDialect):
        expr = date_sub(
            clickhouse_dialect,
            Column(clickhouse_dialect, "created_at"),
            interval(clickhouse_dialect, 2, "hour"),
        )

        sql, params = expr.to_sql()

        assert sql == "date_sub(HOUR, INTERVAL %s HOUR, `created_at`)"
        assert params == (2,)

    def test_date_add_literal_source_params_order(self, clickhouse_dialect: ClickHouseDialect):
        expr = date_add(
            clickhouse_dialect,
            Literal(clickhouse_dialect, "2026-06-04 10:00:00"),
            30,
            "minute",
        )

        sql, params = expr.to_sql()

        assert sql == "date_add(MINUTE, INTERVAL %s MINUTE, %s)"
        assert params == ("2026-06-04 10:00:00", 30)

    @pytest.mark.parametrize(
        "unit",
        ["year", "month", "week", "day", "hour", "minute", "second"],
    )
    def test_date_diff_supported_units(self, clickhouse_dialect: ClickHouseDialect, unit: str):
        expr = date_diff(
            clickhouse_dialect,
            unit,
            Column(clickhouse_dialect, "started_at"),
            Column(clickhouse_dialect, "ended_at"),
        )

        sql, params = expr.to_sql()

        assert sql == "dateDiff(%s, `started_at`, `ended_at`)"
        assert params == (unit.upper(),)

    def test_alias_and_cast(self, clickhouse_dialect: ClickHouseDialect):
        expr = (
            date_diff(
                clickhouse_dialect,
                "day",
                Column(clickhouse_dialect, "started_at"),
                Column(clickhouse_dialect, "ended_at"),
            )
            .cast("SIGNED")
            .as_("elapsed_days")
        )

        sql, params = expr.to_sql()

        assert sql == "CAST(dateDiff(%s, `started_at`, `ended_at`) AS SIGNED) AS `elapsed_days`"
        assert params == ("DAY",)

    def test_query_expression_integration(self, clickhouse_dialect: ClickHouseDialect):
        shifted = date_add(clickhouse_dialect, Column(clickhouse_dialect, "created_at"), 1, "day")
        query = QueryExpression(
            clickhouse_dialect,
            select=[extract(clickhouse_dialect, "year", Column(clickhouse_dialect, "created_at"))],
            from_="events",
            where=shifted > Literal(clickhouse_dialect, "2026-01-01"),
        )

        sql, params = query.to_sql()

        assert "EXTRACT(YEAR FROM `created_at`)" in sql
        assert "date_add(DAY, INTERVAL %s DAY, `created_at`) > %s" in sql
        assert params == (1, "2026-01-01")
