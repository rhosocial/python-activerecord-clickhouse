# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/partition.py
"""ClickHouse table-partition capability and rendering.

ClickHouse partitioning is a property of the ``MergeTree`` family: a
``PARTITION BY <expr>`` clause on ``CREATE TABLE``, where the expression is
any expression over the table's columns (or a tuple of them). There is no
strategy to pick, no ``VALUES`` boundary and no subpartitioning. Declaring the
clause is done by the storage-clause formatter
(:meth:`~.ddl_table_engine.ClickHouseTableEngineMixin.format_table_engine_clauses`,
which renders ``PARTITION BY`` out of the ``storage_options`` mapping); what is
left for this mixin is the support switches and the three ``ALTER TABLE``
maintenance clauses ClickHouse actually has, each addressed by **partition id**.

References (both fetched and HTTP-resolving):
https://clickhouse.com/docs/engines/table-engines/mergetree-family/custom-partitioning-key
https://clickhouse.com/docs/sql-reference/statements/alter/partition
"""
from typing import NoReturn, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.partition import (
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

    def supports_replace_partition(self) -> bool:
        """``ALTER TABLE ... REPLACE PARTITION ID '<id>' FROM <table>`` — supported.

        The reference spells ``REPLACE PARTITION partition_expr FROM table1``;
        the expression node renders the partition-id form of ``partition_expr``.
        """
        return True

    def supports_move_partition(self) -> bool:
        """``ALTER TABLE ... MOVE PARTITION ... TO DISK|VOLUME|TABLE`` — supported."""
        return True

    def supports_freeze_partition(self) -> bool:
        """``ALTER TABLE ... FREEZE [PARTITION ...] [WITH NAME ...]`` — supported."""
        return True

    def supports_unfreeze_partition(self) -> bool:
        """``ALTER TABLE ... UNFREEZE [PARTITION ...] WITH NAME ...`` — supported."""
        return True

    def supports_clear_in_partition(self) -> bool:
        """``ALTER TABLE ... CLEAR COLUMN|INDEX|PROJECTION ... IN PARTITION`` — supported."""
        return True

    def supports_optimize_partition_final(self) -> bool:
        """``OPTIMIZE TABLE ... [PARTITION ...] [FINAL]`` — supported.

        Named with the ClickHouse-only clauses rather than
        ``supports_optimize_partition``: that spelling is MySQL's maintenance
        statement, which this backend deliberately refuses (see
        ``ClickHouseMaintenanceMixin``).
        """
        return True

    # ------------------------------------------------------------------
    # The action family: what a plan may ask to do to a partition
    # ------------------------------------------------------------------
    # ClickHouse partitions are ranges of parts on disk, and the engine
    # derives them from the ``PARTITION BY`` expression; only the statements
    # this backend can render answer True. Every other name is a definite
    # False -- the statement does not exist -- rather than a gap in the
    # implementation.

    def supports_add_partition(self) -> bool:
        """False: partitions appear from inserts; there is no ADD PARTITION."""
        return False

    def supports_truncate_partition(self) -> bool:
        """False: no TRUNCATE PARTITION; ``DROP PARTITION`` is the per-range removal."""
        return False

    def supports_split_partition(self) -> bool:
        """False: no SPLIT PARTITION statement."""
        return False

    def supports_merge_partition(self) -> bool:
        """False: no MERGE PARTITION statement."""
        return False

    def supports_exchange_partition(self) -> bool:
        """False: no swap with a standalone table.

        ``REPLACE PARTITION`` consumes another table's parts and has its own
        switch; it is not the two-way exchange other engines offer.
        """
        return False

    def supports_reorganize_partition(self) -> bool:
        """False: MySQL's REORGANIZE PARTITION has no ClickHouse counterpart."""
        return False

    def supports_coalesce_partition(self) -> bool:
        """False: the partition count is not a hash modulus that can be reduced."""
        return False

    def supports_analyze_partition(self) -> bool:
        """False: no ANALYZE PARTITION; ``OPTIMIZE`` merges parts instead."""
        return False

    def supports_check_partition(self) -> bool:
        """False: no CHECK PARTITION statement."""
        return False

    def supports_optimize_partition(self) -> bool:
        """False: this name is MySQL's statement; the engine's form is FINAL.

        See :meth:`supports_optimize_partition_final`.
        """
        return False

    def supports_rebuild_partition(self) -> bool:
        """False: no REBUILD PARTITION statement."""
        return False

    def supports_repair_partition(self) -> bool:
        """False: no REPAIR PARTITION statement."""
        return False

    def supports_remove_partitioning(self) -> bool:
        """False: ``PARTITION BY`` is fixed at CREATE; changing it needs a new table."""
        return False

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

    def format_partition_definition(self, expr) -> Tuple[str, tuple]:
        """Refuse an inline ``PARTITION ... VALUES ...`` definition.

        ClickHouse has no inline partition definitions: a partition is not
        declared in the table's DDL, so there is nothing for a definition to
        render.
        """
        self._refuse_mysql_partition("inline partition definitions")

    def format_partition_definition_expression(self, expr) -> Tuple[str, tuple]:
        """Node entry for an inline ``PARTITION ... VALUES ...`` definition.

        Core's PartitionDefinitionExpression dispatches to this name; ClickHouse
        has no inline partition definitions, so it refuses exactly as
        ``format_partition_definition`` does.
        """
        return self.format_partition_definition(expr)

    def _refuse_mysql_partition(self, feature: str) -> NoReturn:
        """Raise ``UnsupportedFeatureError`` naming ClickHouse's partitioning."""
        raise UnsupportedFeatureError(self.name, feature, _PARTITION_ALTERNATIVES)

    # ------------------------------------------------------------------
    # Formatters — the partition maintenance clauses ClickHouse has
    # ------------------------------------------------------------------

    def format_drop_partition_statement(
        self, expr: "ClickHouseDropPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... DROP PARTITION ID '<id>'``.

        The id is an inline literal rather than a bind parameter because an
        ``ALTER`` clause is DDL-shaped: the partition id is chosen by the
        caller, not derived from a column value, so there is no query-planning
        benefit in parameterising it.

        Raises:
            TypeError: if ``expr`` is not a ``ClickHouseDropPartitionStatement``.
            UnsupportedFeatureError: if ``expr`` does not carry a partition id.
        """
        from ..expression.partition import ClickHouseDropPartitionStatement

        if not isinstance(expr, ClickHouseDropPartitionStatement):
            raise TypeError(
                "format_drop_partition_statement expects a "
                "ClickHouseDropPartitionStatement, "
                f"got {type(expr).__name__}"
            )
        partition_id = expr.partition_id
        if not isinstance(partition_id, str) or not partition_id.strip():
            raise UnsupportedFeatureError(
                self.name, "DROP PARTITION", _PARTITION_ALTERNATIVES
            )
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        return (
            f"ALTER TABLE {table_sql} DROP "
            f"{self._partition_expression(partition_id)}",
            (),
        )

    def format_detach_partition_statement(
        self, expr: "ClickHouseDetachPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... DETACH PARTITION ID '<id>'``.

        The id is an inline literal rather than a bind parameter because an
        ``ALTER`` clause is DDL-shaped: the partition id is chosen by the
        caller, not derived from a column value, so there is no query-planning
        benefit in parameterising it.

        Raises:
            TypeError: if ``expr`` is not a ``ClickHouseDetachPartitionStatement``.
            UnsupportedFeatureError: if ``expr`` does not carry a partition id.
        """
        from ..expression.partition import ClickHouseDetachPartitionStatement

        if not isinstance(expr, ClickHouseDetachPartitionStatement):
            raise TypeError(
                "format_detach_partition_statement expects a "
                "ClickHouseDetachPartitionStatement, "
                f"got {type(expr).__name__}"
            )
        partition_id = expr.partition_id
        if not isinstance(partition_id, str) or not partition_id.strip():
            raise UnsupportedFeatureError(
                self.name, "DETACH PARTITION", _PARTITION_ALTERNATIVES
            )
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        return (
            f"ALTER TABLE {table_sql} DETACH "
            f"{self._partition_expression(partition_id)}",
            (),
        )

    def format_attach_partition_statement(
        self, expr: "ClickHouseAttachPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... ATTACH PARTITION ID '<id>'``.

        The id is an inline literal rather than a bind parameter because an
        ``ALTER`` clause is DDL-shaped: the partition id is chosen by the
        caller, not derived from a column value, so there is no query-planning
        benefit in parameterising it.

        Raises:
            TypeError: if ``expr`` is not a ``ClickHouseAttachPartitionStatement``.
            UnsupportedFeatureError: if ``expr`` does not carry a partition id.
        """
        from ..expression.partition import ClickHouseAttachPartitionStatement

        if not isinstance(expr, ClickHouseAttachPartitionStatement):
            raise TypeError(
                "format_attach_partition_statement expects a "
                "ClickHouseAttachPartitionStatement, "
                f"got {type(expr).__name__}"
            )
        partition_id = expr.partition_id
        if not isinstance(partition_id, str) or not partition_id.strip():
            raise UnsupportedFeatureError(
                self.name, "ATTACH PARTITION", _PARTITION_ALTERNATIVES
            )
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        return (
            f"ALTER TABLE {table_sql} ATTACH "
            f"{self._partition_expression(partition_id)}",
            (),
        )

    # ------------------------------------------------------------------
    # Formatters — the remaining ClickHouse partition operations
    # ------------------------------------------------------------------

    def format_replace_partition_statement(
        self, expr: "ClickHouseReplacePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... REPLACE PARTITION ID '<id>' FROM <table>``.

        Official reference ("REPLACE PARTITION"):
        https://clickhouse.com/docs/sql-reference/statements/alter/partition

        Raises:
            UnsupportedFeatureError: if the table, partition id or source
                table is missing or not a non-empty string. The grammar has no
                ``REPLACE PARTITION`` without a source, so there is no SQL to
                render for that shape.
        """
        detail = (
            "REPLACE PARTITION needs a target table, the partition id from "
            "system.parts.partition_id, and a source table: the reference spells "
            "``ALTER TABLE table2 REPLACE PARTITION partition_expr FROM table1``."
        )
        self._require_partition_target(expr, "REPLACE PARTITION", detail)
        self._require_name(expr.source_table, "REPLACE PARTITION", detail)
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        source_sql = self._partition_table_sql(expr.source_table, expr.source_schema)
        return (
            f"ALTER TABLE {table_sql} REPLACE PARTITION ID "
            f"{self.format_literal(expr.partition_id)} FROM {source_sql}",
            (),
        )

    def format_move_partition_statement(
        self, expr: "ClickHouseMovePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... MOVE PARTITION ID '<id>' TO <target>``.

        ``DISK`` and ``VOLUME`` name a configured storage device and are
        rendered as quoted literals, as the reference spells them; ``TABLE``
        names another table and is rendered as an identifier. Official
        reference ("MOVE PARTITION|PART" and "MOVE PARTITION TO TABLE"):
        https://clickhouse.com/docs/sql-reference/statements/alter/partition

        Raises:
            UnsupportedFeatureError: if the table, partition id or target is
                missing/blank, or if ``destination`` is not ``DISK``, ``VOLUME``
                or ``TABLE``.
        """
        detail = (
            "MOVE PARTITION is spelled ``ALTER TABLE table_name MOVE PARTITION "
            "partition_expr TO DISK|VOLUME 'name'`` or ``... TO TABLE table_dest``."
        )
        self._require_partition_target(expr, "MOVE PARTITION", detail)
        destination = self._partition_kind(expr.destination, "MOVE PARTITION", detail)
        if destination not in ("DISK", "VOLUME", "TABLE"):
            raise UnsupportedFeatureError(
                self.name,
                f"MOVE PARTITION TO {destination or expr.destination}",
                detail,
            )
        self._require_name(expr.target, "MOVE PARTITION", detail)
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        if destination == "TABLE":
            target_sql = self._partition_table_sql(expr.target, expr.target_schema)
        else:
            target_sql = self.format_literal(expr.target)
        return (
            f"ALTER TABLE {table_sql} MOVE PARTITION ID "
            f"{self.format_literal(expr.partition_id)} TO {destination} {target_sql}",
            (),
        )

    def format_freeze_partition_statement(
        self, expr: "ClickHouseFreezePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... FREEZE [PARTITION ID '<id>'] [WITH NAME '<name>']``.

        Both clauses are optional in the reference grammar: omitting
        ``PARTITION`` freezes every partition, omitting ``WITH NAME`` lets the
        server pick the next incremental number. A present-but-blank value is
        refused, because it renders as an empty partition id or an empty backup
        name rather than as "absent".

        Official reference ("FREEZE PARTITION"):
        https://clickhouse.com/docs/sql-reference/statements/alter/partition

        Raises:
            UnsupportedFeatureError: if the table is missing, or a supplied
                partition id / backup name is not a non-empty string.
        """
        detail = (
            "FREEZE is spelled ``ALTER TABLE table_name FREEZE [PARTITION "
            "partition_expr] [WITH NAME 'backup_name']``."
        )
        self._require_name(expr.table, "FREEZE PARTITION", detail)
        self._require_optional_name(expr.partition_id, "FREEZE PARTITION", detail)
        self._require_optional_name(expr.name, "FREEZE PARTITION", detail)
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        parts = [f"ALTER TABLE {table_sql} FREEZE"]
        if expr.partition_id is not None:
            parts.append(f"PARTITION ID {self.format_literal(expr.partition_id)}")
        if expr.name is not None:
            parts.append(f"WITH NAME {self.format_literal(expr.name)}")
        return " ".join(parts), ()

    def format_unfreeze_partition_statement(
        self, expr: "ClickHouseUnfreezePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... UNFREEZE [PARTITION ID '<id>'] WITH NAME '<name>'``.

        ``WITH NAME`` is mandatory here, unlike on ``FREEZE``: the reference
        grammar shows it without brackets, and ``UNFREEZE`` has no incremental
        number to fall back to. The partition clause stays optional.

        Official reference ("UNFREEZE PARTITION"):
        https://clickhouse.com/docs/sql-reference/statements/alter/partition

        Raises:
            UnsupportedFeatureError: if the table is missing, the backup name
                is missing/blank, or a supplied partition id is blank. The
                missing name is refused by name rather than rendered as
                ``UNFREEZE`` without ``WITH NAME``, which the server cannot
                parse.
        """
        detail = (
            "UNFREEZE is spelled ``ALTER TABLE table_name UNFREEZE [PARTITION "
            "'part_expr'] WITH NAME 'backup_name'``; the reference gives WITH "
            "NAME no brackets, so it is required."
        )
        self._require_name(expr.table, "UNFREEZE PARTITION", detail)
        self._require_optional_name(expr.partition_id, "UNFREEZE PARTITION", detail)
        if expr.name is None or not isinstance(expr.name, str) or not expr.name.strip():
            raise UnsupportedFeatureError(
                self.name, "UNFREEZE PARTITION WITH NAME", detail
            )
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        parts = [f"ALTER TABLE {table_sql} UNFREEZE"]
        if expr.partition_id is not None:
            parts.append(f"PARTITION ID {self.format_literal(expr.partition_id)}")
        parts.append(f"WITH NAME {self.format_literal(expr.name)}")
        return " ".join(parts), ()

    def format_clear_in_partition_statement(
        self, expr: "ClickHouseClearInPartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... CLEAR {COLUMN|INDEX|PROJECTION} <name> [IN PARTITION ID '<id>']``.

        ``IN PARTITION`` is required for ``COLUMN`` and ``INDEX`` but optional
        for ``PROJECTION``; that asymmetry is the reference's, so the formatter
        refuses a missing partition for the first two and renders the
        table-wide form for the third.

        References:
        https://clickhouse.com/docs/sql-reference/statements/alter/partition
        https://clickhouse.com/docs/sql-reference/statements/alter/column
        https://clickhouse.com/docs/sql-reference/statements/alter/projection

        Raises:
            UnsupportedFeatureError: if the table or the cleared object's name
                is missing, if ``kind`` is not one of the three keywords, or if
                a ``COLUMN`` / ``INDEX`` clear carries no partition id.
        """
        detail = (
            "CLEAR is spelled ``ALTER TABLE table_name CLEAR COLUMN column_name "
            "IN PARTITION partition_expr`` or the same with INDEX, or "
            "``CLEAR PROJECTION projection_name [IN PARTITION partition_expr]``."
        )
        self._require_name(expr.table, "CLEAR IN PARTITION", detail)
        kind = self._partition_kind(expr.kind, "CLEAR IN PARTITION", detail)
        if kind not in ("COLUMN", "INDEX", "PROJECTION"):
            raise UnsupportedFeatureError(
                self.name,
                f"CLEAR {kind or expr.kind} IN PARTITION",
                detail,
            )
        self._require_name(expr.name, f"CLEAR {kind} IN PARTITION", detail)
        if kind != "PROJECTION" and (
            expr.partition_id is None
            or not isinstance(expr.partition_id, str)
            or not expr.partition_id.strip()
        ):
            raise UnsupportedFeatureError(
                self.name, f"CLEAR {kind} IN PARTITION", detail
            )
        self._require_optional_name(
            expr.partition_id, f"CLEAR {kind} IN PARTITION", detail
        )
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        parts = [
            f"ALTER TABLE {table_sql} CLEAR {kind}",
            self.format_identifier(expr.name),
        ]
        if expr.partition_id is not None:
            parts.append(f"IN {self._partition_expression(expr.partition_id)}")
        return " ".join(parts), ()

    def format_optimize_partition_final_statement(
        self, expr: "ClickHouseOptimizePartitionStatement"
    ) -> Tuple[str, tuple]:
        """Render ``OPTIMIZE TABLE ... [PARTITION ID '<id>'] [FINAL]``.

        A statement of its own, not an ``ALTER TABLE`` action. ``FINAL`` is
        omitted only when the caller asked for the plain form; the partition
        clause is optional in the grammar.

        Official reference:
        https://clickhouse.com/docs/sql-reference/statements/optimize

        Raises:
            UnsupportedFeatureError: if the table is missing, a supplied
                partition id is blank, or ``final`` is not a bool. A non-bool
                would be truthiness-rendered, which turns ``"no"`` into
                ``FINAL``; refusing is the only truthful answer.
        """
        detail = (
            "OPTIMIZE is spelled ``OPTIMIZE TABLE [db.]name [PARTITION "
            "partition | PARTITION ID 'partition_id'] [FINAL]``."
        )
        self._require_name(expr.table, "OPTIMIZE TABLE", detail)
        self._require_optional_name(expr.partition_id, "OPTIMIZE TABLE", detail)
        if not isinstance(expr.final, bool):
            raise UnsupportedFeatureError(
                self.name, "OPTIMIZE TABLE ... FINAL", detail
            )
        table_sql = self._partition_table_sql(expr.table, expr.schema)
        parts = [f"OPTIMIZE TABLE {table_sql}"]
        if expr.partition_id is not None:
            parts.append(f"PARTITION ID {self.format_literal(expr.partition_id)}")
        if expr.final:
            parts.append("FINAL")
        return " ".join(parts), ()

    # ------------------------------------------------------------------
    # Helpers shared by the statements above
    # ------------------------------------------------------------------

    def _partition_table_sql(self, table: str, schema: Optional[str]) -> str:
        """Render a table name with the database in ClickHouse's catalog slot."""
        from rhosocial.activerecord.backend.expression.objects import Table

        table_sql, _params = self.format_table_object(
            Table(self, table, catalog_name=schema)
        )
        return table_sql

    def _partition_expression(self, partition_id: str) -> str:
        """Render the partition-id form of ``partition_expr``."""
        return f"PARTITION ID {self.format_literal(partition_id)}"

    def _require_partition_target(self, expr, feature: str, detail: str) -> None:
        """Require a non-empty table and partition id on *expr*."""
        self._require_name(expr.table, feature, detail)
        if (
            expr.partition_id is None
            or not isinstance(expr.partition_id, str)
            or not expr.partition_id.strip()
        ):
            raise UnsupportedFeatureError(self.name, feature, detail)

    def _require_name(self, value, feature: str, detail: str) -> None:
        """Require a non-empty string; the statement cannot be aimed without it."""
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedFeatureError(self.name, feature, detail)

    def _require_optional_name(self, value, feature: str, detail: str) -> None:
        """Allow ``None``, but refuse a present value that is not a non-empty string."""
        if value is None:
            return
        self._require_name(value, feature, detail)

    def _partition_kind(self, value, feature: str, detail: str) -> str:
        """Normalise a keyword, or return ``""`` for a non-string value."""
        if not isinstance(value, str):
            return ""
        return value.strip().upper()
