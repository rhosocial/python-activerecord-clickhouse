# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/type.py
"""ClickHouse-native data type protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import DataTypeSupport


__all__ = ["ClickHouseTypeSupport"]


@runtime_checkable
class ClickHouseTypeSupport(DataTypeSupport, Protocol):
    """ClickHouse-native data type protocol.

    Feature Source: ClickHouse native (not SQL standard)

    ClickHouse owns a large set of types core does not model, and the framework
    renders them through the naming convention rather than through an interface:
    a ``ClickHouse`` type declares ``name = "clickhouse_<type>"`` and the dialect
    answers with ``format_data_type_clickhouse_<type>`` /
    ``supports_data_type_clickhouse_<type>``. Enumerating all of them here would
    mean restating the type list in a second place, where it would go stale the
    next time a type is added.

    What the protocol *does* state is the one thing the naming pattern cannot
    express: that this backend's own types are declared alongside the core ones
    in the same correspondence, and that a concept ClickHouse genuinely cannot
    spell is answered through
    :meth:`~...dialect.mixins.data_type.DataTypeMixin.suggested_data_types`
    rather than left silent. ``ClickHouseSetTypeSupport`` is *not* part of this —
    it covers ``FIND_IN_SET`` and the SET literal syntax, which are functions
    rather than a column type, and mixing the two would make ``isinstance`` true
    for a dialect that had one and not the other.
    """

    def suggested_data_types(self) -> dict:
        """Core concepts this dialect cannot spell, and the types it stores instead.

        Keys are core concept ``name``s; values are ``DataType`` subclasses this
        dialect renders through their own ``name``. Disjoint from the set of
        rendered names by contract.
        """
        ...
