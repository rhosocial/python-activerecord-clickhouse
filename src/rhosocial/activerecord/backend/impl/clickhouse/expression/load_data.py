# src/rhosocial/activerecord/backend/impl/clickhouse/expression/load_data.py
"""
ClickHouse-specific LOAD DATA expression.

This module provides ClickHouseLoadDataStatement for ClickHouse's LOAD DATA
INFILE functionality. The statement itself is refused by the dialect's
formatter (ClickHouse has no LOAD DATA), so the expression exists to carry the
would-be statement's parameters as data -- and to say no when rendered.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseLoadDataStatement(BaseExpression):
    """ClickHouse LOAD DATA INFILE expression.

    Collects parameters for LOAD DATA [LOCAL] INFILE statement.
    The actual SQL formatting is done by ClickHouseDialect.format_load_data_statement(),
    which refuses: ClickHouse has no LOAD DATA. The parameters travel anyway,
    as plain JSON scalars -- an artifact carries what the constructor declares,
    and an options *object* has no artifact form (the codec writes nodes,
    scalars, and containers of those two), which is why the former
    ``LoadDataOptions`` dataclass was flattened into these parameters.

    Attributes:
        file_path: Path to the data file
        table: Target table name
        local: Use LOCAL keyword (client-side file)
        replace: Use REPLACE mode (replace existing rows on duplicate key)
        ignore: Use IGNORE mode (ignore duplicate key errors)
        character_set: Character set of the file
        fields_terminated_by: Field terminator string (default: tab)
        fields_enclosed_by: Field enclosure character
        fields_escaped_by: Escape character
        lines_starting_by: Line prefix to skip
        lines_terminated_by: Line terminator string
        ignore_lines: Number of lines to skip at start
        column_list: List of column names for mapping
        set_assignments: SET clause for column transformations
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        file_path: str,
        table: str,
        *,
        local: bool = True,
        replace: bool = False,
        ignore: bool = False,
        character_set: Optional[str] = None,
        fields_terminated_by: Optional[str] = None,
        fields_enclosed_by: Optional[str] = None,
        fields_escaped_by: Optional[str] = None,
        lines_starting_by: Optional[str] = None,
        lines_terminated_by: Optional[str] = None,
        ignore_lines: Optional[int] = None,
        column_list: Optional[List[str]] = None,
        set_assignments: Optional[Dict[str, Any]] = None,
    ):
        """Initialize LOAD DATA expression.

        Args:
            dialect: SQL dialect
            file_path: Path to the data file
            table: Target table name
            local: Use LOCAL keyword (client-side file)
            replace: Use REPLACE mode (replace existing rows on duplicate key)
            ignore: Use IGNORE mode (ignore duplicate key errors)
            character_set: Character set of the file
            fields_terminated_by: Field terminator string (default: tab)
            fields_enclosed_by: Field enclosure character
            fields_escaped_by: Escape character
            lines_starting_by: Line prefix to skip
            lines_terminated_by: Line terminator string
            ignore_lines: Number of lines to skip at start
            column_list: List of column names for mapping
            set_assignments: SET clause for column transformations
        """
        super().__init__(dialect)
        self.file_path = file_path
        self.table = table
        self.local = local
        self.replace = replace
        self.ignore = ignore
        self.character_set = character_set
        self.fields_terminated_by = fields_terminated_by
        self.fields_enclosed_by = fields_enclosed_by
        self.fields_escaped_by = fields_escaped_by
        self.lines_starting_by = lines_starting_by
        self.lines_terminated_by = lines_terminated_by
        self.ignore_lines = ignore_lines
        self.column_list = list(column_list) if column_list is not None else None
        self.set_assignments = set_assignments

    def validate(self, strict: bool = True) -> None:
        """Validate expression parameters.

        Args:
            strict: Enable strict validation (unused but required by base class)

        Raises:
            ValueError: If both replace and ignore are True
            TypeError: If parameters have wrong types
        """
        if not strict:
            return

        if not isinstance(self.file_path, str):
            raise TypeError(f"file_path must be str, got {type(self.file_path)}")

        if not isinstance(self.table, str):
            raise TypeError(f"table must be str, got {type(self.table)}")

        if self.replace and self.ignore:
            raise ValueError("Cannot use both REPLACE and IGNORE in LOAD DATA")

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_load_data_statement"
