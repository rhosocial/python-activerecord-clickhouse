# src/rhosocial/activerecord/backend/impl/clickhouse/expression/json_duality_view.py
"""
ClickHouse JSON Duality View expressions (ClickHouse 9.7+).

Provides expression classes for CREATE/DROP JSON RELATIONAL DUALITY VIEW
and the JSON_DUALITY_OBJECT function used within them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class DualityViewDMLTag(Enum):
    """DML permission tags for JSON_DUALITY_OBJECT."""

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class DualityColumnMapping:
    """A key-column mapping within JSON_DUALITY_OBJECT.

    Attributes:
        json_key: JSON key name in the output document
        column_expr: Column expression (e.g., 'table.column')
    """

    json_key: str
    column_expr: str


@dataclass
class DualityNestedMapping:
    """A nested object/array mapping using a subquery.

    Attributes:
        json_key: JSON key name for the nested data
        subquery: The nested SELECT ... JSON_ARRAYAGG(JSON_DUALITY_OBJECT(...)) subquery expression
    """

    json_key: str
    subquery: "DualityObjectSpec"


@dataclass
class DualityObjectSpec:
    """Specification for a JSON_DUALITY_OBJECT call.

    Attributes:
        tags: DML permission tags (INSERT, UPDATE, DELETE). Empty = read-only.
        columns: Direct column mappings
        nested: Nested object/array mappings
        from_table: Source table name
        from_alias: Optional table alias
        join_condition: WHERE clause for nested subqueries (e.g., 'child.fk = parent.pk')
    """

    tags: List[DualityViewDMLTag] = field(default_factory=list)
    columns: List[DualityColumnMapping] = field(default_factory=list)
    nested: List[DualityNestedMapping] = field(default_factory=list)
    from_table: Optional[str] = None
    from_alias: Optional[str] = None
    join_condition: Optional[str] = None


class CreateJsonDualityViewExpression(BaseExpression):
    """CREATE JSON RELATIONAL DUALITY VIEW expression (ClickHouse 9.7+).

    Attributes:
        view_name: Name of the duality view
        root_spec: Root-level DualityObjectSpec
        replace: If True, use CREATE OR REPLACE
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        view_name: str,
        root_spec: DualityObjectSpec,
        replace: bool = False,
    ):
        super().__init__(dialect)
        self.view_name = view_name
        self.root_spec = root_spec
        self.replace = replace

    def to_sql(self):
        return self.dialect.format_create_json_duality_view_statement(self)


class DropJsonDualityViewExpression(BaseExpression):
    """DROP VIEW expression for JSON Duality Views.

    Uses standard DROP VIEW syntax since ClickHouse has no special DROP for duality views.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        view_name: str,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        self.view_name = view_name
        self.if_exists = if_exists

    def to_sql(self):
        return self.dialect.format_drop_json_duality_view_statement(self)
