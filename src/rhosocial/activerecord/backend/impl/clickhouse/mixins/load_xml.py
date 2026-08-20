# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/load_xml.py
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.impl.clickhouse.expression.load_xml import (
        ClickHouseLoadXMLEXpression,
    )


class ClickHouseLoadXMLLMixin:
    """ClickHouse LOAD XML statement support."""

    def supports_load_xml(self) -> bool:
        return True

    def format_load_xml_statement(self, expr: "ClickHouseLoadXMLEXpression") -> Tuple[str, tuple]:
        """Format ``LOAD XML ... INFILE ... INTO TABLE ...``."""
        expr.validate(strict=self.strict_validation)

        parts = ["LOAD XML"]

        if expr.priority.value:
            parts.append(expr.priority.value)
        elif expr.local:
            parts.append("LOCAL")

        parts.append("INFILE")
        file_path_escaped = expr.file_path.replace("\\", "\\\\").replace("'", "\\'")
        parts.append(f"'{file_path_escaped}'")

        if expr.conflict_mode.value:
            parts.append(expr.conflict_mode.value)

        parts.append("INTO TABLE")
        parts.append(self.format_identifier(expr.table))

        if expr.character_set:
            parts.append(f"CHARACTER SET {expr.character_set}")

        if expr.rows_identified_by:
            parts.append(f"ROWS IDENTIFIED BY '<{expr.rows_identified_by}>'")

        if expr.ignore_count is not None:
            parts.append(f"IGNORE {expr.ignore_count} {expr.ignore_unit}")

        return " ".join(parts), ()