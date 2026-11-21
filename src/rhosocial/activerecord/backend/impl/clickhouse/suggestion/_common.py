# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/_common.py
"""Shared helpers and the common base for ClickHouse's partition suggestions.

Each of the eight partition-lifecycle suggestion mixins reads a small,
documented set of fields from an opaque ``plan`` and turns them into real
expression nodes. The plan-reading helper (``_get``) and the helpers that build
a ``Table`` or a ``PARTITION BY`` expression tuple are used by more than one
mixin, so they live here on a single base class that all eight mixins inherit.
Splitting them out of the former single ``partition.py`` changes no behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Tuple

from ....expression.bases import BaseExpression
from ....expression.objects import Table

__all__ = ["ClickHousePartitionSuggestionBase", "_get"]


def _get(plan: Any, name: str, default: Any = None) -> Any:
    """Read one field from a mapping-shaped or attribute-shaped plan."""
    if plan is None:
        return default
    if isinstance(plan, Mapping):
        return plan.get(name, default)
    return getattr(plan, name, default)


class ClickHousePartitionSuggestionBase:
    """Plan-reading helpers shared by ClickHouse's eight suggestion mixins."""

    def _suggestion_table(self, plan: Any) -> Optional[Table]:
        """Build a ``Table`` from ``plan.table`` when it names one."""
        target = _get(plan, "table")
        if isinstance(target, Table):
            return target
        if isinstance(target, str) and target.strip():
            return Table(self, target)
        return None

    def _suggestion_table_name(self, plan: Any) -> Optional[str]:
        """Return a plain table name for the ``PARTITION ID`` statements."""
        target = _get(plan, "table")
        if isinstance(target, Table):
            name = getattr(target, "name", None)
            return name if isinstance(name, str) and name.strip() else None
        if isinstance(target, str) and target.strip():
            return target
        return None

    def _suggestion_expressions(self, plan: Any) -> Optional[Tuple[BaseExpression, ...]]:
        """Return the build's ``PARTITION BY`` expression nodes, if valid."""
        raw = _get(plan, "expressions")
        if raw is None:
            raw = _get(plan, "keys")
        if isinstance(raw, BaseExpression):
            return (raw,)
        if (
            isinstance(raw, (list, tuple))
            and raw
            and all(isinstance(item, BaseExpression) for item in raw)
        ):
            return tuple(raw)
        return None
