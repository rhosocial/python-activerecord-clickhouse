# src/rhosocial/activerecord/backend/impl/clickhouse/expression/load_xml.py
"""ClickHouse LOAD XML statement expression.

ClickHouse supports importing an XML document into a table:

    LOAD XML [LOW_PRIORITY | CONCURRENT] [LOCAL] INFILE 'file'
      [REPLACE | IGNORE]
      INTO TABLE tbl_name
      [CHARACTER SET charset_name]
      [ROWS IDENTIFIED BY '<tagname>']
      [IGNORE number {LINES | ROWS}]
"""

from enum import Enum
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class LoadXMLPriority(Enum):
    """LOW_PRIORITY / CONCURRENT selector."""

    NONE = ""
    LOW_PRIORITY = "LOW_PRIORITY"
    CONCURRENT = "CONCURRENT"


class LoadXMLConflictMode(Enum):
    """REPLACE / IGNORE selector."""

    NONE = ""
    REPLACE = "REPLACE"
    IGNORE = "IGNORE"


class ClickHouseLoadXMLEXpression(BaseExpression):
    """Represent the ClickHouse ``LOAD XML`` statement.

    Attributes:
        file_path: Path to the XML file.
        table: Target table name.
        local: Use the LOCAL keyword (client-side file).
        priority: LOW_PRIORITY / CONCURRENT selector.
        conflict_mode: REPLACE / IGNORE selector.
        character_set: Character set of the file.
        rows_identified_by: XML tag name used as the row boundary.
        ignore_units: Number of leading LINES/ROWS to skip and their unit.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        file_path: str,
        table: str,
        *,
        local: bool = False,
        priority: "LoadXMLPriority" = LoadXMLPriority.NONE,
        conflict_mode: "LoadXMLConflictMode" = LoadXMLConflictMode.NONE,
        character_set: Optional[str] = None,
        rows_identified_by: Optional[str] = None,
        ignore_count: Optional[int] = None,
        ignore_unit: str = "LINES",
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.file_path: str = file_path
        self.table: str = table
        self.local: bool = local
        self.priority: LoadXMLPriority = priority
        self.conflict_mode: LoadXMLConflictMode = conflict_mode
        self.character_set: Optional[str] = character_set
        self.rows_identified_by: Optional[str] = rows_identified_by
        self.ignore_count: Optional[int] = ignore_count
        self.ignore_unit: str = ignore_unit
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    def validate(self, strict: bool = True) -> None:
        """Validate expression parameters.

        Raises:
            TypeError: If required parameters have wrong types.
            ValueError: If conflicting modes are combined.
        """
        if not strict:
            return
        if not isinstance(self.file_path, str):
            raise TypeError(f"file_path must be str, got {type(self.file_path)}")
        if not isinstance(self.table, str):
            raise TypeError(f"table must be str, got {type(self.table)}")
        if self.priority != LoadXMLPriority.NONE and self.local:
            raise ValueError("LOW_PRIORITY/CONCURRENT cannot be combined with LOCAL")
        if self.ignore_count is not None and self.ignore_count < 0:
            raise ValueError("ignore_count must be a non-negative integer")
        if self.ignore_unit not in ("LINES", "ROWS"):
            raise ValueError("ignore_unit must be 'LINES' or 'ROWS'")

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_load_xml_statement(self)