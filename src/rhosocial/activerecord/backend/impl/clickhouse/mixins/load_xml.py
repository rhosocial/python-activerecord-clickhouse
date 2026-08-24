# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/load_xml.py
from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class ClickHouseLoadXMLLMixin:
    """ClickHouse does not support ``LOAD XML``.

    ``LOAD XML INFILE ... INTO TABLE`` is a MySQL statement. ClickHouse ingests
    data via ``input()`` table function, external dictionaries, or
    ``INSERT INTO ... FROM`` with format parsers (e.g. ``Format XML``).
    All methods fail fast.
    """

    def supports_load_xml(self) -> bool:
        return False

    def format_load_xml_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "LOAD XML",
            suggestion="ClickHouse has no LOAD XML; use a format parser or input() table function.",
        )
