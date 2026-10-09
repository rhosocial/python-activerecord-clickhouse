# src/rhosocial/activerecord/backend/impl/clickhouse/expression/partition.py
"""ClickHouse table-partition DDL expressions.

ClickHouse partitioning is **not** MySQL's declarative partitioning. It is a
property of the ``MergeTree`` family of table engines, declared as an
arbitrary expression in ``CREATE TABLE``::

    CREATE TABLE visits (VisitDate Date, Hour UInt8)
    ENGINE = MergeTree
    PARTITION BY toYYYYMM(VisitDate)   -- any expression, or a tuple of them
    ORDER BY Hour

There is no partitioning *strategy* to choose, no ``PARTITION ... VALUES LESS
THAN`` / ``VALUES IN`` / ``MAXVALUE`` boundary, and no subpartitioning: a
partition is simply the set of rows whose partition-key expression evaluates
to the same value. A partition appears the first time a row lands in it; it is
never declared, so it cannot be "added" as an empty range either.

What ``ALTER TABLE`` does offer is *maintenance* of an existing partition, and
it addresses it by **partition id** (the human-readable string in the
``partition_id`` column of ``system.parts``) or by the partition-key value
itself::

    ALTER TABLE visits DROP PARTITION ID '202601';
    ALTER TABLE visits DETACH PARTITION ID '202601';
    ALTER TABLE visits ATTACH PARTITION ID '202601';

Only those three appear in this module; the rest of the ClickHouse inventory
is on the page cited below (``DROP PART``, ``DROP DETACHED PARTITION``,
``FORGET PARTITION``, ``ATTACH PARTITION FROM``, ``REPLACE PARTITION``,
``MOVE PARTITION TO TABLE``, ``FREEZE``/``UNFREEZE``, ``FETCH PARTITION``,
``MOVE PARTITION|PART ... TO DISK|VOLUME``, ``CLEAR COLUMN|INDEX IN PARTITION``,
``UPDATE``/``DELETE IN PARTITION``, ``REWRITE PARTS``). A statement that is not
on that page has no ClickHouse spelling at any version. That inventory is also
what proves the absence of the MySQL statements this backend used to stub
(``ADD PARTITION``, ``TRUNCATE PARTITION``, ``REORGANIZE PARTITION``,
``EXCHANGE PARTITION``, ``REMOVE PARTITIONING``, ``COALESCE PARTITION``,
``ANALYZE``/``CHECK``/``OPTIMIZE``/``REBUILD``/``REPAIR PARTITION``,
``SUBPARTITION BY``): none of them is in it, and asking the server for one
returns an expectation list naming every clause it *does* accept.

Introspecting partitions reads ``system.parts`` (``partition``,
``partition_id``, ``name``, ``active``); there is no
``information_schema.PARTITIONS`` — verified on the scenario server, which
answers that table name with ``Unknown table expression identifier
'information_schema.PARTITIONS'``.

Declaring ``PARTITION BY`` is not this module's job: it belongs to the storage
clauses of the table engine, rendered from the ``storage_options`` mapping by
``ClickHouseTableEngineMixin.format_table_engine_clauses``.

References (both fetched and HTTP-resolving):
https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
https://clickhouse.com/docs/sql-reference/statements/alter/partition
"""
from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import ClickHouseDialect


__all__ = [
    "ClickHouseDropPartitionExpression",
    "ClickHouseDetachPartitionExpression",
    "ClickHouseAttachPartitionExpression",
]


