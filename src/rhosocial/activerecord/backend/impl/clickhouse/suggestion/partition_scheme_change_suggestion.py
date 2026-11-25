# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_scheme_change_suggestion.py
"""ClickHouse's answer for the partition-scheme-change decision point.

A ClickHouse partition is an inline ``PARTITION BY <expr>`` clause of CREATE
TABLE and has no ``ALTER`` verb to add, remove or rewrite that declaration. A
bare old/new pair of declarations therefore cannot be resolved here: the
honest answer is ``False``.

The point's projections may instead carry a backend-local maintenance plan --
an ``operations`` list in the old or new projection -- for the data-preserving
steps a caller has already chosen. Each recognised name is dispatched to an
*existing* ClickHouse statement node, behind the dialect's own probe for that
verb: ``drop``, ``detach``, ``attach``, ``replace``, ``move``, ``freeze``,
``unfreeze``, ``clear`` and ``optimize``. Every node is an independent statement
(the backend never combines actions into one statement), and no SQL is built
here -- constructors take only values and the dialect formats them.

The five MySQL partition verbs the reference does not support -- REORGANIZE,
EXCHANGE, COALESCE, REMOVE PARTITIONING and SUBPARTITION -- are refused by name
before any node is built, so they can never appear in an emitted chain. An
unknown or malformed request is refused the same way; a missing parameter is
never filled with a guess.
"""

from collections.abc import Mapping
from typing import Any, Optional, Tuple

from ....expression.bases import BaseExpression
from ....suggestion.definitions import PartitionSchemeChangeSuggestion
from ..expression import (
    ClickHouseAttachPartitionStatement,
    ClickHouseClearInPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseDropPartitionStatement,
    ClickHouseFreezePartitionStatement,
    ClickHouseMovePartitionStatement,
    ClickHouseOptimizePartitionStatement,
    ClickHouseReplacePartitionStatement,
    ClickHouseUnfreezePartitionStatement,
)

__all__ = ["ClickHousePartitionSchemeChangeSuggestionMixin"]

#: Names the ALTER TABLE PARTITION reference does not contain. Listed so the
#: refusal is explicit and testable, rather than a side effect of an unknown key.
REFUSED_OPERATIONS = frozenset(
    {
        "reorganize",
        "exchange",
        "coalesce",
        "remove_partitioning",
        "subpartition",
    }
)

_INVALID = object()


def _field(
    params: Mapping, key: str, *, required: bool = False, default: Any = None
) -> Any:
    """Read one non-blank string parameter, or return the invalid sentinel."""
    value = params.get(key)
    if value is None:
        return _INVALID if required else default
    if not isinstance(value, str) or not value.strip():
        return _INVALID
    return value


