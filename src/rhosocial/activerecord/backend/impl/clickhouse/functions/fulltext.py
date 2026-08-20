# src/rhosocial/activerecord/backend/impl/clickhouse/functions/fulltext.py
"""
ClickHouse full-text search function factories.

Functions: match_against

.. warning::
    This module was copied from the MySQL backend template and contains
    MySQL-style SQL functions/show commands. ClickHouse uses different
    function names (e.g. ``JSONExtract*``) and a different SHOW command
    subset. May generate non-ClickHouse SQL; verify before use.
"""

from typing import Union, List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases

if TYPE_CHECKING:  # pragma: no cover
    from .dialect import ClickHouseDialect


def match_against(
    dialect: "ClickHouseDialect",
    columns: Union[str, List[str]],
    search_string: str,
    mode: Optional[str] = None,
) -> "bases.BaseExpression":
    """
    Creates a MATCH ... AGAINST expression for full-text search.

    Usage rules:
    - Natural language mode (default): match_against(dialect, "content", "search term")
    - Boolean mode: match_against(dialect, "content", "+term -exclude", mode="BOOLEAN")
    - Query expansion: match_against(dialect, "content", "search term", mode="QUERY_EXPANSION")

    Args:
        dialect: The ClickHouse dialect instance
        columns: Column name(s) to search
        search_string: Search string
        mode: Search mode - "NATURAL_LANGUAGE", "BOOLEAN", or "QUERY_EXPANSION"

    Returns:
        A ClickHouseMatchAgainstExpression instance representing MATCH ... AGAINST

    Version: ClickHouse 5.6+ (with parser option in 5.7+)
    """
    from rhosocial.activerecord.backend.impl.clickhouse.expression.match_against import (
        ClickHouseMatchAgainstExpression,
    )

    if isinstance(columns, str):
        columns = [columns]

    return ClickHouseMatchAgainstExpression(
        dialect,
        columns=columns,
        search_string=search_string,
        mode=mode,
    )


__all__ = [
    "match_against",
]
