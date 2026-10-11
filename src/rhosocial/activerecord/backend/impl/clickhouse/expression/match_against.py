# src/rhosocial/activerecord/backend/impl/clickhouse/expression/match_against.py
"""
ClickHouse-specific MATCH...AGAINST expression.

This module provides ClickHouseMatchAgainstExpression for ClickHouse's full-text search functionality.
"""

from typing import TYPE_CHECKING, List, Optional

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
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

    This dialect never renders it: ``ClickHouseFullTextSearchMixin.format_match_against``
    raises ``UnsupportedFeatureError``. ClickHouse has no ``MATCH ... AGAINST``
    and no ``FULLTEXT`` index type — declaring one answers ``Unknown Index type
    'fulltext'`` and lists what the server does have (``hypothesis, text,
    vector_similarity, bloom_filter, sparse_grams, tokenbf_v1, ngrambf_v1, set,
    minmax``). The ClickHouse equivalent is a ``text`` inverted index queried
    with ``hasAllTokens`` / ``hasAnyTokens``. No ClickHouse version enables this
    syntax, because no version has the statement.

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
        *,
        alias: Optional[str] = None,
    ):
        """Initialize MATCH...AGAINST expression.

        Args:
            dialect: SQL dialect
            columns: Column names to search
            search_string: Search term
            mode: Search mode
            alias: Optional alias
        """
        super().__init__(dialect)
        self.columns = columns
        self.search_string = search_string
        self.mode = mode
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_match_against"


__all__ = [
    "ClickHouseMatchAgainstExpression",
    "MatchAgainstMode",
]
