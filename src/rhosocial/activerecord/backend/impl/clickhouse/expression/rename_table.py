# src/rhosocial/activerecord/backend/impl/clickhouse/expression/rename_table.py
"""ClickHouse RENAME TABLE statement expression.

ClickHouse supports atomic renaming of one or more tables in a single statement:

    RENAME TABLE t1 TO t2 [, t3 TO t4, ...]

This is distinct from ``ALTER TABLE ... RENAME TO`` which only renames a
single table. The statement is atomic: all renames either succeed or fail
together.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseRenameTableExpression(BaseExpression):
    """Represent a ClickHouse ``RENAME TABLE ...`` atomic multi-table statement.

    Attributes:
        renames: Sequence of ``(old_name, new_name)`` table name pairs.
        dialect_options: Additional ClickHouse-specific options.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        renames: List[Tuple[str, str]],
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.renames: List[Tuple[str, str]] = list(renames)
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    def validate(self, strict: bool = True) -> None:
        """Validate the rename pair list.

        Raises:
            ValueError: If the rename list is empty or contains an invalid pair.
        """
        if not strict:
            return
        if not self.renames:
            raise ValueError("RENAME TABLE requires at least one <table> TO <table> pair")
        for pair in self.renames:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError(f"Invalid rename pair: {pair!r}")
            old_name, new_name = pair
            if not isinstance(old_name, str) or not isinstance(new_name, str):
                raise TypeError("Rename table names must be strings")

    def to_sql(self) -> Tuple[str, tuple]:
        """Generate SQL by delegating to the dialect."""
        return self.dialect.format_rename_table_statement(self)