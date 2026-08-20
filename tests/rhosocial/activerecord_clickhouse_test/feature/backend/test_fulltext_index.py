# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_fulltext_index.py
"""
ClickHouse FULLTEXT index support tests.

This module tests ClickHouse-specific FULLTEXT index functionality including:
- Protocol support detection
- MATCH ... AGAINST expression formatting
- CREATE FULLTEXT INDEX statement formatting
"""

import pytest
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.expression.statements import (
    CreateFulltextIndexExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression import ClickHouseMatchAgainstExpression


class TestFullTextProtocol:
    """Test FULLTEXT protocol implementation."""

    def test_supports_fulltext_index_version_check(self):
        """Test version check for FULLTEXT index support."""
        # ClickHouse 5.5 - not supported for InnoDB
        dialect_55 = ClickHouseDialect(version=(5, 5, 0))
        assert not dialect_55.supports_fulltext_index()

        # ClickHouse 5.6 - supported for InnoDB
        dialect_56 = ClickHouseDialect(version=(5, 6, 0))
        assert dialect_56.supports_fulltext_index()

        # ClickHouse 8.0 - supported
        dialect_80 = ClickHouseDialect(version=(8, 0, 0))
        assert dialect_80.supports_fulltext_index()

    def test_format_match_against(self):
        """Test format_match_against method."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        sql, params = dialect.format_match_against(["title", "content"], "ClickHouse", mode="NATURAL_LANGUAGE")

        assert "MATCH(`title`, `content`)" in sql
        assert "AGAINST" in sql
        assert "IN NATURAL LANGUAGE MODE" in sql
        assert params == ("ClickHouse",)

    def test_match_against_expression(self):
        """Test ClickHouseMatchAgainstExpression class."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseMatchAgainstExpression(
            dialect, columns=["title", "content"], search_string="database", mode="BOOLEAN"
        )

        sql, params = expr.to_sql()

        assert "MATCH(`title`, `content`)" in sql
        assert "AGAINST" in sql
        assert "IN BOOLEAN MODE" in sql
        assert params == ("database",)

    def test_match_against_with_alias(self):
        """Test ClickHouseMatchAgainstExpression with alias."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = ClickHouseMatchAgainstExpression(dialect, columns=["title", "content"], search_string="test")

        aliased = expr.as_("relevance")
        sql, params = aliased.to_sql()

        assert "MATCH(`title`, `content`)" in sql
        assert "AGAINST" in sql
        assert params == ("test",)

    def test_supports_fulltext_parser(self):
        """Test parser plugin support."""
        dialect = ClickHouseDialect(version=(8, 0, 0))
        assert dialect.supports_fulltext_parser()

        dialect_old = ClickHouseDialect(version=(5, 0, 0))
        assert not dialect_old.supports_fulltext_parser()

    def test_supports_fulltext_query_expansion(self):
        """Test query expansion support."""
        dialect = ClickHouseDialect(version=(5, 7, 0))
        assert dialect.supports_fulltext_query_expansion()

    def test_format_fulltext_match_natural_mode(self):
        """Test MATCH ... AGAINST with natural language mode."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        sql, params = dialect.format_fulltext_match(["title", "content"], "database system")

        assert "MATCH(`title`, `content`)" in sql
        assert "AGAINST" in sql
        assert "IN NATURAL LANGUAGE MODE" in sql
        assert params == ("database system",)

    def test_format_fulltext_match_boolean_mode(self):
        """Test MATCH ... AGAINST with boolean mode."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        sql, params = dialect.format_fulltext_match(["title", "content"], "+database +system", mode="BOOLEAN")

        assert "MATCH(`title`, `content`)" in sql
        assert "AGAINST" in sql
        assert "IN BOOLEAN MODE" in sql
        assert params == ("+database +system",)

    def test_format_fulltext_match_query_expansion(self):
        """Test MATCH ... AGAINST with query expansion."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        sql, params = dialect.format_fulltext_match(["content"], "database", mode="QUERY EXPANSION")

        assert "MATCH(`content`)" in sql
        assert "AGAINST" in sql
        assert "WITH QUERY EXPANSION" in sql
        assert params == ("database",)

    def test_format_create_fulltext_index(self):
        """Test CREATE FULLTEXT INDEX statement formatting."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = CreateFulltextIndexExpression(
            dialect=dialect, index_name="idx_content", table_name="articles", columns=["title", "content"]
        )
        sql, params = expr.to_sql()

        assert "CREATE FULLTEXT INDEX" in sql
        assert "`idx_content`" in sql
        assert "ON `articles`" in sql
        assert "`title`, `content`" in sql
        assert params == ()

    def test_format_create_fulltext_index_with_parser(self):
        """Test CREATE FULLTEXT INDEX with parser plugin."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        expr = CreateFulltextIndexExpression(
            dialect=dialect, index_name="idx_content", table_name="articles", columns=["content"], parser="ngram"
        )
        sql, params = expr.to_sql()

        assert "CREATE FULLTEXT INDEX" in sql
        assert "WITH PARSER `ngram`" in sql
        assert params == ()

    def test_fulltext_unsupported_raises_error(self):
        """Test that unsupported FULLTEXT raises error."""
        dialect = ClickHouseDialect(version=(5, 5, 0))

        with pytest.raises(Exception):  # UnsupportedFeatureError  # noqa: B017
            dialect.format_fulltext_match(["title"], "test")

        with pytest.raises(Exception):  # UnsupportedFeatureError  # noqa: B017
            expr = CreateFulltextIndexExpression(
                dialect=dialect, index_name="idx_test", table_name="test_table", columns=["content"]
            )
            expr.to_sql()


class TestAsyncFullTextProtocol:
    """Test async FULLTEXT protocol (same as sync, but verifies parity)."""

    @pytest.mark.asyncio
    async def test_async_supports_fulltext_index(self):
        """Test async version of supports_fulltext_index."""
        dialect = ClickHouseDialect(version=(8, 0, 0))
        # Protocol methods are synchronous, so async just calls sync
        assert dialect.supports_fulltext_index()

    @pytest.mark.asyncio
    async def test_async_format_fulltext_match(self):
        """Test async version of MATCH formatting."""
        dialect = ClickHouseDialect(version=(8, 0, 0))

        sql, params = dialect.format_fulltext_match(["title"], "test", mode="BOOLEAN")

        assert "MATCH(`title`)" in sql
        assert "IN BOOLEAN MODE" in sql
