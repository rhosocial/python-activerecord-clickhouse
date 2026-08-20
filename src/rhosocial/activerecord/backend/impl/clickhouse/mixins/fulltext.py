# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/fulltext.py
from typing import List, Optional, Tuple


class ClickHouseFullTextSearchMixin:
    """ClickHouse full-text search mixin."""

    def supports_fulltext_index(self) -> bool:
        """Whether FULLTEXT index is supported (ClickHouse 5.6+ InnoDB)."""
        return self.version >= (5, 6, 0)

    def supports_fulltext_search(self) -> bool:
        """Whether full-text search (MATCH ... AGAINST) is supported.

        ClickHouse exposes FULLTEXT indexes and ``MATCH ... AGAINST`` together,
        so this delegates to :meth:`supports_fulltext_index`. Override in
        subclasses only if a future ClickHouse-flavoured backend decouples the
        two.
        """
        return self.supports_fulltext_index()

    def supports_fulltext_parser(self) -> bool:
        return self.version >= (5, 1, 0)

    def supports_fulltext_query_expansion(self) -> bool:
        return True

    def format_fulltext_index_options(
        self, index_name: str, columns: List[str], index_type: Optional[str] = None, parser_name: Optional[str] = None
    ) -> Tuple[str, tuple]:
        """Format FULLTEXT index options for CREATE TABLE / ALTER TABLE."""
        col_parts = [self.format_identifier(c) for c in columns]
        sql = f"FULLTEXT {self.format_identifier(index_name)} ({', '.join(col_parts)})"
        if parser_name:
            sql += f" WITH PARSER {self.format_identifier(parser_name)}"
        return sql, ()

    def format_match_against(
        self, columns: List[str], search_string: str, mode: Optional[str] = None
    ) -> Tuple[str, tuple]:
        """Format MATCH ... AGAINST expression."""
        cols_sql = ", ".join(self.format_identifier(c) for c in columns)

        placeholder = self.get_parameter_placeholder()
        search_sql = placeholder
        search_params = (search_string,)

        if mode:
            mode_upper = mode.upper()
            if mode_upper == "NATURAL_LANGUAGE":
                mode_str = "IN NATURAL LANGUAGE MODE"
            elif mode_upper == "BOOLEAN":
                mode_str = "IN BOOLEAN MODE"
            elif mode_upper == "QUERY_EXPANSION":
                mode_str = "IN NATURAL LANGUAGE MODE WITH QUERY EXPANSION"
            else:
                mode_str = ""
        else:
            mode_str = "IN NATURAL LANGUAGE MODE"

        sql = f"MATCH({cols_sql}) AGAINST({search_sql} {mode_str})"
        return sql, search_params
