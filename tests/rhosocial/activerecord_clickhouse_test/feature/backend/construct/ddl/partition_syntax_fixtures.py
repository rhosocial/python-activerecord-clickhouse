# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/ddl/partition_syntax_fixtures.py
"""Fixture data for the ClickHouse partition-syntax matrix.

The matrix is one row per syntax family. A row carries the builder that
produces the family's SQL (or the input a read/report case needs), the
fragments that must and must not appear, and optional live hooks. The matrix
is deliberately offline: the live contract lives in
``tests/.../backend/ddl/test_partition_maintenance.py`` and
``tests/.../backend/introspection/test_introspection_partitions.py``, which
already execute the same clauses against a server and skip when none is
reachable. This module does not repeat those cases; it pins the syntax family
itself, with no connection.

``builder`` returns one of:

* ``str`` -- a ``CREATE TABLE`` storage-clause tail (``ENGINE``/``ORDER BY``/
  ``PARTITION BY``) rendered by the nodes ``test_partition_syntax_matrix.py``
  reads;
* an expression node -- an ``ALTER TABLE ... PARTITION`` statement, rendered
  with ``to_sql()`` by the test;
* a tuple of str -- management verbs ClickHouse does not have;
* a list of dict -- aggregate ``system.parts`` rows;
* a mapping with ``initial`` / ``changed`` row lists -- a cache scenario;
* ``None`` -- a case whose expectation is a declared vocabulary.

References:
https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
https://clickhouse.com/docs/sql-reference/statements/alter/partition
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pytest

from rhosocial.activerecord.backend.expression.core import Column, FunctionCall
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseAttachPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseDropPartitionStatement,
    ClickHouseEngineSpec,
    ClickHouseStorageOptionKind,
    ClickHouseTableStorageOption,
)


__all__ = [
    "ASPECTS",
    "CASES",
    "DATABASE",
    "PARTITION_ID",
    "PartitionSyntaxCase",
    "TABLE",
    "partition_syntax_case",
]


TABLE = "ar_partition_matrix"
DATABASE = "analytics"
PARTITION_ID = "202601"

#: The aspects the matrix is grouped by. Each one has its own offline test in
#: ``test_partition_syntax_matrix.py``.
ASPECTS = (
    "partition_by",
    "single_level",
    "verb",
    "refusal",
    "introspection",
    "cache",
    "maintenance_list",
    "maintenance_verbs",
)


def _storage_tail(dialect: Any, partition_by: Sequence[Any]) -> str:
    """Render the storage-clause tail a ``CREATE TABLE`` would carry.

    Only the tail is rendered: the column list belongs to the DDL-generation
    tests, and repeating it here would make this matrix a second copy of them.
    """
    clauses = [
        ClickHouseTableStorageOption(
            dialect,
            ClickHouseStorageOptionKind.ENGINE,
            value=ClickHouseEngineSpec(dialect, "MergeTree"),
        ),
        ClickHouseTableStorageOption(
            dialect,
            ClickHouseStorageOptionKind.ORDER_BY,
            value=[Column(dialect, "id")],
        ),
        ClickHouseTableStorageOption(
            dialect,
            ClickHouseStorageOptionKind.PARTITION_BY,
            value=list(partition_by),
        ),
    ]
    rendered: List[str] = []
    for clause in sorted(clauses, key=lambda item: item.option.rank):
        clause_sql, _params = clause.to_sql()
        rendered.append(clause_sql)
    return " ".join(rendered)


def _partition_row(
    partition_id: str,
    row_count: int,
    bytes_on_disk: int,
    active_part_count: int,
    modified: datetime,
) -> Dict[str, Any]:
    """One aggregate row, shaped as ``ClickHouseTablePartitionsQuery`` returns it.

    The aliases are the dataclass field names, so the mapping is by name and
    nothing is inferred from a position. ``202601`` deliberately carries more
    than one active part: that is the normal state between merges.
    """
    return {
        "partition_id": partition_id,
        "partition": partition_id,
        "engine": "MergeTree",
        "row_count": row_count,
        "bytes_on_disk": bytes_on_disk,
        "active_part_count": active_part_count,
        "min_modification_time": modified,
        "max_modification_time": modified,
    }


#: Two partitions as they exist after the inserts that create them.
_INITIAL_ROWS: List[Dict[str, Any]] = [
    _partition_row("202601", 3, 300, 2, datetime(2026, 1, 6)),
    _partition_row("202602", 1, 100, 1, datetime(2026, 2, 2)),
]

#: The same table after ``DROP PARTITION ID '202601'``.
_CHANGED_ROWS: List[Dict[str, Any]] = [
    _partition_row("202602", 1, 100, 1, datetime(2026, 2, 2)),
]

#: The MySQL management verbs ClickHouse answers with ``UnsupportedFeatureError``.
_UNSUPPORTED_VERBS = (
    "add",
    "truncate",
    "reorganize",
    "exchange",
    "coalesce",
    "subpartition",
)


@dataclass(frozen=True)
class PartitionSyntaxCase:
    """One row of the ClickHouse partition-syntax matrix.

    Attributes:
        name: The pytest id of the row.
        description: What family this row pins, and why it exists.
        aspect: Which offline test asserts it (one of :data:`ASPECTS`).
        builder: Produces the row's SQL or input; see the module docstring.
        expected_fragments: Fragments that must appear in the rendered SQL
            (or, for ``maintenance_verbs``, the declared verb vocabulary).
        forbidden_fragments: Fragments that must not appear.
        live_setup: Optional hook a live-server run could use to create the
            fixture. ``None`` for every offline row in this matrix.
        live_check: Optional hook a live-server run could use to assert the
            server outcome. ``None`` for every offline row in this matrix.
    """

    name: str
    description: str
    aspect: str
    builder: Optional[Callable[[Any], Any]]
    expected_fragments: Tuple[str, ...] = ()
    forbidden_fragments: Tuple[str, ...] = ()
    live_setup: Optional[Callable[[Any], None]] = None
    live_check: Optional[Callable[[Any], None]] = None


CASES: Tuple[PartitionSyntaxCase, ...] = (
    PartitionSyntaxCase(
        name="partition_by_tuple",
        description=(
            "A tuple partition key renders as one PARTITION BY clause; the "
            "function name is uppercased by the formatter, which ClickHouse "
            "accepts because its function names are case-insensitive."
        ),
        aspect="partition_by",
        builder=lambda dialect: _storage_tail(
            dialect,
            [
                FunctionCall(
                    dialect,
                    "tuple",
                    Column(dialect, "event_date"),
                    Column(dialect, "id"),
                )
            ],
        ),
        expected_fragments=(
            "ENGINE = MergeTree",
            "PARTITION BY TUPLE(`event_date`, `id`)",
        ),
        forbidden_fragments=(
            "SUBPARTITION",
            "PARTITION BY RANGE",
            "VALUES LESS THAN",
        ),
    ),
    PartitionSyntaxCase(
        name="partition_by_expression",
        description=(
            "The monthly key is an arbitrary expression over a column, not a "
            "strategy keyword with a boundary list."
        ),
        aspect="partition_by",
        builder=lambda dialect: _storage_tail(
            dialect,
            [FunctionCall(dialect, "toYYYYMM", Column(dialect, "created_at"))],
        ),
        expected_fragments=(
            "PARTITION BY TOYYYYMM(`created_at`)",
        ),
        forbidden_fragments=(
            "PARTITION BY RANGE",
            "PARTITION BY LIST",
            "PARTITION BY HASH",
            "VALUES LESS THAN",
            "MAXVALUE",
        ),
    ),
    PartitionSyntaxCase(
        name="single_level",
        description=(
            "ClickHouse partitions one level: there is no SUBPARTITION BY, no "
            "RANGE/LIST/HASH strategy and no boundary list, and the dialect "
            "says so rather than only omitting the syntax."
        ),
        aspect="single_level",
        builder=lambda dialect: _storage_tail(
            dialect,
            [FunctionCall(dialect, "toYYYYMM", Column(dialect, "created_at"))],
        ),
        expected_fragments=(
            "PARTITION BY TOYYYYMM(`created_at`)",
        ),
        forbidden_fragments=(
            "SUBPARTITION",
            "RANGE COLUMNS",
            "VALUES LESS THAN",
            "MAXVALUE",
        ),
    ),
    PartitionSyntaxCase(
        name="drop_partition_id",
        description=(
            "DROP addresses an existing partition by the id system.parts "
            "reports; it never declares a new one."
        ),
        aspect="verb",
        builder=lambda dialect: ClickHouseDropPartitionStatement(
            dialect, TABLE, PARTITION_ID
        ),
        expected_fragments=(
            f"ALTER TABLE `{TABLE}` DROP PARTITION ID '{PARTITION_ID}'",
        ),
        forbidden_fragments=(
            "ADD PARTITION",
            "TRUNCATE PARTITION",
            "REORGANIZE PARTITION",
        ),
    ),
    PartitionSyntaxCase(
        name="detach_partition_id",
        description=(
            "DETACH moves the partition aside so ATTACH can take it back; "
            "the data survives instead of being deleted."
        ),
        aspect="verb",
        builder=lambda dialect: ClickHouseDetachPartitionStatement(
            dialect, TABLE, PARTITION_ID
        ),
        expected_fragments=(
            f"ALTER TABLE `{TABLE}` DETACH PARTITION ID '{PARTITION_ID}'",
        ),
        forbidden_fragments=(
            "TRUNCATE PARTITION",
            "EXCHANGE PARTITION",
        ),
    ),
    PartitionSyntaxCase(
        name="attach_partition_id",
        description=(
            "ATTACH re-adds a previously detached partition by id; it cannot "
            "conjure a partition that never held rows."
        ),
        aspect="verb",
        builder=lambda dialect: ClickHouseAttachPartitionStatement(
            dialect, TABLE, PARTITION_ID
        ),
        expected_fragments=(
            f"ALTER TABLE `{TABLE}` ATTACH PARTITION ID '{PARTITION_ID}'",
        ),
        forbidden_fragments=(
            "ADD PARTITION",
            "ATTACH PARTITION FROM",
        ),
    ),
    PartitionSyntaxCase(
        name="unsupported_verbs",
        description=(
            "The six MySQL partition verbs ClickHouse has no clause for raise "
            "UnsupportedFeatureError naming the three verbs it does have."
        ),
        aspect="refusal",
        builder=lambda dialect: _UNSUPPORTED_VERBS,
        expected_fragments=("DROP / DETACH / ATTACH",),
        forbidden_fragments=(),
    ),
    PartitionSyntaxCase(
        name="introspection_list",
        description=(
            "Partition introspection reads active parts from system.parts and "
            "maps the aggregate aliases onto ClickHousePartitionInfo."
        ),
        aspect="introspection",
        builder=lambda dialect: list(_INITIAL_ROWS),
        expected_fragments=(
            "FROM `system`.`parts`",
            "GROUP BY `partition_id`",
            "`active` = %s",
        ),
        forbidden_fragments=("information_schema.PARTITIONS",),
    ),
    PartitionSyntaxCase(
        name="cache_invalidation",
        description=(
            "A successful mutation drops the table's cached partition listing; "
            "a failed one leaves it intact because the server did not change."
        ),
        aspect="cache",
        builder=lambda dialect: {
            "initial": list(_INITIAL_ROWS),
            "changed": list(_CHANGED_ROWS),
        },
        expected_fragments=(
            f"DROP PARTITION ID '{PARTITION_ID}'",
        ),
        forbidden_fragments=(),
    ),
    PartitionSyntaxCase(
        name="maintenance_list_refresh",
        description=(
            "list(refresh=True) drops the cached answer and reads again; "
            "list(refresh=False) serves the cached rows after an external "
            "partition change."
        ),
        aspect="maintenance_list",
        builder=lambda dialect: {
            "initial": list(_INITIAL_ROWS),
            "changed": list(_CHANGED_ROWS),
        },
    ),
    PartitionSyntaxCase(
        name="maintenance_helpers",
        description=(
            "The service declares exactly drop/detach/attach, and list reads "
            "the introspector rather than being a fourth management verb."
        ),
        aspect="maintenance_verbs",
        builder=lambda dialect: None,
        expected_fragments=("drop", "detach", "attach"),
    ),
)


@pytest.fixture(params=CASES, ids=lambda case: case.name)
def partition_syntax_case(request: pytest.FixtureRequest) -> PartitionSyntaxCase:
    """One matrix row, identified by ``case.name``."""
    return request.param
