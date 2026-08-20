# src/rhosocial/activerecord/backend/impl/clickhouse/expression/match_against.py
"""
ClickHouse-specific MATCH...AGAINST expression.

This module provides ClickHouseMatchAgainstExpression for ClickHouse's full-text search functionality.
"""

from typing import TYPE_CHECKING, List, Optional

from rhosocial.activerecord.backend.expression.bases import SQLQueryAndParams, SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class MatchAgainstMode:
    """Full-text search mode constants."""

    NATURAL_LANGUAGE = "NATURAL LANGUAGE"
    BOOLEAN = "BOOLEAN"
    NATURAL_LANGUAGE_WITH_QUERY_EXPANSION = "NATURAL LANGUAGE WITH QUERY EXPANSION"


class ClickHouseMatchAgainstExpression(
    AliasableMixin,
    ComparisonMixin,
    SQLValueExpression,
):
    """ClickHouse MATCH...AGAINST expression.

    Generates MATCH(col1, col2, ...) AGAINST(search_string [IN mode]) syntax.
    Supported in ClickHouse 5.6+ (with FULLTEXT index).

    Attributes:
        columns: Column names to search
        search_string: Search term
        mode: Search mode - NATURAL_LANGUAGE, BOOLEAN, or NATURAL_LANGUAGE_WITH_QUERY_EXPANSION

    Example:
        >>> expr = ClickHouseMatchAgainstExpression(
        ...     dialect,
        ...     columns=['title', 'content'],
        ...     search_string='ClickHouse',
        ...     mode='NATURAL_LANGUAGE'
        ... )
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        columns: List[str],
        search_string: str,
        mode: Optional[str] = None,
    ):
        """Initialize MATCH...AGAINST expression.

        Args:
            dialect: SQL dialect
            columns: Column names to search
            search_string: Search term
            mode: Search mode
        """
        super().__init__(dialect)
        self.columns = columns
        self.search_string = search_string
        self.mode = mode
        self.alias = None  # Initialize alias attribute

    def to_sql(self) -> "SQLQueryAndParams":
        """Generate MATCH...AGAINST SQL using dialect's format method."""
        sql, params = self.dialect.format_match_against(
            self.columns,
            self.search_string,
            self.mode,
        )

        # Apply alias if any
        if self.alias:
            sql = f"{sql} AS {self.dialect.format_identifier(self.alias)}"

        return sql, params


__all__ = [
    "ClickHouseMatchAgainstExpression",
    "MatchAgainstMode",
]
