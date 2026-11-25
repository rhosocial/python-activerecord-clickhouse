# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/table_constraint_change_suggestion.py
"""ClickHouse's answer for the table-constraint-change decision point.

ClickHouse 26.7.3.19 accepts two table-constraint lifecycle commands and no
others: ``ADD CONSTRAINT <name> CHECK|ASSUME <expr>`` and
``DROP CONSTRAINT [IF EXISTS] <name>``. The probes
``supports_add_constraint()`` / ``supports_drop_constraint()`` are ``True`` for
exactly that reason; ``MODIFY CONSTRAINT`` is refused by
``supports_alter_constraint()`` (the recorded substitute is drop + add), and
every other kind -- PRIMARY KEY, UNIQUE, FOREIGN KEY -- is a Code 62 at ADD
time. Core models only CHECK among the two accepted kinds (ASSUME has no
branch class), so CHECK is the only kind this suggestion may add.

The point carries *frozen projections*, not necessarily expression nodes. A
drop needs only a name and can be built from a projection; an add needs a real
:class:`~...expression.statements.ddl_table.TableConstraint` node with a CHECK
branch, because neither SQL text nor a predicate can be recovered from a
frozen projection. When an add cannot be rebuilt honestly, the whole answer is
``False`` rather than a partial chain that silently drops a constraint. Each
returned operation is an ``AlterTableStatement`` carrying exactly one action
(the backend never packs two actions into one statement).
"""

from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Tuple

from ....expression.objects import Table
from ....expression.statements.ddl_alter import (
    AlterTableStatement,
    AddTableConstraintAction,
    DropTableConstraintAction,
)
from ....expression.statements.ddl_table import TableCheckConstraint, TableConstraint
from ....suggestion.definitions import TableConstraintChangeSuggestion

__all__ = ["ClickHouseTableConstraintChangeSuggestionMixin"]


def _declared_name(projection: Any) -> Optional[str]:
    """Read a constraint name from a node, a mapping or a frozen projection.

    ``schema_change`` freezes declarations through ``_freeze``, so a real point
    can hold ``("params", (... ("name", "ck") ...))`` instead of a node. Only
    the name is needed for a DROP; the expression is never reconstructed from
    a frozen projection.
    """
    if isinstance(projection, TableConstraint):
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
    """Normalise a point's constraint field to a tuple of projections."""
    if isinstance(value, (tuple, list)):
        return tuple(value)
    return (value,) if value is not None else ()


class ClickHouseTableConstraintChangeSuggestionMixin:
    """Suggest real ADD/DROP CONSTRAINT statements for CHECK changes.

    Plain class, not a protocol subclass: the other backend suggestion mixins
    follow that rule because ``Protocol.__init__`` would otherwise sit ahead of
    ``SQLDialectBase`` in the dialect's MRO and swallow constructor arguments.
    The runtime-checkable protocol is satisfied structurally.
    """

    def suggest_table_constraint_change(
        self, point: TableConstraintChangeSuggestion
    ) -> TableConstraintChangeSuggestion:
        """Return a drop-then-add chain, ``None`` for no change, ``False`` otherwise."""
        table_name = point.table_name
        if not isinstance(table_name, str) or not table_name.strip():
            return TableConstraintChangeSuggestion(operations=False)

        old_items = _projections(point.old_constraints)
        new_items = _projections(point.new_constraints)
        if old_items == new_items:
            return TableConstraintChangeSuggestion(operations=None)

        old_by_name: Dict[str, Any] = {}
        new_by_name: Dict[str, Any] = {}
        for items, target in ((old_items, old_by_name), (new_items, new_by_name)):
            for item in items:
                name = _declared_name(item)
                if name is None or name in target:
                    # Unnamed, duplicated or unreadable: no safe way to address
                    # the constraint with DROP CONSTRAINT <name>.
                    return TableConstraintChangeSuggestion(operations=False)
                target[name] = item

        removed = [name for name in old_by_name if name not in new_by_name]
        added = [name for name in new_by_name if name not in old_by_name]
        modified = [
            name
            for name in old_by_name
            if name in new_by_name and old_by_name[name] != new_by_name[name]
        ]
        if not (removed or added or modified):
            return TableConstraintChangeSuggestion(operations=None)

        # A changed declaration must be dropped before it is added: ClickHouse
        # has no MODIFY CONSTRAINT (supports_alter_constraint() is False).
        drops = removed + modified
        adds = added + modified
        if drops and not self.supports_drop_constraint():  # type: ignore[attr-defined]
            return TableConstraintChangeSuggestion(operations=False)
        if adds and not self.supports_add_constraint():  # type: ignore[attr-defined]
            return TableConstraintChangeSuggestion(operations=False)

        table = Table(self, table_name)
        if_exists = bool(self.supports_drop_constraint_if_exists())  # type: ignore[attr-defined]
        operations: List[AlterTableStatement] = [
            AlterTableStatement(
                self,
                table,
                [DropTableConstraintAction(self, name, if_exists=if_exists)],
            )
            for name in drops
        ]
        for name in adds:
            constraint = new_by_name[name]
            if not isinstance(constraint, TableConstraint) or not isinstance(
                constraint.branch, TableCheckConstraint
            ):
                # A frozen projection carries no predicate; only a real CHECK
                # node can produce SQL the server accepts. Other kinds are
                # refused at ADD CONSTRAINT time anyway.
                return TableConstraintChangeSuggestion(operations=False)
            operations.append(
                AlterTableStatement(
                    self,
                    table,
                    [AddTableConstraintAction(self, constraint)],
                )
            )
        return TableConstraintChangeSuggestion(operations=tuple(operations))