def _make_drop(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id", required=True)
    schema = _field(params, "schema")
    if _INVALID in (partition_id, schema):
        return None
    return ClickHouseDropPartitionStatement(dialect, table, partition_id, schema=schema)


def _make_detach(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id", required=True)
    schema = _field(params, "schema")
    if _INVALID in (partition_id, schema):
        return None
    return ClickHouseDetachPartitionStatement(dialect, table, partition_id, schema=schema)


def _make_attach(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id", required=True)
    schema = _field(params, "schema")
    if _INVALID in (partition_id, schema):
        return None
    return ClickHouseAttachPartitionStatement(dialect, table, partition_id, schema=schema)


def _make_replace(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id", required=True)
    source_table = _field(params, "source_table", required=True)
    schema = _field(params, "schema")
    source_schema = _field(params, "source_schema")
    if _INVALID in (partition_id, source_table, schema, source_schema):
        return None
    return ClickHouseReplacePartitionStatement(
        dialect,
        table,
        partition_id,
        source_table,
        schema=schema,
        source_schema=source_schema,
    )


def _make_move(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id", required=True)
    destination = _field(params, "destination", required=True)
    target = _field(params, "target", required=True)
    schema = _field(params, "schema")
    target_schema = _field(params, "target_schema")
    if _INVALID in (partition_id, destination, target, schema, target_schema):
        return None
    return ClickHouseMovePartitionStatement(
        dialect,
        table,
        partition_id,
        destination,
        target,
        schema=schema,
        target_schema=target_schema,
    )


def _make_freeze(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id")
    name = _field(params, "backup_name")
    schema = _field(params, "schema")
    if _INVALID in (partition_id, name, schema):
        return None
    return ClickHouseFreezePartitionStatement(
        dialect, table, partition_id, name, schema=schema
    )


def _make_unfreeze(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    name = _field(params, "backup_name", required=True)
    partition_id = _field(params, "partition_id")
    schema = _field(params, "schema")
    if _INVALID in (name, partition_id, schema):
        return None
    return ClickHouseUnfreezePartitionStatement(
        dialect, table, partition_id, name, schema=schema
    )


def _make_clear(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    kind = _field(params, "kind", required=True)
    name = _field(params, "name", required=True)
    partition_id = _field(params, "partition_id")
    schema = _field(params, "schema")
    if _INVALID in (kind, name, partition_id, schema):
        return None
    return ClickHouseClearInPartitionStatement(
        dialect, table, kind, name, partition_id, schema=schema
    )


def _make_optimize(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id")
    schema = _field(params, "schema")
    final = params.get("final", True)
    if _INVALID in (partition_id, schema) or not isinstance(final, bool):
        return None
    return ClickHouseOptimizePartitionStatement(
        dialect, table, partition_id, final, schema=schema
    )


#: operation name -> (capability probe, existing-node factory).
_OPERATIONS = {
    "drop": ("supports_drop_partition", _make_drop),
    "detach": ("supports_detach_partition", _make_detach),
    "attach": ("supports_attach_partition", _make_attach),
    "replace": ("supports_replace_partition", _make_replace),
    "move": ("supports_move_partition", _make_move),
    "freeze": ("supports_freeze_partition", _make_freeze),
    "unfreeze": ("supports_unfreeze_partition", _make_unfreeze),
    "clear": ("supports_clear_in_partition", _make_clear),
    "optimize": ("supports_optimize_partition_final", _make_optimize),
}


def _requests(projection: Any) -> Tuple[Any, ...]:
    """Read operation requests from one old/new projection, if it carries any."""
    if isinstance(projection, str):
        return (projection,)
    if isinstance(projection, Mapping):
        raw = projection.get("operations")
        if isinstance(raw, (str, Mapping)):
            return (raw,)
        if isinstance(raw, (list, tuple)):
            return tuple(raw)
    return ()


def _operation_name(request: Any) -> Optional[str]:
    """Normalise a request's operation name; only strings are accepted."""
    if isinstance(request, str):
        raw = request
    elif isinstance(request, Mapping):
        raw = request.get("operation")
    else:
        return None
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip().lower().replace("-", "_").replace(" ", "_")


class ClickHousePartitionSchemeChangeSuggestionMixin:
    """Suggest gated ClickHouse partition maintenance operations, or refuse.

    Plain class, not a protocol subclass: inheriting the runtime-checkable
    protocol would insert ``Protocol.__init__`` into the dialect's MRO and
    swallow constructor arguments, as the other backend mixins document.
    """

    def suggest_partition_scheme_change(
        self, point: PartitionSchemeChangeSuggestion
    ) -> PartitionSchemeChangeSuggestion:
        """Return a real node chain, ``False`` for a bare change, ``None`` if equal."""
        table_name = point.table_name
        if not isinstance(table_name, str) or not table_name.strip():
            return PartitionSchemeChangeSuggestion(operations=False)
        if point.old_partition == point.new_partition:
            return PartitionSchemeChangeSuggestion(operations=None)

        requests = _requests(point.old_partition) + _requests(point.new_partition)
        if not requests:
            # A plain declaration change has in-place spelling on ClickHouse.
            return PartitionSchemeChangeSuggestion(operations=False)

        chain = []
        for request in requests:
            name = _operation_name(request)
            if name is None or name in REFUSED_OPERATIONS or name not in _OPERATIONS:
                return PartitionSchemeChangeSuggestion(operations=False)
            probe, factory = _OPERATIONS[name]
            if not bool(getattr(self, probe)()):  # type: ignore[attr-defined]
                return PartitionSchemeChangeSuggestion(operations=False)
            node = factory(self, table_name, request if isinstance(request, Mapping) else {})
            if not isinstance(node, BaseExpression):
                return PartitionSchemeChangeSuggestion(operations=False)
            chain.append(node)
        return PartitionSchemeChangeSuggestion(operations=tuple(chain))
