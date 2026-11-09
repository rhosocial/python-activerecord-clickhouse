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

Those are the only three management verbs ClickHouse has. There is no ``ADD
PARTITION`` (a partition appears with its first row), no ``TRUNCATE PARTITION``
(the substitute is ``DELETE IN PARTITION``), no ``REORGANIZE`` / ``EXCHANGE`` /
``COALESCE`` / ``REMOVE PARTITIONING``, and no ``SUBPARTITION BY``: ClickHouse
partitions one level, by an arbitrary key expression. The inventory that proves
that absence lives as data in ``mixins/partition.py``
(``ALTER_PARTITION_INVENTORY`` / ``MYSQL_ONLY_PARTITION_STATEMENTS``), and this
module refuses anything outside it rather than inventing a clause the server
would reject.

This is the maintenance layer the plan keeps outside the ``PartitionSupport``
protocol: the protocol answers capability questions and renders ``PARTITION BY``
clauses, not lifecycle. The three verbs are not re-spelled here. Each helper
builds the expression node from ``expression/partition.py`` and executes the SQL
that node renders, so the clause has exactly one home, and :meth:`list` returns
the introspector's own :class:`ClickHousePartitionInfo` rows, whose
``partition_id`` is precisely the value the three helpers take.

No table name, partition name or retention window is defaulted or derived here.
Which tables to maintain, how often, and what to keep belong to the application;
a helper that guessed any of them would be one application's policy written into
the library. Partition ids are assigned by the server, and the three verbs act
on ids that already exist — they cannot create a partition for a future bucket.

Because ClickHouse has no transactions, each call is one statement. A failure
leaves the partition exactly as the server left it, and that outcome is reported
by the raised error rather than hidden behind a rollback that cannot happen.

References (both fetched and HTTP-resolving):
https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
https://clickhouse.com/docs/sql-reference/statements/alter/partition
"""

from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
from rhosocial.activerecord.backend.result import QueryResult

from .expression.partition import (
    ClickHouseAttachPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseDropPartitionStatement,
)
from .introspection.types import ClickHousePartitionInfo

if TYPE_CHECKING:  # pragma: no cover
    from .backend.backend import ClickHouseBackend
    from .dialect import ClickHouseDialect


__all__ = [
    "ClickHousePartitionMaintenance",
    "MANAGEMENT_VERBS",
]


#: The three management verbs, spelled as the helper methods that implement
#: them. :meth:`list` is a read, takes no partition id and is kept out of this
#: tuple so that ``execute`` cannot be asked to "run" it.
MANAGEMENT_VERBS = ("drop", "detach", "attach")


#: What to say when a caller asks for a verb ClickHouse does not have. The
#: suggestion names the three that exist and the substitutions a retention
#: tool is most likely to be reaching for, because "not supported" alone would
#: leave the caller guessing whether the failure was a missing argument.
_UNSUPPORTED_VERB_SUGGESTION = (
    "ClickHouse partition maintenance is DROP / DETACH / ATTACH PARTITION ID; "
    "a partition appears with the first row that lands in it, so ADD has no "
    "clause, TRUNCATE is spelled DELETE IN PARTITION, and there is no "
    "REORGANIZE / EXCHANGE / COALESCE / REMOVE PARTITIONING / SUBPARTITION BY."
)


class ClickHousePartitionMaintenance:
    """The partition maintenance ClickHouse actually has, as four helpers.

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
