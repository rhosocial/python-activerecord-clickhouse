# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/fulltext.py
from typing import List, Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseFullTextSearchMixin:
    """ClickHouse full-text search mixin.

    ClickHouse does not support standard MySQL-style FULLTEXT indexes
    or MATCH ... AGAINST search. All supports_* methods return False and
    format methods raise UnsupportedFeatureError. ClickHouse's own facility is
    the ``text`` inverted index (GA from 26.2), declared as a skip index and
    queried with ``hasAllTokens`` / ``hasAnyTokens``.
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
        self, index: str, columns: List[str], index_type: Optional[str] = None, parser_name: Optional[str] = None
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "FULLTEXT index",
            suggestion="ClickHouse does not support FULLTEXT indexes; use a text inverted index "
            "skip index (INDEX ... TYPE text(tokenizer = splitByNonAlpha)) queried with "
            "hasAllTokens / hasAnyTokens. tokenbf_v1 still works but is deprecated from 26.2.",
        )

    def format_match_against(self, expr) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "MATCH ... AGAINST",
            suggestion="ClickHouse does not support MATCH ... AGAINST; use a text inverted index "
            "with hasAllTokens / hasAnyTokens, or LIKE.",
        )