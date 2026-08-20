# src/rhosocial/activerecord/backend/impl/clickhouse/expression/table_statement.py
"""ClickHouse TABLE statement and VALUES table-value constructor expressions.

ClickHouse 8.0+ supports two simplified query forms:

    TABLE <table> [ORDER BY ...] [LIMIT ...]
    VALUES ROW(...), ROW(...) [ORDER BY ...] [LIMIT ...]

``TABLE`` is a shortcut for ``SELECT * FROM <table>`` and ``VALUES`` lets a
row list be used as a table value constructor.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseBaseTableStatement(BaseExpression):
    """Common base for the ``TABLE``/``VALUES`` simplified statements.

    Attributes:
        order_by: Optional list of column names for the ORDER BY clause.
        limit: Optional LIMIT row count.
        offset: Optional OFFSET row count.
        dialect_options: Additional ClickHouse-specific options.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.order_by: List[str] = list(order_by or [])
        self.limit: Optional[int] = limit
        self.offset: Optional[int] = offset
        self.dialect_options: Dict[str, Any] = dialect_options or {}

    def _validate_common(self) -> None:
        if self.limit is not None and self.limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if self.offset is not None and self.offset < 0:
            raise ValueError("offset must be a non-negative integer")


class ClickHouseTableExpression(ClickHouseBaseTableStatement):
    """Represent the ClickHouse ``TABLE <table>`` simplified SELECT statement."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table_name: str,
        *,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            dialect,
            order_by=order_by,
            limit=limit,
            offset=offset,
            dialect_options=dialect_options,
        )
        self.table_name: str = table_name

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.table_name, str):
            raise TypeError("table_name must be a string")
        self._validate_common()

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_table_statement(self)


class ClickHouseValuesExpression(ClickHouseBaseTableStatement):
    """Represent the ClickHouse ``VALUES ROW(...), ...`` table value constructor."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        rows: List[List[Any]],
        *,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            dialect,
            order_by=order_by,
            limit=limit,
            offset=offset,
            dialect_options=dialect_options,
        )
        self.rows: List[List[Any]] = [list(row) for row in rows]

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.rows:
            raise ValueError("VALUES requires at least one ROW(...)")
        self._validate_common()

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_values_statement(self)