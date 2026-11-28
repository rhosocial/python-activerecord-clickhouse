# src/rhosocial/activerecord/backend/impl/clickhouse/expression/query_parts/partition.py
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

This module carries the operations from that page which have a stable SQL
shape and that the backend models: the three verbs above, plus
``REPLACE PARTITION ... FROM``, ``MOVE PARTITION ... TO``,
``FREEZE`` / ``UNFREEZE``, ``CLEAR ... IN PARTITION`` and
``OPTIMIZE TABLE ... [PARTITION] FINAL``. For the partition addressing forms
the page documents (a ``system.parts.partition`` value, ``ALL``, a
``tuple(...)`` of key values, or ``PARTITION ID '<id>'``), every node here
renders the ``PARTITION ID`` form, because it is the form that works whatever
the partition key's type is.

The rest of the ClickHouse inventory is on the page cited below (``DROP PART``,
``DROP DETACHED PARTITION``, ``FORGET PARTITION``, ``ATTACH PARTITION FROM``,
``FETCH PARTITION``, ``MOVE PARTITION|PART ... TO DISK|VOLUME`` for parts,
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
https://clickhouse.com/docs/sql-reference/statements/optimize
"""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.bases.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import ClickHouseDialect


__all__ = [
    "ClickHouseDropPartitionStatement",
    "ClickHouseDetachPartitionStatement",
    "ClickHouseAttachPartitionStatement",
    "ClickHouseReplacePartitionStatement",
    "ClickHouseMovePartitionStatement",
    "ClickHouseFreezePartitionStatement",
    "ClickHouseUnfreezePartitionStatement",
    "ClickHouseClearInPartitionStatement",
    "ClickHouseOptimizePartitionStatement",
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

    # No ``format_method`` here on purpose: this shared shape is not a kind of
    # its own. Each concrete subclass declares its formatter, which is also what
    # keeps the private base out of the artifact registry (a base that names no
    # formatter cannot be carried by an artifact).
    # ``test_format_method_names_the_dialect_formatter`` in
    # ``tests/.../backend/expression/test_expression_signatures.py`` keeps each
    # declaration in step with its ``verb``.

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(table={self.table!r}, " f"partition_id={self.partition_id!r})"
        )


class ClickHouseDropPartitionStatement(_ClickHousePartitionIdExpression):
    """``ALTER TABLE ... DROP PARTITION ID`` — deletes a partition's data.

    The partition's parts are tagged inactive and deleted in the background
    (~10 minutes), and the statement is replicated on a replicated table.
    """

    verb = "DROP"

    @property
    def format_method(self) -> str:
        return "format_drop_partition_statement"


class ClickHouseDetachPartitionStatement(_ClickHousePartitionIdExpression):
    """``ALTER TABLE ... DETACH PARTITION ID`` — moves a partition aside.

    Unlike ``DROP``, the data survives in the table's ``detached/`` directory,
    so it can be inspected on disk and put back with
    :class:`ClickHouseAttachPartitionStatement`. The server forgets the
    partition until it is attached again.
    """

    verb = "DETACH"

    @property
    def format_method(self) -> str:
        return "format_detach_partition_statement"


class ClickHouseAttachPartitionStatement(_ClickHousePartitionIdExpression):
    """``ALTER TABLE ... ATTACH PARTITION ID`` — re-adds a detached partition.

    Reads the partition back from the ``detached/`` directory and returns its
    rows to the table; the inverse of
    :class:`ClickHouseDetachPartitionStatement`.
    """

    verb = "ATTACH"

    @property
    def format_method(self) -> str:
        return "format_attach_partition_statement"


class ClickHouseReplacePartitionStatement(BaseExpression):
    """``ALTER TABLE ... REPLACE PARTITION ID '<id>' FROM <source_table>``.

    Copies the source table's partition over the target table's partition of
    the same id, atomically. The source's data is not deleted. ClickHouse
    requires both tables to share the structure, partition key, order-by key,
    primary key and storage policy, and the target to carry at least the
    source's skipping indexes and projections. Those preconditions are the
    server's to enforce; this node renders the statement, not a pre-flight
    check.

    Official reference ("REPLACE PARTITION"):
    https://clickhouse.com/docs/sql-reference/statements/alter/partition
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_id: str,
        source_table: str,
        *,
        schema: Optional[str] = None,
        source_schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: ClickHouse dialect instance.
            table: Target table name.
            partition_id: Value of ``system.parts.partition_id`` for the
                partition being replaced.
            source_table: Table the partition is copied from.
            schema: Database of *table*, when not the connected database.
            source_schema: Database of *source_table*, when not the connected
                database.

        No validation here: the constructor carries the parameters, and the
        dialect formatter decides whether the combination has a ClickHouse
        spelling (see ``format_replace_partition_statement``). That split keeps
        the round-trip artifact carrying exactly what the caller passed.
        """
        super().__init__(dialect)
        self.table = table
        self.partition_id = partition_id
        self.source_table = source_table
        self.schema = schema
        self.source_schema = source_schema

    @property
    def format_method(self) -> str:
        return "format_replace_partition_statement"


class ClickHouseMovePartitionStatement(BaseExpression):
    """``ALTER TABLE ... MOVE PARTITION ID '<id>' TO {DISK|VOLUME|TABLE} <target>``.

    ``TO DISK`` / ``TO VOLUME`` move a partition between storage devices;
    ``TO TABLE`` moves it into another table, deleting it from the source.
    The target of a disk/volume clause is a configured disk or volume name
    (rendered as a quoted literal, as the reference spells it); the target of
    a table clause is a table name (rendered as an identifier).

    Official reference ("MOVE PARTITION|PART" and "MOVE PARTITION TO TABLE"):
    https://clickhouse.com/docs/sql-reference/statements/alter/partition
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_id: str,
        destination: str,
        target: str,
        *,
        schema: Optional[str] = None,
        target_schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: ClickHouse dialect instance.
            table: Source table name.
            partition_id: Value of ``system.parts.partition_id``.
            destination: ``DISK``, ``VOLUME`` or ``TABLE`` (case-insensitive
                at render time).
            target: The disk/volume name, or the destination table name.
            schema: Database of *table*, when not the connected database.
            target_schema: Database of *target* when *destination* is
                ``TABLE``; ignored otherwise.

        No validation here; see
        ``format_move_partition_statement`` for the spelling rules.
        """
        super().__init__(dialect)
        self.table = table
        self.partition_id = partition_id
        self.destination = destination
        self.target = target
        self.schema = schema
        self.target_schema = target_schema

    @property
    def format_method(self) -> str:
        return "format_move_partition_statement"


class ClickHouseFreezePartitionStatement(BaseExpression):
    """``ALTER TABLE ... FREEZE [PARTITION ID '<id>'] [WITH NAME '<name>']``.

    Creates a local hard-link backup in ``shadow/``. The ``PARTITION`` clause
    is optional (omitting it freezes every partition), and so is ``WITH NAME``
    (omitting it selects the next incremental number). The statement is not
    replicated: it backs up the local server only.

    Official reference ("FREEZE PARTITION"):
    https://clickhouse.com/docs/sql-reference/statements/alter/partition
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_id: Optional[str] = None,
        name: Optional[str] = None,
        *,
        schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: ClickHouse dialect instance.
            table: Table to freeze.
            partition_id: The partition to freeze, or ``None`` for all.
            name: Backup name, or ``None`` to let the server number it.
            schema: Database of *table*, when not the connected database.

        No validation here; see ``format_freeze_partition_statement``.
        """
        super().__init__(dialect)
        self.table = table
        self.partition_id = partition_id
        self.name = name
        self.schema = schema

    @property
    def format_method(self) -> str:
        return "format_freeze_partition_statement"


class ClickHouseUnfreezePartitionStatement(BaseExpression):
    """``ALTER TABLE ... UNFREEZE [PARTITION ID '<id>'] WITH NAME '<name>'``.

    Removes a frozen backup written by :class:`ClickHouseFreezePartitionStatement`.
    Unlike ``FREEZE``, ``WITH NAME`` is not optional in the reference grammar:
    ``UNFREEZE`` names which backup to remove, and there is no "next
    incremental number" to guess. The formatter refuses a missing name by name
    rather than rendering a statement the server cannot parse.

    Official reference ("UNFREEZE PARTITION"):
    https://clickhouse.com/docs/sql-reference/statements/alter/partition
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_id: Optional[str] = None,
        name: Optional[str] = None,
        *,
        schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: ClickHouse dialect instance.
            table: Table whose backup is removed.
            partition_id: The partition, or ``None`` for the whole table.
            name: Backup name. Required by the grammar; the formatter refuses
                a missing or blank value.
            schema: Database of *table*, when not the connected database.

        No validation here; see ``format_unfreeze_partition_statement``.
        """
        super().__init__(dialect)
        self.table = table
        self.partition_id = partition_id
        self.name = name
        self.schema = schema

    @property
    def format_method(self) -> str:
        return "format_unfreeze_partition_statement"


class ClickHouseClearInPartitionStatement(BaseExpression):
    """``ALTER TABLE ... CLEAR {COLUMN|INDEX|PROJECTION} <name> [IN PARTITION ID '<id>']``.

    Resets the column's values, the skipping index's files, or the projection's
    files inside a partition. The grammar differs by kind:

    * ``CLEAR COLUMN <c> IN PARTITION <expr>`` -- ``IN PARTITION`` is required
      (the column-level reference page spells it without brackets);
    * ``CLEAR INDEX <i> IN PARTITION <expr>`` -- likewise required;
    * ``CLEAR PROJECTION <p> [IN PARTITION <expr>]`` -- optional; omitting it
      clears the projection files across the whole table.

    The formatter enforces that distinction instead of inventing a table-wide
    ``CLEAR COLUMN`` the server rejects.

    References:
    https://clickhouse.com/docs/sql-reference/statements/alter/partition
    https://clickhouse.com/docs/sql-reference/statements/alter/column
    https://clickhouse.com/docs/sql-reference/statements/alter/projection
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        kind: str,
        name: str,
        partition_id: Optional[str] = None,
        *,
        schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: ClickHouse dialect instance.
            table: Table to modify.
            kind: ``COLUMN``, ``INDEX`` or ``PROJECTION`` (case-insensitive at
                render time).
            name: The column, index or projection name. An identifier, not a
                value, so the formatter quotes it.
            partition_id: The partition to clear in, or ``None`` for a
                projection-wide clear.
            schema: Database of *table*, when not the connected database.

        No validation here; see ``format_clear_in_partition_statement``.
        """
        super().__init__(dialect)
        self.table = table
        self.kind = kind
        self.name = name
        self.partition_id = partition_id
        self.schema = schema

    @property
    def format_method(self) -> str:
        return "format_clear_in_partition_statement"


class ClickHouseOptimizePartitionStatement(BaseExpression):
    """``OPTIMIZE TABLE ... [PARTITION ID '<id>'] [FINAL]``.

    A statement of its own, not an ``ALTER TABLE`` action. ``FINAL`` forces the
    merge even when every row already sits in one part; omitting ``PARTITION``
    optimizes the whole table.

    This is deliberately not :class:`~.maintenance.ClickHouseOptimizeTableExpression`:
    that node models MySQL's comma-separated ``OPTIMIZE TABLE t1, t2``
    maintenance statement, and this dialect refuses it as a whole-table MySQL
    maintenance family. The ClickHouse-only ``PARTITION`` and ``FINAL``
    clauses are what this node exists to spell.

    Official reference:
    https://clickhouse.com/docs/sql-reference/statements/optimize
    """

    def __init__(
        self,
        dialect: "ClickHouseDialect",
        table: str,
        partition_id: Optional[str] = None,
        final: bool = True,
        *,
        schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: ClickHouse dialect instance.
            table: Table to optimize.
            partition_id: The partition to optimize, or ``None`` for the table.
            final: Render the ``FINAL`` keyword. ``False`` renders a plain
                ``OPTIMIZE TABLE``, which is also valid ClickHouse.
            schema: Database of *table*, when not the connected database.

        No validation here; see ``format_optimize_partition_final_statement``.
        """
        super().__init__(dialect)
        self.table = table
        self.partition_id = partition_id
        self.final = final
        self.schema = schema

    @property
    def format_method(self) -> str:
        return "format_optimize_partition_final_statement"
