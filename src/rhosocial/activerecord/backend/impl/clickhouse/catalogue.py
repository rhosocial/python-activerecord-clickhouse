# src/rhosocial/activerecord/backend/impl/clickhouse/catalogue.py
"""Which ``system.*`` columns each ClickHouse release line actually answers.

The introspection queries in ``mixins.introspection`` read ClickHouse's own
catalogue tables. Those tables are not frozen: a column that a newer release
adds does not exist on an older one, and a table that a newer release adds does
not exist at all on an older one. A statement that names such a column or table
is refused by the server (``UNKNOWN_IDENTIFIER`` / ``UNKNOWN_TABLE``) rather
than answered with a partial result, so the version has to decide the statement.

The facts below were measured, not inferred, by running the statements against
real servers:

* **25.8.33.6** -- ``system.data_skipping_indices`` answers ``database``,
  ``table``, ``name``, ``type``, ``type_full``, ``expr``, ``granularity``,
  ``data_compressed_bytes``, ``data_uncompressed_bytes``, ``marks_bytes``
  (no ``creation``); ``system.constraints`` does not exist; ``system.projections``
  answers ``database``, ``table``, ``name``, ``type``, ``sorting_key``, ``query``;
  ``system.tables`` answers ``as_select`` and ``dependencies_table`` but not
  ``target_table``.
* **26.3.71.3** -- ``creation`` joins the skipping-index columns; ``system.constraints``
  still does not exist; ``system.tables`` still has no ``target_table``.
  (``system.projections`` gained ``settings``, which this backend does not read.)
* **26.7.38.18** -- ``creation`` is answered, ``system.constraints`` exists with
  ``database``, ``table``, ``name``, ``type``, ``expression``, and
  ``system.tables`` answers ``target_table``.  (The CI job for the ``26.7`` tag
  selected all three and passed, so the release line agrees.)
* **26.10.3.7** -- same catalogue surface as 26.7 for every column read here;
  measured directly, and it also shows ``unique_key`` / ``skipping_indices_types``
  on ``system.tables``, which this backend does not read.

What this table records is the set of columns **this backend may name**, not
every column the server happens to have. A release line is added here only
after the columns have been measured against that line, and a query that names
one of them is checked against this table by
``test_catalogue_capabilities.py``.

An unrecorded release line is answered with the newest recorded line at or
below it, and a version older than every recorded line with the oldest one. That
direction is deliberate: the fallback may *omit* a column the server actually
has, which is an honest "not asked", but it never names a column the server
may not have. It can therefore refuse a catalogue a newer unmeasured server
does have; it cannot make a statement the server rejects.
"""

from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

#: A ClickHouse server version, as ``(major, minor, patch)``.
Version = Tuple[int, int, int]

#: A release line, as ``(major, minor)``: catalogue columns move between lines.
Line = Tuple[int, int]


@dataclass(frozen=True)
class ClickHouseCatalogueCapabilities:
    """The catalogue columns this backend may name on one release line."""

    #: The release line these sets were measured on.
    line: Line
    #: Readable columns of ``system.data_skipping_indices``.
    skipping_index_columns: FrozenSet[str]
    #: Readable columns of ``system.projections``.
    projection_columns: FrozenSet[str]
    #: Readable columns of ``system.constraints``, or ``None`` when the table
    #: does not exist on this line. ``None`` is a refusal, never an empty table:
    #: the method that needs this catalogue raises by name instead of answering
    #: "no constraints", which would be a claim the server never made.
    constraint_columns: Optional[FrozenSet[str]]
    #: Readable columns of ``system.tables`` used for derived-object discovery.
    system_table_columns: FrozenSet[str]

    def has_constraint_catalogue(self) -> bool:
        """Whether ``system.constraints`` exists on this line."""
        return self.constraint_columns is not None


_SKIPPING_INDICES_WITHOUT_CREATION = frozenset(
    {
        "database",
        "table",
        "name",
        "type",
        "type_full",
        "expr",
        "granularity",
        "data_compressed_bytes",
        "data_uncompressed_bytes",
        "marks_bytes",
    }
)
_SKIPPING_INDICES_WITH_CREATION = _SKIPPING_INDICES_WITHOUT_CREATION | {"creation"}

_PROJECTIONS = frozenset({"database", "table", "name", "type", "sorting_key", "query"})

_CONSTRAINTS = frozenset({"database", "table", "name", "type", "expression"})

_SYSTEM_TABLES_WITHOUT_TARGET = frozenset(
    {"database", "name", "engine", "as_select", "dependencies_table"}
)
_SYSTEM_TABLES_WITH_TARGET = _SYSTEM_TABLES_WITHOUT_TARGET | {"target_table"}


#: Measured catalogue surface, one entry per release line this backend targets.
#: Keys are ordered by release line; ``capabilities_for_version`` relies on
#: ordinary tuple ordering, not on dict insertion order.
CAPABILITY_MATRIX = {
    (25, 8): ClickHouseCatalogueCapabilities(
        line=(25, 8),
        skipping_index_columns=_SKIPPING_INDICES_WITHOUT_CREATION,
        projection_columns=_PROJECTIONS,
        constraint_columns=None,
        system_table_columns=_SYSTEM_TABLES_WITHOUT_TARGET,
    ),
    (26, 3): ClickHouseCatalogueCapabilities(
        line=(26, 3),
        skipping_index_columns=_SKIPPING_INDICES_WITH_CREATION,
        projection_columns=_PROJECTIONS,
        constraint_columns=None,
        system_table_columns=_SYSTEM_TABLES_WITHOUT_TARGET,
    ),
    (26, 7): ClickHouseCatalogueCapabilities(
        line=(26, 7),
        skipping_index_columns=_SKIPPING_INDICES_WITH_CREATION,
        projection_columns=_PROJECTIONS,
        constraint_columns=_CONSTRAINTS,
        system_table_columns=_SYSTEM_TABLES_WITH_TARGET,
    ),
    (26, 10): ClickHouseCatalogueCapabilities(
        line=(26, 10),
        skipping_index_columns=_SKIPPING_INDICES_WITH_CREATION,
        projection_columns=_PROJECTIONS,
        constraint_columns=_CONSTRAINTS,
        system_table_columns=_SYSTEM_TABLES_WITH_TARGET,
    ),
}

#: The oldest measured line, also the answer when no version is known yet.
_BASELINE_LINE = min(CAPABILITY_MATRIX)


def capabilities_for_version(
    version: Optional[Version],
) -> ClickHouseCatalogueCapabilities:
    """The recorded catalogue surface in force for *version*.

    The lookup is by release line: catalogue columns move when a release line
    moves, not on a patch. An unrecorded line resolves to the newest recorded
    line at or below it; a version older than every recorded line, or one
    nobody knows yet, resolves to the oldest recorded line. See the module
    docstring for why the fallback never moves forward.
    """
    if version is None:
        return CAPABILITY_MATRIX[_BASELINE_LINE]
    line = (version[0], version[1])
    recorded = [key for key in CAPABILITY_MATRIX if key <= line]
    if recorded:
        return CAPABILITY_MATRIX[max(recorded)]
    return CAPABILITY_MATRIX[_BASELINE_LINE]


def version_label(version: Optional[Version]) -> str:
    """A version as a dotted release, or ``unknown`` when none is known."""
    if version is None:
        return "unknown"
    return f"{version[0]}.{version[1]}.{version[2]}"
