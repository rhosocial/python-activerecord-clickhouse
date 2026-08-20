# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/fulltext.py
from typing import List, Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseFullTextSearchMixin:
    """ClickHouse full-text search mixin.

    ClickHouse does not support standard MySQL-style FULLTEXT indexes
    or MATCH ... AGAINST search. All supports_* methods return False and
    format methods raise UnsupportedFeatureError. ClickHouse uses skip
    indexes (INDEX ... USING) instead of FULLTEXT.
    """

    def supports_fulltext_index(self) -> bool:
        return False

    def supports_fulltext_search(self) -> bool:
        return False

    def supports_fulltext_parser(self) -> bool:
        return False

    def supports_fulltext_query_expansion(self) -> bool:
        return False

    def format_fulltext_index_options(
        self, index_name: str, columns: List[str], index_type: Optional[str] = None, parser_name: Optional[str] = None
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "FULLTEXT index",
            suggestion="ClickHouse does not support FULLTEXT indexes; use skip indexes (INDEX ... USING)."
        )

    def format_match_against(
        self, columns: List[str], search_string: str, mode: Optional[str] = None
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "MATCH ... AGAINST",
            suggestion="ClickHouse does not support MATCH ... AGAINST; use LIKE, hasToken, or tokenbf_v1 skip indexes."
        )