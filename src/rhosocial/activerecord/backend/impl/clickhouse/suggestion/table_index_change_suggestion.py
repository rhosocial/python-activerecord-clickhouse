# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/table_index_change_suggestion.py
"""ClickHouse's answer for the table-index-change decision point.

ClickHouse does have ``ALTER TABLE ... ADD INDEX`` / ``DROP INDEX`` for its
data-skipping indexes; the official reference documents both, and the live
execute test at ``feature/backend/execute/query/test_query_features.py`` runs
them against 26.7.3.19. What used to be missing was an expression node for the
spelling: the only index node was the inline ``ClickHouseIndexDefinition`` and
core's ``AddIndexAction`` / ``DropIndexAction`` render MySQL's form. That gap is
closed by :class:`~..expression.statements.index.ClickHouseAddIndexStatement` and
:class:`~..expression.statements.index.ClickHouseDropIndexStatement`.

This mixin now answers with a real chain when it can build it honestly:

* a DROP needs only a name, which the frozen projection carries;
* an ADD needs the index body (expression, type, granularity), which only a
  live ``IndexDefinition`` declaration carries -- a frozen projection does not,
  so an add that cannot be rebuilt returns ``False`` rather than guessing;
* a changed declaration is dropped before it is added, because ClickHouse has
  no ``MODIFY INDEX`` (the same shape as ``MODIFY CONSTRAINT``).

Every destructive alternative (rebuilding the table, moving data) is refused:
the only statements this point emits are the two skip-index metadata actions.
"""

from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Tuple

from ....dialect.exceptions import UnsupportedFeatureError
from ....expression.bases.bases import BaseExpression
from ....expression.column_types.column import Column
from ....expression.statements.ddl_table import IndexDefinition
from ....suggestion.definitions import TableIndexChangeSuggestion
from ..expression.statements.index import (
    ClickHouseAddIndexStatement,
    ClickHouseDropIndexStatement,
)

__all__ = ["ClickHouseTableIndexChangeSuggestionMixin"]


#: Chains that would destroy or relocate table data are never emitted here.
#: The two index statements only touch index metadata / index files, so a
#: rendered chain containing any of these fragments is a defect in the wiring
#: rather than a legitimate answer, and is refused defensively.
_FORBIDDEN_SQL = (
    "DROP TABLE",
    "DROP DATABASE",
    "DROP SCHEMA",
    "REPLACE PARTITION",
    "MOVE PARTITION",
    "DELETE FROM",
    "INSERT INTO",
)


def _declared_name(projection: Any) -> Optional[str]:
    """Read an index name from a node, a mapping or a frozen projection."""
    if isinstance(projection, IndexDefinition):
        name = projection.name
        return name if isinstance(name, str) and name.strip() else None
    if isinstance(projection, Mapping):
        name = projection.get("name")
        return name if isinstance(name, str) and name.strip() else None
    if isinstance(projection, (tuple, list)):
        for item in projection:
            if isinstance(item, (tuple, list)) and len(item) == 2 and item[0] == "name":
                name = item[1]
                return name if isinstance(name, str) and name.strip() else None
            nested = _declared_name(item)
            if nested is not None:
                return nested
    return None


def _projections(value: Any) -> Tuple[Any, ...]:
    """Normalise a point's index field to a tuple of projections."""
    if isinstance(value, (tuple, list)):
        return tuple(value)
    return (value,) if value is not None else ()


def _live_declarations(value: Any) -> Tuple[IndexDefinition, ...]:
    """Keep only real index declarations; ignore ``None`` and stray values."""
    if isinstance(value, (tuple, list)):
        return tuple(item for item in value if isinstance(item, IndexDefinition))
    return (value,) if isinstance(value, IndexDefinition) else ()


