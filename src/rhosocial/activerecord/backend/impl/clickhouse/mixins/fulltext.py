# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/fulltext.py
from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.impl.clickhouse.expression.functions import (
        ClickHouseMatchAgainstExpression,
    )


class ClickHouseFullTextSearchMixin:
    """ClickHouse full-text search mixin.

    ClickHouse does not support standard MySQL-style FULLTEXT indexes
    or MATCH ... AGAINST search. All supports_* methods return False and
    format functions raise UnsupportedFeatureError. ClickHouse's own facility is
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

    def format_match_against_expression(
        self, expr: "ClickHouseMatchAgainstExpression"
    ) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "MATCH ... AGAINST",
            suggestion="ClickHouse does not support MATCH ... AGAINST; use a text inverted index "
            "with hasAllTokens / hasAnyTokens, or LIKE.",
        )
