# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/partition.py
"""ClickHouse table-partition capability and rendering.

ClickHouse partitioning is a property of the ``MergeTree`` family: a
``PARTITION BY <expr>`` clause on ``CREATE TABLE``, where the expression is
any expression over the table's columns (or a tuple of them). There is no
strategy to pick, no ``VALUES`` boundary and no subpartitioning. Declaring the
clause is done by the storage-clause formatter
(:meth:`~.ddl_table_engine.ClickHouseTableEngineMixin.format_table_engine_clauses`,
which renders ``PARTITION BY`` out of the ``storage_options`` mapping); what is
left for this mixin is the capability switches and the three ``ALTER TABLE``
maintenance clauses ClickHouse actually has, each addressed by **partition id**.

References (both fetched and HTTP-resolving):
https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
https://clickhouse.com/docs/sql-reference/statements/alter/partition
"""
from typing import NoReturn, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.partition import (
        ClickHouseAttachPartitionExpression,
        ClickHouseDetachPartitionExpression,
        ClickHouseDropPartitionExpression,
    )


#: The ``ALTER TABLE ... PARTITION`` inventory, transcribed from the ALTER TABLE
#: ... PARTITION reference cited below. This is also what proves the absence of
#: everything else, so it is kept as data rather than prose: a test asserts
#: that nothing in :data:`MYSQL_ONLY_PARTITION_STATEMENTS` /
#: :data:`MYSQL_ONLY_PARTITION_SYNTAX` appears in it.
#:
#: The server's own expectation list is a mild superset of this tuple — it also
#: offers partition-level ``MODIFY TTL`` / ``REMOVE TTL`` / ``MATERIALIZE TTL``
#: and ``UNLOCK SNAPSHOT`` — so nothing here is wrong, but the tuple is not the
#: whole of what ClickHouse accepts either.
ALTER_PARTITION_INVENTORY = (
    "DETACH PARTITION|PART",
    "DROP PARTITION|PART",
    "DROP DETACHED PARTITION|PART",
    "FORGET PARTITION",
    "ATTACH PARTITION|PART",
    "ATTACH PARTITION FROM",
    "REPLACE PARTITION",
    "MOVE PARTITION TO TABLE",
    "CLEAR COLUMN IN PARTITION",
    "CLEAR INDEX IN PARTITION",
    "FREEZE PARTITION",
    "UNFREEZE PARTITION",
    "FETCH PARTITION|PART",
    "MOVE PARTITION|PART TO DISK|VOLUME",
    "UPDATE IN PARTITION",
    "DELETE IN PARTITION",
    "REWRITE PARTS",
)

#: MySQL ``ALTER TABLE`` partition statements with no ClickHouse spelling.
#: Nothing in :data:`ALTER_PARTITION_INVENTORY` matches any of these; asking the
#: server for one returns its expectation list naming every clause it does
#: accept, and none of those names is among them.
MYSQL_ONLY_PARTITION_STATEMENTS = (
    "ADD PARTITION",
    "TRUNCATE PARTITION",
    "REORGANIZE PARTITION",
    "EXCHANGE PARTITION",
    "REMOVE PARTITIONING",
    "COALESCE PARTITION",
    "ANALYZE PARTITION",
    "CHECK PARTITION",
    "OPTIMIZE PARTITION",
    "REBUILD PARTITION",
    "REPAIR PARTITION",
    "SUBPARTITION BY",
)

#: MySQL inline partition syntax with no ClickHouse spelling. Not a statement
#: name, so kept apart from :data:`MYSQL_ONLY_PARTITION_STATEMENTS` to keep that
#: tuple comparable against :data:`ALTER_PARTITION_INVENTORY` entry by entry.
MYSQL_ONLY_PARTITION_SYNTAX = (
    "PARTITION ... VALUES LESS THAN",
    "PARTITION ... VALUES IN",
    "MAXVALUE partition boundary",
)

_PARTITION_ALTERNATIVES = (
    "ClickHouse partitions a MergeTree table with PARTITION BY <expr> in "
    "CREATE TABLE, not with a named RANGE/LIST/HASH/KEY strategy; it is "
    "declared through the storage_options mapping. A partition comes into "
    "existence when a row lands in it, so there is nothing to ADD, and its "
    "contents are addressed by system.parts.partition_id rather than by a "
    "DDL-declared name."
)


