# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/fulltext_search.py
"""ClickHouse full-text search protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import IndexObjectSupport


@runtime_checkable
class ClickHouseFullTextSearchSupport(IndexObjectSupport, Protocol):
    """ClickHouse full-text search protocol.

    Note: Most interfaces are defined in generic IndexObjectSupport protocol.
    This protocol only defines ClickHouse-specific interfaces.

    Feature Source: ClickHouse 5.6+

    ClickHouse full-text features:
    - FULLTEXT index on CHAR, VARCHAR, TEXT columns
    - FULLTEXT index on multiple columns
    - Natural language, Boolean, Query expansion modes
    - IN NATURAL LANGUAGE MODE, IN BOOLEAN MODE, WITH QUERY EXPANSION
    - Stopwords, minimum word length

    Official Documentation:
    - Full-Text Search Functions: https://dev.clickhouse.com/doc/refman/8.0/en/fulltext-search.html

    Version Requirements:
    - FULLTEXT index: ClickHouse 5.6+ (InnoDB), all versions (MyISAM)
    - FULLTEXT parser: ClickHouse 5.1+
    - IN BOOLEAN MODE: ClickHouse 5.6+
    - WITH QUERY EXPANSION: ClickHouse 5.6.7+
    """

    def supports_fulltext_index(self) -> bool:
        """Whether FULLTEXT index is supported (ClickHouse 5.6+ InnoDB)."""
        ...

    def supports_fulltext_search(self) -> bool:
        """Whether ``MATCH ... AGAINST`` querying is supported (ClickHouse 5.6+).

        ClickHouse couples DDL and query capabilities — a FULLTEXT index
        enables MATCH ... AGAINST. This delegates to
        :meth:`supports_fulltext_index`.
        """
        ...

    def supports_fulltext_parser(self) -> bool:
        """Whether custom full-text parser plugins are supported (ClickHouse 5.1+)."""
        ...

    def supports_fulltext_query_expansion(self) -> bool:
        """Whether query expansion mode is supported (ClickHouse 5.6.7+)."""
        ...

    def format_match_against(self, expr) -> Tuple[str, tuple]:
        """Format MATCH ... AGAINST expression."""
        ...

    def format_fulltext_index_options(
        self, index: str, columns: list, index_type: str = None, parser_name: str = None
    ) -> Tuple[str, tuple]:
        """Format FULLTEXT index options."""
        ...
