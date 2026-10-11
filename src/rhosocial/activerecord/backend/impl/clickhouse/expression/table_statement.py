# src/rhosocial/activerecord/backend/impl/clickhouse/expression/table_statement.py
"""MySQL's ``TABLE`` / ``VALUES`` simplified statements — ClickHouse has neither.

MySQL 8.0.19 added two query forms::

    TABLE <table> [ORDER BY ...] [LIMIT ...]
    VALUES ROW(...), ROW(...) [ORDER BY ...] [LIMIT ...]

where ``TABLE`` is a shortcut for ``SELECT * FROM <table>`` and ``VALUES`` is a
row-list table-value constructor. **ClickHouse has no such statements at any
version**, so there is no version floor to name. On 26.7.3.19:

* ``TABLE system.metrics`` — ``Code: 62. DB::Exception: Syntax error: failed at
  position 1 (TABLE): TABLE system.metrics. Expected one of: Query, Query with
  output, EXPLAIN, EXPLAIN, SELECT query, possibly with UNION, list of union
  elements, SELECT query, subquery, possibly with UNION, SELECT or EXPLAIN
  subquery, SELECT query, WITH, FROM, SELECT, SHOW CREATE QUOTA query, SHOW
  CREATE, SHOW [FULL] [TEMPORARY] TABLES|DATABASES|CLUSTERS|CLUSTER|MERGES
  'name' [[NOT] [I]LIKE 'str'] [LIMIT expr], SHOW, SHOW COLUMNS query, SHOW
  ENGINES query, ... (SYNTAX_ERROR)``. That is the server listing every
  top-level statement it accepts, and ``TABLE`` is not among them — nor is
  ``VALUES``.
* ``SELECT * FROM VALUES(1,2,3)`` **does** work, and
  ``system.table_functions`` lists ``values``. But that is the ``values``
  *table function* taking a comma-separated list of scalar values, not MySQL's
  ``VALUES ROW(...), ROW(...)`` statement: ``SELECT * FROM
  VALUES(ROW(1,2), ROW(3,4))`` is ``Code: 46. DB::Exception: Function with name
  `ROW` does not exist. In scope SELECT * FROM `VALUES`(ROW(1, 2), ROW(3, 4)).
  Maybe you meant: ['now','pow']. (UNKNOWN_FUNCTION)`` — ClickHouse has no
  ``ROW`` constructor function at all.

So both expression classes below are fail-fast switches:
``supports_table_statement()`` and ``supports_values_table_constructor()`` are
``False``, and ``format_table_statement`` / ``format_values_statement`` raise
``UnsupportedFeatureError`` naming ``SELECT * FROM <table>`` and
``SELECT ... UNION ALL SELECT ...`` as the ClickHouse spellings.
"""

from typing import Any, List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class ClickHouseBaseTableStatement(BaseExpression):
    """Common base for the ``TABLE``/``VALUES`` simplified statements.

    Attributes:
        order_by: Optional list of column names for the ORDER BY clause.
        limit: Optional LIMIT row count.
        offset: Optional OFFSET row count.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ):
        super().__init__(dialect)
        self.order_by: List[str] = list(order_by or [])
        self.limit: Optional[int] = limit
        self.offset: Optional[int] = offset

    def _validate_common(self) -> None:
        if self.limit is not None and self.limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if self.offset is not None and self.offset < 0:
            raise ValueError("offset must be a non-negative integer")


class ClickHouseTableExpression(ClickHouseBaseTableStatement):
    """MySQL's ``TABLE <table>`` simplified SELECT — a statement ClickHouse does not have.

    Fail-fast switch: ``to_sql()`` raises ``UnsupportedFeatureError`` through the
    dialect, naming ``SELECT * FROM <table>``. No ClickHouse release parses it —
    see the module docstring.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: str,
        *,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ):
        super().__init__(
            dialect,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        self.table: str = table

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.table, str):
            raise TypeError("table must be a string")
        self._validate_common()

    @property
    def format_method(self) -> str:
        return "format_table_statement"


class ClickHouseValuesExpression(ClickHouseBaseTableStatement):
    """MySQL's ``VALUES ROW(...), ...`` table value constructor — not in ClickHouse.

    Fail-fast switch: ``to_sql()`` raises ``UnsupportedFeatureError`` through the
    dialect, naming ``SELECT ... UNION ALL SELECT ...``. ClickHouse's ``values``
    *table function* is a different thing and is not what this models — it takes
    bare scalar values and there is no ``ROW()`` constructor to pass it; see the
    module docstring.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        rows: List[List[Any]],
        *,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ):
        super().__init__(
            dialect,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        self.rows: List[List[Any]] = [list(row) for row in rows]

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.rows:
            raise ValueError("VALUES requires at least one ROW(...)")
        self._validate_common()

    @property
    def format_method(self) -> str:
        return "format_values_statement"