class ClickHousePartitionMixin:
    """ClickHouse table-partition support.

    Covers the two things ClickHouse genuinely has — the ``PARTITION BY``
    capability and partition maintenance by partition id — and refuses
    everything the MySQL partition surface asked for. The refusals are
    overrides of the generic ``PartitionSupport`` contract rather than one
    ``supports_*`` switch per MySQL statement: a switch per MySQL statement
    would be an inventory of statements ClickHouse does not have, and the
    authoritative inventory is
    :data:`ALTER_PARTITION_INVENTORY` (see :mod:`..expression.partition`).
    """

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def supports_table_partitioning(self) -> bool:
        """ClickHouse partitions tables, via ``PARTITION BY <expr>`` on MergeTree."""
        return True

    def supports_partitioned_table_creation(self) -> bool:
        """``CREATE TABLE`` may carry the ``PARTITION BY`` clause."""
        return True

    def supports_partition_metadata_introspection(self) -> bool:
        """ClickHouse reports partitions in ``system.parts``.

        The columns that carry the partition are ``partition`` (the key value),
        ``partition_id`` (the id ``ALTER TABLE ... PARTITION ID`` addresses) and
        ``name`` (the part name). ``information_schema.PARTITIONS`` is MySQL's
        and the server rejects that table name.
        """
        return True

    def supports_drop_partition(self) -> bool:
        """``ALTER TABLE ... DROP PARTITION ID`` — supported."""
        return True

    def supports_detach_partition(self) -> bool:
        """``ALTER TABLE ... DETACH PARTITION ID`` — supported."""
        return True

    def supports_attach_partition(self) -> bool:
        """``ALTER TABLE ... ATTACH PARTITION ID`` — supported."""
        return True

    # ------------------------------------------------------------------
    # Refusals
    # ------------------------------------------------------------------

    def format_partition_clause(self, expr) -> Tuple[str, tuple]:
        """Refuse a generic ``PartitionClause``.

        A generic ``PartitionClause`` can only be spelled ``RANGE``/``LIST``/
        ``HASH`` (or the backend's own enum), and none of those is a ClickHouse
        partition key — ClickHouse takes an arbitrary expression instead. The
        honest refusal points at where ``PARTITION BY`` *is* written.
        """
        self._refuse_mysql_partition("declarative PARTITION BY <strategy>")

    def format_partition_definition(self, definition) -> Tuple[str, tuple]:
        """Refuse an inline ``PARTITION ... VALUES ...`` definition.

        ClickHouse has no inline partition definitions: a partition is not
        declared in the table's DDL, so there is nothing for a definition to
        render.
        """
        self._refuse_mysql_partition("inline partition definitions")

    def _refuse_mysql_partition(self, feature: str) -> NoReturn:
        """Raise ``UnsupportedFeatureError`` naming ClickHouse's partitioning."""
        raise UnsupportedFeatureError(self.name, feature, _PARTITION_ALTERNATIVES)

    # ------------------------------------------------------------------
    # Formatters — the three maintenance clauses ClickHouse has
    # ------------------------------------------------------------------

    def format_drop_partition_statement(
        self, expr: "ClickHouseDropPartitionExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... DROP PARTITION ID '<id>'``.

        Raises:
            UnsupportedFeatureError: if ``expr`` does not carry a partition id.
        """
        return self._format_partition_id_statement(expr, "DROP")

    def format_detach_partition_statement(
        self, expr: "ClickHouseDetachPartitionExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... DETACH PARTITION ID '<id>'``.

        Raises:
            UnsupportedFeatureError: if ``expr`` does not carry a partition id.
        """
        return self._format_partition_id_statement(expr, "DETACH")

    def format_attach_partition_statement(
        self, expr: "ClickHouseAttachPartitionExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... ATTACH PARTITION ID '<id>'``.

        Raises:
            UnsupportedFeatureError: if ``expr`` does not carry a partition id.
        """
        return self._format_partition_id_statement(expr, "ATTACH")

    def _format_partition_id_statement(self, expr, verb: str) -> Tuple[str, tuple]:
        """Render one ``ALTER TABLE ... <verb> PARTITION ID '<id>'`` statement.

        The id is an inline literal rather than a bind parameter because an
        ``ALTER`` clause is DDL-shaped: the partition id is chosen by the
        caller, not derived from a column value, so there is no query-planning
        benefit in parameterising it.
        """
        partition_id = getattr(expr, "partition_id", None)
        if not isinstance(partition_id, str) or not partition_id.strip():
            raise UnsupportedFeatureError(
                self.name,
                f"{verb} PARTITION",
                _PARTITION_ALTERNATIVES,
            )
        from rhosocial.activerecord.backend.expression.objects import Table

        # The expression stores the bare name (and the database, when given)
        # so its round trip carries exactly what the constructor accepted; the
        # catalog slot is where ClickHouse keeps its database, so that is where
        # the name is qualified here, at render time.
        table_sql, table_params = self.format_table_object(
            Table(self, expr.table, catalog_name=expr.schema)
        )
        return (
            f"ALTER TABLE {table_sql} {verb} PARTITION ID "
            f"{self.format_literal(partition_id)}",
            tuple(table_params),
        )