class _ClickHousePartitionIdExpression(BaseExpression):
    """Shared shape for the ``ALTER TABLE ... <verb> PARTITION ID`` clauses.

    ClickHouse addresses a partition by **id**, not by a name declared in the
    table's DDL: the id is the string the server derives from the partition key
    and reports in ``system.parts.partition_id`` (for a table partitioned by
    ``toYYYYMM(created_at)`` that is ``'202601'``). MySQL names its partitions in
    the DDL and addresses them by that name; ClickHouse has no such name to
    address, and a name passed where an expression belongs is a parse error —
    on the scenario server ``ALTER TABLE t DROP PARTITION p2026_01`` answers
    ``Expected one of: token sequence, Dot, token``. What the server does accept
    is listed in the "How to Set Partition Expression" section of the ALTER
    reference: a value from ``system.parts.partition``, the keyword ``ALL``, a
    ``tuple(...)`` of key values, or ``PARTITION ID '<id>'``. This backend
    always renders the last of those, because the id form is the one that works
    whatever the partition key's type is (``DROP PARTITION 202601`` happens to
    parse for a numeric key, ``DROP PARTITION '202601'`` for a string one, but
    only ``PARTITION ID`` needs no per-key guessing).

    Subclasses supply only the verb; the rendering is shared so the three
    clauses cannot drift apart.
    """

    #: The ``ALTER TABLE`` clause verb, overridden by each concrete subclass.
    verb: str = ""

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_id: str,
        *,
        schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: ClickHouse dialect instance.
            table: Target table name.
            partition_id: Value of ``system.parts.partition_id`` for the
                partition this statement addresses.
            schema: Database name, when the table is not in the connection's
                current database.

        Raises:
            ValueError: if ``table`` or ``partition_id`` is empty/whitespace.
            TypeError: if ``partition_id`` is not a string.
        """
        super().__init__(dialect)
        if not isinstance(table, str) or not table.strip():
            raise ValueError("table must be a non-empty string")
        if not isinstance(partition_id, str):
            raise TypeError(
                "partition_id must be a string (system.parts.partition_id), "
                f"got {type(partition_id).__name__}"
            )
        if not partition_id.strip():
            raise ValueError("partition_id must be a non-empty string")
        # Stored verbatim rather than as a Table object, so that the generic
        # ``get_params()`` emits exactly what the constructor accepted and the
        # round trip rebuilds the same instance. The dialect wraps these into a
        # ``Table`` at render time, where the database lands in the catalog
        # slot -- the slot ClickHouse actually has.
        self.table = table
        self.schema = schema
        self.partition_id = partition_id

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression.

        Declared as a constant by each subclass (the convention the rest of
        this backend follows, and what the structural sweep in
        ``test_clickhouse_type_protocol.py`` reads off the class rather than an
        instance). ``test_format_method_names_the_dialect_formatter`` in
        ``tests/.../backend/expression/test_expression_signatures.py`` keeps each
        constant in step with its ``verb``.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must declare its format_method property."
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(table={self.table!r}, "
            f"partition_id={self.partition_id!r})"
        )


class ClickHouseDropPartitionExpression(_ClickHousePartitionIdExpression):
    """``ALTER TABLE ... DROP PARTITION ID`` — deletes a partition's data.

    The partition's parts are tagged inactive and deleted in the background
    (~10 minutes), and the statement is replicated on a replicated table.
    """

    verb = "DROP"

    @property
    def format_method(self) -> str:
        return "format_drop_partition_statement"


class ClickHouseDetachPartitionExpression(_ClickHousePartitionIdExpression):
    """``ALTER TABLE ... DETACH PARTITION ID`` — moves a partition aside.

    Unlike ``DROP``, the data survives in the table's ``detached/`` directory,
    so it can be inspected on disk and put back with
    :class:`ClickHouseAttachPartitionExpression`. The server forgets the
    partition until it is attached again.
    """

    verb = "DETACH"

    @property
    def format_method(self) -> str:
        return "format_detach_partition_statement"


class ClickHouseAttachPartitionExpression(_ClickHousePartitionIdExpression):
    """``ALTER TABLE ... ATTACH PARTITION ID`` — re-adds a detached partition.

    Reads the partition back from the ``detached/`` directory and returns its
    rows to the table; the inverse of
    :class:`ClickHouseDetachPartitionExpression`.
    """

    verb = "ATTACH"

    @property
    def format_method(self) -> str:
        return "format_attach_partition_statement"