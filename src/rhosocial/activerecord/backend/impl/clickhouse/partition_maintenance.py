# src/rhosocial/activerecord/backend/impl/clickhouse/partition_maintenance.py
"""Backend-level maintenance helpers for ClickHouse table partitions.

ClickHouse partitions a ``MergeTree``-family table with a ``PARTITION BY
<expr>`` clause on ``CREATE TABLE``, and a partition materialises the first
time a row lands in it. ``ALTER TABLE`` is therefore not a place to *declare*
partitions; it maintains the ones that already exist, and it addresses each by
the id the server reports in ``system.parts.partition_id``::

    ALTER TABLE visits DROP PARTITION ID '202601';
    ALTER TABLE visits DETACH PARTITION ID '202601';
    ALTER TABLE visits ATTACH PARTITION ID '202601';

Those three are the verbs this service's ``execute`` dispatcher takes: ``DROP``,
``DETACH`` and ``ATTACH`` are the lifecycle verbs a retention job drives. The
same reference page carries more ``ALTER TABLE ... PARTITION`` operations, and
the ones with a stable, parameterised shape are also exposed here as direct
helpers -- ``replace`` (``REPLACE PARTITION ... FROM``), ``move``
(``MOVE PARTITION ... TO DISK|VOLUME|TABLE``), ``freeze`` / ``unfreeze``,
``clear`` (``CLEAR COLUMN|INDEX|PROJECTION ... IN PARTITION``) and ``optimize``
(``OPTIMIZE TABLE ... [PARTITION] FINAL``). What has no clause at all is still
refused: there is no ``ADD PARTITION`` (a partition appears with its first
row), no ``TRUNCATE PARTITION`` (the substitute is ``DELETE IN PARTITION``),
no ``REORGANIZE`` / ``EXCHANGE`` / ``COALESCE`` / ``REMOVE PARTITIONING``, and
no ``SUBPARTITION BY``: ClickHouse partitions one level, by an arbitrary key
expression. The inventory that proves that absence lives as data in
``mixins/partition.py`` (``ALTER_PARTITION_INVENTORY`` /
``MYSQL_ONLY_PARTITION_STATEMENTS``), and this module refuses anything outside
it rather than inventing a clause the server would reject.

This is the maintenance layer the plan keeps outside the ``PartitionSupport``
protocol: the protocol answers capability questions and renders ``PARTITION BY``
clauses, not lifecycle. The verbs are not re-spelled here. Each helper builds
the expression node from ``expression/partition.py`` and executes the SQL that
node renders, so the clause has exactly one home, and :meth:`list` returns the
introspector's own :class:`ClickHousePartitionInfo` rows, whose
``partition_id`` is precisely the value the helpers take.

No table name, partition name or retention window is defaulted or derived here.
Which tables to maintain, how often, and what to keep belong to the
application; a helper that guessed any of them would be one application's
policy written into the library. Partition ids are assigned by the server, and
the verbs act on ids that already exist — they cannot create a partition for a
future bucket. The one deliberate default is ``optimize(final=True)``: the
reference describes the plain form as an ordinary scheduled merge, while
``FINAL`` is the administrative force-merge callers reach for; pass
``final=False`` for the plain form.

Because ClickHouse has no transactions, each call is one statement. A failure
leaves the partition exactly as the server left it, and that outcome is reported
by the raised error rather than hidden behind a rollback that cannot happen.

References (both fetched and HTTP-resolving):
https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
https://clickhouse.com/docs/sql-reference/statements/alter/partition
https://clickhouse.com/docs/sql-reference/statements/optimize
"""

from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
from rhosocial.activerecord.backend.result import QueryResult

