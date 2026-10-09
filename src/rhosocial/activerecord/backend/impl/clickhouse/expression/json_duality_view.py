# src/rhosocial/activerecord/backend/impl/clickhouse/expression/json_duality_view.py
"""
ClickHouse JSON Duality View expressions.

Provides expression classes for ``CREATE JSON RELATIONAL DUALITY VIEW`` and
``DROP`` of it, plus the dataclasses describing a ``JSON_DUALITY_OBJECT`` call.

**ClickHouse has no duality views at any version, and there is nothing to
name a version for.** Three measurements on 26.7.3.19, each an inventory rather
than an absence of evidence:

* ``CREATE JSON RELATIONAL DUALITY VIEW v AS SELECT 1`` —
  ``Code: 62. DB::Exception: Syntax error: failed at position 8 (JSON): JSON
  RELATIONAL DUALITY VIEW v AS SELECT 1. Expected one of: OR REPLACE,
  TEMPORARY, TABLE, DATABASE, sql security, DEFINER, SQL SECURITY, MATERIALIZED,
  VIEW, DICTIONARY, WINDOW, USER, ROLE, QUOTA, POLICY, ROW POLICY, MASKING
  POLICY, SETTINGS PROFILE, PROFILE, FUNCTION, WORKLOAD, RESOURCE, NAMED
  COLLECTION, UNIQUE, INDEX, HYPOTHETICAL. (SYNTAX_ERROR)`` — that list is the
  server enumerating every object ``CREATE`` can make, and a duality view is not
  on it.
* ``SELECT JSON_DUALITY_OBJECT(1)`` — ``Code: 46. DB::Exception: Function with
  name `JSON_DUALITY_OBJECT` does not exist. (UNKNOWN_FUNCTION)``, and
  ``SELECT count() FROM system.functions WHERE name ILIKE '%DUALITY%'`` is 0.
* ``https://clickhouse.com/docs/reference/statements/create/table`` documents
  exactly two table-constraint forms — ``CONSTRAINT name CHECK expr`` and
  ``CONSTRAINT name ASSUME expr`` — and no duality view.

So the switch stays fail-fast rather than becoming a version gate:
``supports_json_duality_view()`` is ``False`` and
``format_create_json_duality_view_statement`` raises
``UnsupportedFeatureError``. What the server does have for reacting to a row is
``CREATE FUNCTION ... AS`` (a SQL UDF) plus a MATERIALIZED VIEW, and what it has
for relational JSON is the ``JSON`` column type with the ``JSONExtract*``
family.
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
    """``CREATE JSON RELATIONAL DUALITY VIEW`` — a statement ClickHouse does not have.

    Kept as a fail-fast switch, not as a renderer: ``to_sql()`` raises
    ``UnsupportedFeatureError`` through the dialect, naming
    ``CREATE FUNCTION ... AS`` plus a MATERIALIZED VIEW as the ClickHouse way to
    react to a row. There is no ClickHouse version at which this statement
    starts parsing — see the module docstring for the three measurements.

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

    @property
    def format_method(self) -> str:
        return "format_create_json_duality_view_statement"


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

    @property
    def format_method(self) -> str:
        return "format_drop_json_duality_view_statement"
