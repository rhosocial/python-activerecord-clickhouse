# src/rhosocial/activerecord/backend/impl/clickhouse/suggestion/partition_scheme_change_suggestion.py
"""ClickHouse's answer for the partition-scheme-change decision point.

A ClickHouse partition is an inline ``PARTITION BY <expr>`` clause of CREATE
TABLE and has no ``ALTER`` verb to add, remove or rewrite that declaration. A
bare old/new pair of declarations therefore cannot be resolved here: the
honest answer is ``False``.

The point's projections may instead carry a backend-local maintenance plan --
an ``operations`` list in the old or new projection -- for the data-preserving
steps a caller has already chosen. A scheme-change point never authorises
destroying or relocating rows: ``drop`` (deletes a partition), ``replace``
(overwrites the partition's rows from a source table), ``move`` (deletes them
from the source table) and ``clear`` (resets column/index values) are refused.
``detach`` is emitted only when the same chain later attaches that partition
back; a standalone ``detach`` or an ``attach`` without its own prior ``detach``
is refused. ``freeze``, ``unfreeze`` and ``optimize`` leave the table's rows in
place and are dispatched to existing nodes behind the dialect's own probe.

Every emitted node is an independent statement (the backend never combines
actions into one statement), and no SQL is built here -- constructors take only
values and the dialect formats them. The five MySQL partition verbs the
reference does not support -- REORGANIZE, EXCHANGE, COALESCE, REMOVE
PARTITIONING and SUBPARTITION -- are refused by name before any node is built.
An unknown or malformed request is refused the same way; a missing parameter
is never filled with a guess.
"""

from collections.abc import Mapping
from typing import Any, Optional, Tuple

from ....expression.bases import BaseExpression
from ....suggestion.definitions import PartitionSchemeChangeSuggestion
from ..expression import (
    ClickHouseAttachPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseFreezePartitionStatement,
    ClickHouseOptimizePartitionStatement,
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

#: Operations that rewrite, export or reset stored rows. ClickHouse's own
#: reference confirms DROP deletes the partition, REPLACE FROM overwrites the
#: destination partition, MOVE TO TABLE deletes the rows from the source and
#: CLEAR COLUMN/INDEX IN PARTITION resets stored values. A declaration change
#: authorises none of them.
_DATA_CHANGING_OPERATIONS = frozenset({"drop", "replace", "move", "clear"})


def _refuse_data_changing_operation() -> PartitionSchemeChangeSuggestion:
    """Decline destructive or data-moving operations for a scheme-change point.

    These operations require an explicit maintenance request or a data-preserving
    migration plan, not a scheme-change point. An old/new partition declaration
    says nothing about which rows may be deleted, overwritten, moved or reset,
    so even a dialect that supports the statement must not emit it here.
    """
    return PartitionSchemeChangeSuggestion(operations=False)


def _field(params: Mapping, key: str, *, required: bool = False, default: Any = None) -> Any:
    """Read one non-blank string parameter, or return the invalid sentinel."""
    value = params.get(key)
    if value is None:
        return _INVALID if required else default
    if not isinstance(value, str) or not value.strip():
        return _INVALID
    return value


def _make_detach(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    """Move a partition aside, only as part of a chain that attaches it back.

    ClickHouse's DETACH forgets the partition until ATTACH reads it from the
    ``detached`` directory; the pairing check in the mixin enforces that.
    """
    partition_id = _field(params, "partition_id", required=True)
    schema = _field(params, "schema")
    if _INVALID in (partition_id, schema):
        return None
    return ClickHouseDetachPartitionStatement(dialect, table, partition_id, schema=schema)


def _make_attach(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    """Return a detached partition to the table.

    Emitted only for an id this same chain detached, so a scheme-change answer
    never pulls in data left outside the table by somebody else.
    """
    partition_id = _field(params, "partition_id", required=True)
    schema = _field(params, "schema")
    if _INVALID in (partition_id, schema):
        return None
    return ClickHouseAttachPartitionStatement(dialect, table, partition_id, schema=schema)


def _make_freeze(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id")
    name = _field(params, "backup_name")
    schema = _field(params, "schema")
    if _INVALID in (partition_id, name, schema):
        return None
    return ClickHouseFreezePartitionStatement(dialect, table, partition_id, name, schema=schema)


def _make_unfreeze(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    name = _field(params, "backup_name", required=True)
    partition_id = _field(params, "partition_id")
    schema = _field(params, "schema")
    if _INVALID in (name, partition_id, schema):
        return None
    return ClickHouseUnfreezePartitionStatement(dialect, table, partition_id, name, schema=schema)


def _make_optimize(dialect: Any, table: str, params: Mapping) -> Optional[BaseExpression]:
    partition_id = _field(params, "partition_id")
    schema = _field(params, "schema")
    final = params.get("final", True)
    if _INVALID in (partition_id, schema) or not isinstance(final, bool):
        return None
    return ClickHouseOptimizePartitionStatement(dialect, table, partition_id, final, schema=schema)


#: operation name -> (capability probe, existing-node factory). The four
#: data-changing names are deliberately absent: see _refuse_data_changing_operation.
_OPERATIONS = {
    "detach": ("supports_detach_partition", _make_detach),
    "attach": ("supports_attach_partition", _make_attach),
    "freeze": ("supports_freeze_partition", _make_freeze),
    "unfreeze": ("supports_unfreeze_partition", _make_unfreeze),
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
        """Return a data-preserving node chain, or ``False``/``None``.

        ``None`` means the declarations are equal. ``False`` covers a bare
        change and any request that would delete, overwrite, export or reset
        table rows, or leave a detached partition outside the table.
        """
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
        detached = []
        for request in requests:
            name = _operation_name(request)
            if (
                name is None
                or name in REFUSED_OPERATIONS
                or (name not in _OPERATIONS and name not in _DATA_CHANGING_OPERATIONS)
            ):
                return PartitionSchemeChangeSuggestion(operations=False)
            if name in _DATA_CHANGING_OPERATIONS:
                return _refuse_data_changing_operation()
            params = request if isinstance(request, Mapping) else {}
            partition_id = None
            if name in ("detach", "attach"):
                partition_id = _field(params, "partition_id", required=True)
            if partition_id is _INVALID or (name == "attach" and partition_id not in detached):
                return PartitionSchemeChangeSuggestion(operations=False)
            probe, factory = _OPERATIONS[name]
            if not bool(getattr(self, probe)()):  # type: ignore[attr-defined]
                return PartitionSchemeChangeSuggestion(operations=False)
            node = factory(self, table_name, params)
            if not isinstance(node, BaseExpression):
                return PartitionSchemeChangeSuggestion(operations=False)
            if name == "detach":
                detached.append(partition_id)
            elif name == "attach":
                detached.remove(partition_id)
            chain.append(node)
        if detached:
            # DETACH without a matching ATTACH leaves rows outside the table.
            return PartitionSchemeChangeSuggestion(operations=False)
        return PartitionSchemeChangeSuggestion(operations=tuple(chain))