class ClickHouseTableIndexChangeSuggestionMixin:
    """Suggest real ADD/DROP INDEX statements for skip-index changes.

    Plain class, not a protocol subclass: see the other backend suggestion
    mixins. Inheriting the protocol would put ``Protocol.__init__`` ahead of
    ``SQLDialectBase`` in the dialect's MRO; structural presence is enough.
    """

    def suggest_table_index_change(
        self, point: TableIndexChangeSuggestion
    ) -> TableIndexChangeSuggestion:
        """Return a drop/add chain, ``None`` for no change, ``False`` otherwise."""
        table_name = point.table_name
        if not isinstance(table_name, str) or not table_name.strip():
            return TableIndexChangeSuggestion(operations=False)

        old_items = _projections(point.old_indexes)
        new_items = _projections(point.new_indexes)
        if old_items == new_items:
            return TableIndexChangeSuggestion(operations=None)

        old_by_name: Dict[str, Any] = {}
        new_by_name: Dict[str, Any] = {}
        for items, target in ((old_items, old_by_name), (new_items, new_by_name)):
            for item in items:
                name = _declared_name(item)
                if name is None or name in target:
                    # Unnamed or duplicated: DROP INDEX <name> cannot be aimed.
                    return TableIndexChangeSuggestion(operations=False)
                target[name] = item

        removed = [name for name in old_by_name if name not in new_by_name]
        added = [name for name in new_by_name if name not in old_by_name]
        modified = [
            name
            for name in old_by_name
            if name in new_by_name and old_by_name[name] != new_by_name[name]
        ]
        if not (removed or added or modified):
            return TableIndexChangeSuggestion(operations=None)

        # Gate on the capability switches this backend actually answers, so a
        # caller who turns one off never receives a chain it cannot render.
        if (removed or modified) and not self.supports_drop_index():  # type: ignore[attr-defined]
            return TableIndexChangeSuggestion(operations=False)
        if (added or modified) and not self.supports_create_index():  # type: ignore[attr-defined]
            return TableIndexChangeSuggestion(operations=False)

        new_declarations = {
            decl.name: decl
            for decl in _live_declarations(point.new_index_declarations)
            if isinstance(decl.name, str)
        }

        operations: List[BaseExpression] = []
        for name in removed + modified:
            operations.append(
                ClickHouseDropIndexStatement(
                    self,
                    table_name,
                    name,
                    if_exists=bool(self.supports_index_if_exists()),  # type: ignore[attr-defined]
                )
            )

        for name in added + modified:
            declaration = new_declarations.get(name)
            if declaration is None:
                return TableIndexChangeSuggestion(operations=False)
            body = self._index_add_body(declaration)
            if body is None:
                # Frozen projections and declarations the node cannot express
                # (multiple columns, UNIQUE, no TYPE) are refused, not guessed.
                return TableIndexChangeSuggestion(operations=False)
            expression, index_type, granularity, if_not_exists = body
            operations.append(
                ClickHouseAddIndexStatement(
                    self,
                    table_name,
                    name,
                    expression,
                    type=index_type,
                    granularity=granularity,
                    if_not_exists=if_not_exists,
                )
            )

        # Defensive safety guard: a change to index definitions must never
        # grow into a table drop or a data-moving statement. A node that cannot
        # render at all is an unaddressable answer, not an exception to raise.
        for operation in operations:
            try:
                sql = operation.to_sql()[0].upper()
            except UnsupportedFeatureError:
                return TableIndexChangeSuggestion(operations=False)
            if any(fragment in sql for fragment in _FORBIDDEN_SQL):
                return TableIndexChangeSuggestion(operations=False)

        return TableIndexChangeSuggestion(operations=tuple(operations))

    def _index_add_body(
        self, declaration: IndexDefinition
    ) -> Optional[Tuple[BaseExpression, str, Optional[int], bool]]:
        """Project a live index declaration into the ADD node's body fields.

        ``None`` means the declaration cannot be expressed by the ClickHouse
        ADD node: there is no single expression to carry, no TYPE, or a trait
        (UNIQUE) the engine does not have. The check runs before any statement
        is emitted, so an unexpressible add never leaves a partial chain.
        """
        if declaration.unique:
            return None
        columns = declaration.columns
        if len(columns) != 1:
            # A skip index takes one expression. A parenthesised column list is
            # the inline CREATE TABLE shape, not an ALTER TABLE expression.
            return None
        column = columns[0]
        if isinstance(column, BaseExpression):
            expression = column
        elif isinstance(column, str) and column.strip():
            expression = Column(self, column)
        else:
            return None
        index_type = declaration.type
        if not isinstance(index_type, str) or not index_type.strip():
            return None
        granularity = vars(declaration).get("granularity", None)
        if_not_exists = bool(declaration.if_not_exists)
        if if_not_exists and not self.supports_index_if_not_exists():  # type: ignore[attr-defined]
            return None
        return expression, index_type, granularity, if_not_exists