from .expression.partition import (
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
from .introspection.types import ClickHousePartitionInfo

if TYPE_CHECKING:  # pragma: no cover
    from .backend.backend import ClickHouseBackend
    from .dialect import ClickHouseDialect


__all__ = [
    "ClickHousePartitionMaintenance",
    "MANAGEMENT_VERBS",
]


#: The three verbs the ``execute`` dispatcher takes, spelled as the helper
#: methods that implement them. :meth:`list` is a read, takes no partition id
#: and is kept out of this tuple so that ``execute`` cannot be asked to "run"
#: it. The remaining partition operations (``replace`` / ``move`` / ``freeze`` /
#: ``unfreeze`` / ``clear`` / ``optimize``) take more parameters than this
#: dispatcher's shape carries, so they are direct helpers rather than verbs
#: here.
MANAGEMENT_VERBS = ("drop", "detach", "attach")


#: What to say when a caller asks ``execute`` for a verb it does not dispatch.
#: The suggestion names the three it does and the substitutions a retention
#: tool is most likely to be reaching for, because "not supported" alone would
#: leave the caller guessing whether the failure was a missing argument.
_UNSUPPORTED_VERB_SUGGESTION = (
    "execute() dispatches DROP / DETACH / ATTACH PARTITION ID. A partition "
    "appears with the first row that lands in it, so ADD has no clause, "
    "TRUNCATE is spelled DELETE IN PARTITION, and there is no REORGANIZE / "
    "EXCHANGE / COALESCE / REMOVE PARTITIONING / SUBPARTITION BY. REPLACE / "
    "MOVE / FREEZE / UNFREEZE / CLEAR / OPTIMIZE are available as direct "
    "helpers, because they take more parameters than execute() carries."
)


class ClickHousePartitionMaintenance:
    """The partition maintenance ClickHouse actually has, as one read and several helpers.

    A service rather than a set of module functions so that it can carry the
    backend it acts on, and so the backend can expose one stable entry point
    (``backend.partition_maintenance``) without every call naming the backend
    again. It holds only that reference and builds one statement per call; it
    keeps no partition plan and no cached partition list of its own.

    Attributes:
        backend: The backend whose dialect and connection this service uses.
        verbs: The management verbs :meth:`execute` accepts.

    Example:
        >>> service = backend.partition_maintenance
        >>> partitions = service.list("visits", refresh=True)
        >>> [p.partition_id for p in partitions]
        ['202601', '202602']
        >>> service.detach("visits", "202601")
        >>> service.attach("visits", "202601")
        >>> service.drop("visits", "202601")
        >>> service.replace("visits", "202601", "visits_staging")
        >>> service.move("visits", "202601", "VOLUME", "cold")
        >>> service.freeze("visits", "202601", name="backup_202601")
        >>> service.clear("visits", "COLUMN", "browser", "202601")
        >>> service.optimize("visits", "202601")
    """

    #: The management verbs, in the spelling :meth:`execute` normalises to.
    verbs = MANAGEMENT_VERBS

    def __init__(self, backend: "ClickHouseBackend") -> None:
        """Bind the service to a backend.

        Args:
            backend: ClickHouse backend whose ``dialect`` renders the clauses
                and whose ``execute`` runs them. The backend is not connected
                here; a connection is opened when a call first needs one.
        """
        self._backend = backend

    @property
    def backend(self) -> "ClickHouseBackend":
        """The backend this service acts on."""
        return self._backend

    @property
    def dialect(self) -> "ClickHouseDialect":
        """The backend's ClickHouse dialect, used to render each clause."""
        return self._backend.dialect

    def list(
        self,
        table: str,
        *,
        database: Optional[str] = None,
        refresh: bool = False,
    ) -> List[ClickHousePartitionInfo]:
        """List a table's partitions, aggregated from its active parts.

        This is the read a retention job decides from: every item carries the
        ``partition_id`` the three management helpers take, plus the readable
        ``partition`` value, the row count and the bytes on disk. The read is
        the introspector's (``system.parts``, active parts only), so the two
        entry points cannot disagree.

        Args:
            table: The table to read. A table declared without ``PARTITION BY``
                answers its one ``'all'`` partition.
            database: The ClickHouse database the table lives in; ``None`` means
                the connected database.
            refresh: Drop the cached answer for *table* before reading. Set this
                after a partition change made outside this service — a raw
                ``ALTER TABLE`` through ``backend.execute``, or another process
                on the same server — because the introspector caches its answer.

        Returns:
            One :class:`ClickHousePartitionInfo` per ``partition_id``, ordered
            by that id. A table with no parts returns an empty list: the server
            has nothing to report, so nothing is invented.

        Raises:
            ValueError: if *table* is not a non-empty string.
        """
        self._require_table(table)
        if refresh:
            self._invalidate(table)
        return self._backend.introspector.list_partitions(table, database)

    def drop(
        self,
        table: str,
        partition_id: str,
        *,
        database: Optional[str] = None,
    ) -> QueryResult:
        """Delete a partition and its data with ``DROP PARTITION ID``.

        This is the operation partitioning exists for: ClickHouse tags the
        partition's parts inactive and removes them in the background, rather
        than deleting rows one at a time. On a replicated table the drop is
        replicated too.

        Args:
            table: The table to modify.
            partition_id: A value from ``system.parts.partition_id``, as
                :meth:`list` returns it.
            database: The ClickHouse database the table lives in; ``None`` means
                the connected database.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            ValueError: if *table* or *partition_id* is empty.
            TypeError: if *partition_id* is not a string.
        """
        return self._run(
            ClickHouseDropPartitionStatement(self.dialect, table, partition_id, schema=database)
        )

    def detach(
        self,
        table: str,
        partition_id: str,
        *,
        database: Optional[str] = None,
    ) -> QueryResult:
        """Move a partition aside with ``DETACH PARTITION ID``.

        The data survives in the table's ``detached/`` directory instead of
        being deleted, which is what makes :meth:`attach` possible. Until it is
        attached again the server does not report the partition in
        ``system.parts``, and queries over the table no longer see its rows.

        Args:
            table: The table to modify.
            partition_id: A value from ``system.parts.partition_id``.
            database: The ClickHouse database the table lives in; ``None`` means
                the connected database.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            ValueError: if *table* or *partition_id* is empty.
            TypeError: if *partition_id* is not a string.
        """
        return self._run(
            ClickHouseDetachPartitionStatement(self.dialect, table, partition_id, schema=database)
        )

    def attach(
        self,
        table: str,
        partition_id: str,
        *,
        database: Optional[str] = None,
    ) -> QueryResult:
        """Take a detached partition back with ``ATTACH PARTITION ID``.

        Reads the partition from the table's ``detached/`` directory and
        returns its rows to the table — the inverse of :meth:`detach`. It acts
        on an id that was detached earlier; it cannot conjure rows for a bucket
        that never held any.

        Args:
            table: The table to modify.
            partition_id: The id of a partition previously detached from this
                table, as ``system.parts.partition_id`` reported it.
            database: The ClickHouse database the table lives in; ``None`` means
                the connected database.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            ValueError: if *table* or *partition_id* is empty.
            TypeError: if *partition_id* is not a string.
        """
        return self._run(
            ClickHouseAttachPartitionStatement(self.dialect, table, partition_id, schema=database)
        )

    def replace(
        self,
        table: str,
        partition_id: str,
        source_table: str,
        *,
        database: Optional[str] = None,
        source_database: Optional[str] = None,
    ) -> QueryResult:
        """Replace a partition with ``REPLACE PARTITION ID ... FROM``.

        Copies *source_table*'s partition of the same id over *table*'s, atomically.
        The source's data is not deleted. The server requires both tables to
        share structure, partition/order/primary keys and storage policy; those
        are the server's preconditions, so they are not pre-flighted here.

        Args:
            table: The table whose partition is replaced.
            partition_id: A value from ``system.parts.partition_id``.
            source_table: The table the partition is copied from.
            database: Database of *table*, when not the connected database.
            source_database: Database of *source_table*, when not the connected
                database. Installs are usually same-database; spell it only when
                they are not.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            UnsupportedFeatureError: if a required argument is missing or blank
                (see ``format_replace_partition_statement``).
        """
        return self._run(
            ClickHouseReplacePartitionStatement(
                self.dialect,
                table,
                partition_id,
                source_table,
                schema=database,
                source_schema=source_database,
            )
        )

    def move(
        self,
        table: str,
        partition_id: str,
        destination: str,
        target: str,
        *,
        database: Optional[str] = None,
        target_database: Optional[str] = None,
    ) -> QueryResult:
        """Move a partition with ``MOVE PARTITION ID ... TO``.

        Args:
            table: Source table.
            partition_id: A value from ``system.parts.partition_id``.
            destination: ``DISK``, ``VOLUME`` or ``TABLE`` (case-insensitive).
            target: The disk/volume name, or the destination table name.
            database: Database of *table*, when not the connected database.
            target_database: Database of *target* when *destination* is
                ``TABLE``.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            UnsupportedFeatureError: if *destination* is not one of the three
                keywords, or a required name is missing/blank.
        """
        return self._run(
            ClickHouseMovePartitionStatement(
                self.dialect,
                table,
                partition_id,
                destination,
                target,
                schema=database,
                target_schema=target_database,
            )
        )

    def freeze(
        self,
        table: str,
        partition_id: Optional[str] = None,
        *,
        name: Optional[str] = None,
        database: Optional[str] = None,
    ) -> QueryResult:
        """Create a local backup with ``FREEZE [PARTITION ID] [WITH NAME]``.

        Args:
            table: Table to freeze.
            partition_id: The partition to freeze; ``None`` freezes all.
            name: Backup name; ``None`` lets the server number it.
            database: Database of *table*, when not the connected database.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            UnsupportedFeatureError: if a supplied value is blank instead of
                absent, or the table is missing.
        """
        return self._run(
            ClickHouseFreezePartitionStatement(
                self.dialect, table, partition_id, name, schema=database
            )
        )

    def unfreeze(
        self,
        table: str,
        name: str,
        partition_id: Optional[str] = None,
        *,
        database: Optional[str] = None,
    ) -> QueryResult:
        """Remove a frozen backup with ``UNFREEZE [PARTITION ID] WITH NAME``.

        *name* is required by the grammar: ``UNFREEZE`` names which backup to
        remove, so there is no incremental number to default to.

        Args:
            table: Table whose backup is removed.
            name: The backup name, as ``freeze(name=...)`` wrote it.
            partition_id: The partition; ``None`` removes the whole table's
                backup.
            database: Database of *table*, when not the connected database.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            UnsupportedFeatureError: if *name* is missing/blank (the statement
                has no spelling without ``WITH NAME``), or another supplied
                value is blank.
        """
        return self._run(
            ClickHouseUnfreezePartitionStatement(
                self.dialect, table, partition_id, name, schema=database
            )
        )

    def clear(
        self,
        table: str,
        kind: str,
        name: str,
        partition_id: Optional[str] = None,
        *,
        database: Optional[str] = None,
    ) -> QueryResult:
        """Clear a column, index or projection with ``CLEAR ... IN PARTITION``.

        Args:
            table: Table to modify.
            kind: ``COLUMN``, ``INDEX`` or ``PROJECTION`` (case-insensitive).
            name: The column/index/projection name (an identifier).
            partition_id: The partition to clear in. Required for ``COLUMN``
                and ``INDEX``, optional for ``PROJECTION`` -- that asymmetry
                is the reference grammar's.
            database: Database of *table*, when not the connected database.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            UnsupportedFeatureError: if *kind* is not one of the three
                keywords, a name is missing, or a ``COLUMN`` / ``INDEX`` clear
                carries no partition id.
        """
        return self._run(
            ClickHouseClearInPartitionStatement(
                self.dialect,
                table,
                kind,
                name,
                partition_id,
                schema=database,
            )
        )

    def optimize(
        self,
        table: str,
        partition_id: Optional[str] = None,
        *,
        database: Optional[str] = None,
        final: bool = True,
    ) -> QueryResult:
        """Run ``OPTIMIZE TABLE ... [PARTITION ID] [FINAL]``.

        Args:
            table: Table to optimize.
            partition_id: The partition to optimize; ``None`` for the table.
            database: Database of *table*, when not the connected database.
            final: Render ``FINAL`` (the default). Pass ``False`` for the
                plain, scheduled-merge form.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            UnsupportedFeatureError: if the table is missing, a partition id
                is blank, or *final* is not a bool.
        """
        return self._run(
            ClickHouseOptimizePartitionStatement(
                self.dialect, table, partition_id, final, schema=database
            )
        )

    def execute(
        self,
        verb: str,
        table: str,
        partition_id: Optional[str] = None,
        *,
        database: Optional[str] = None,
    ) -> QueryResult:
        """Run one management verb by name.

        Exists for callers that hold the verb as configuration (a CLI flag, a
        retention policy file) and should not have to map it to a method name
        by hand. The mapping is exactly :data:`MANAGEMENT_VERBS`; everything
        else raises :class:`UnsupportedFeatureError`, because ClickHouse has no
        clause for it — the failure is the capability answer, not an
        ``AttributeError`` that would read as a typo.

        Args:
            verb: ``"drop"``, ``"detach"`` or ``"attach"``, case-insensitively.
            table: The table to modify.
            partition_id: A value from ``system.parts.partition_id``.
            database: The ClickHouse database the table lives in; ``None`` means
                the connected database.

        Returns:
            The backend's :class:`QueryResult` for the statement.

        Raises:
            ValueError: if *verb* is empty, or *partition_id* is empty or
                missing for a verb that needs one.
            TypeError: if *partition_id* is not a string.
            UnsupportedFeatureError: if *verb* is not one ClickHouse has.
        """
        if not isinstance(verb, str) or not verb.strip():
            raise ValueError("verb must be a non-empty string")
        name = verb.strip().lower()
        if name not in MANAGEMENT_VERBS:
            raise UnsupportedFeatureError(
                self.dialect.name, f"{name.upper()} PARTITION", _UNSUPPORTED_VERB_SUGGESTION
            )
        if partition_id is None:
            raise ValueError(f"{name} needs a partition_id from system.parts.partition_id")
        if not isinstance(partition_id, str):
            raise TypeError("partition_id must be a string")
        if not partition_id.strip():
            raise ValueError(f"{name} needs a partition_id from system.parts.partition_id")
        return getattr(self, name)(table, partition_id, database=database)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _run(self, statement) -> QueryResult:
        """Render and execute one partition statement, then refresh the cache.

        Invalidation happens only after the statement succeeds: a failed drop
        leaves the table as it was, so the cached listing is still correct and
        must not be thrown away.
        """
        sql, params = statement.to_sql()
        result = self._backend.execute(sql, params)
        self._invalidate(statement.table)
        return result

    def _invalidate(self, table: str) -> None:
        """Drop the cached table-scope answers that mention *table*."""
        self._backend.introspector.invalidate_cache(scope=IntrospectionScope.TABLE, name=table)

    @staticmethod
    def _require_table(table: str) -> None:
        """Refuse an empty table name before a statement is rendered."""
        if not isinstance(table, str) or not table.strip():
            raise ValueError("table must be a non-empty string")
