# tests/test_change_suggestion_contract.py
"""Contract for ClickHouse's four migration change-point suggestions.

Offline only: a ``ClickHouseDialect`` renders expression nodes without a
connection, so this module runs with ``--noconftest`` next to the existing
partition-suggestion contract. For each protocol it pins the tri-state value,
the exact SQL of any supported chain, the evidence behind an explicit
``False``, and -- for partition scheme changes -- a guard that none of the
verbs ClickHouse's reference refuses can be emitted.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddIndexAction,
    AddTableConstraintAction,
    AlterTableStatement,
    DropTableConstraintAction,
    ModifyColumnAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnDefinition,
    TableCheckConstraint,
    TableConstraint,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression import (
    ClickHouseAttachPartitionStatement,
    ClickHouseClearInPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseDropPartitionStatement,
    ClickHouseFreezePartitionStatement,
    ClickHouseIndexDefinition,
    ClickHouseMovePartitionStatement,
    ClickHouseOptimizePartitionStatement,
    ClickHouseReplacePartitionStatement,
    ClickHouseUnfreezePartitionStatement,
)
from rhosocial.activerecord.backend.impl.clickhouse.suggestion import (
    ClickHouseColumnReorderSuggestionMixin,
    ClickHousePartitionSchemeChangeSuggestionMixin,
    ClickHouseTableConstraintChangeSuggestionMixin,
    ClickHouseTableIndexChangeSuggestionMixin,
)
from rhosocial.activerecord.backend.suggestion.definitions import (
    ColumnReorderSuggestion,
    PartitionSchemeChangeSuggestion,
    TableConstraintChangeSuggestion,
    TableIndexChangeSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    ColumnReorderSuggestionSupport,
    PartitionSchemeChangeSuggestionSupport,
    TableConstraintChangeSuggestionSupport,
    TableIndexChangeSuggestionSupport,
)


@pytest.fixture
def dialect():
    return ClickHouseDialect((26, 7, 3))


MIXINS = [
    ClickHouseColumnReorderSuggestionMixin,
    ClickHouseTableConstraintChangeSuggestionMixin,
    ClickHouseTableIndexChangeSuggestionMixin,
    ClickHousePartitionSchemeChangeSuggestionMixin,
]
PROTOCOLS = [
    ColumnReorderSuggestionSupport,
    TableConstraintChangeSuggestionSupport,
    TableIndexChangeSuggestionSupport,
    PartitionSchemeChangeSuggestionSupport,
]


def test_dialect_carries_the_change_suggestion_mixins():
    for mixin in MIXINS:
        assert issubclass(ClickHouseDialect, mixin), mixin.__name__


def test_dialect_satisfies_all_four_protocols(dialect):
    for protocol in PROTOCOLS:
        assert isinstance(dialect, protocol), protocol.__name__


def _sql(operations):
    return [expr.to_sql()[0] for expr in operations]


# -- Column reorder ---------------------------------------------------------


class TestColumnReorder:
    def test_tristate_is_explicit_unsupported(self, dialect):
        answer = dialect.suggest_column_reorder(
            ColumnReorderSuggestion(
                table_name="events",
                old_order=("id", "ts", "url"),
                new_order=("id", "url", "ts"),
                reordered_columns=("ts", "url"),
            )
        )
        assert answer.operations is False
        assert answer.state == "unaddressable"
        assert dialect.suggest_column_reorder(ColumnReorderSuggestion()).state == "unaddressable"

    def test_evidence_new_column_after_exists_but_reposition_does_not(self, dialect):
        """The refusal is specific: ADD COLUMN has AFTER, existing columns don't.

        The only positional node is ``ClickHouseAddColumnAction``. The portable
        MODIFY COLUMN action refuses the same modifier rather than guess at
        ClickHouse's separate full-type repositioning production.
        """
        from rhosocial.activerecord.backend.impl.clickhouse.expression import (
            ClickHouseAddColumnAction,
        )

        from rhosocial.activerecord.backend.expression.objects import Table

        column = ColumnDefinition(dialect, "age", IntegerType(dialect))
        add = ClickHouseAddColumnAction(dialect, column, after="name")
        add_statement = AlterTableStatement(dialect, Table(dialect, "t"), [add])
        assert add_statement.to_sql()[0] == (
            "ALTER TABLE `t` ADD COLUMN `age` Int32 AFTER `name`"
        )
        portable = ModifyColumnAction(dialect, column, after_column="name")
        with pytest.raises(UnsupportedFeatureError, match="MODIFY COLUMN FIRST/AFTER"):
            portable.to_sql()

    def test_answer_carries_no_expression(self, dialect):
        answer = dialect.suggest_column_reorder(
            ColumnReorderSuggestion(table_name="events", reordered_columns=("a", "b"))
        )
        assert not isinstance(answer.operations, tuple)


# -- Table constraint change ------------------------------------------------


def _check(dialect, name="ck"):
    condition = ComparisonPredicate(dialect, "=", Column(dialect, "a"), Column(dialect, "b"))
    return TableConstraint(
        dialect, branch=TableCheckConstraint(dialect, condition), name=name
    )


class TestTableConstraintChange:
    def test_no_change_has_no_answer(self, dialect):
        check = _check(dialect)
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=(check,), new_constraints=(check,)
            )
        )
        assert answer.operations is None
        assert answer.state == "absent"

    def test_add_check_renders_one_action_per_statement(self, dialect):
        check = _check(dialect)
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=(), new_constraints=(check,)
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 1
        assert isinstance(operations[0], AlterTableStatement)
        assert len(operations[0].actions) == 1
        assert isinstance(operations[0].actions[0], AddTableConstraintAction)
        assert all(isinstance(node, BaseExpression) for node in operations)
        assert _sql(operations) == [
            "ALTER TABLE `events` ADD CONSTRAINT `ck` CHECK (`a` = `b`)"
        ]

    def test_drop_from_a_frozen_projection_renders_if_exists(self, dialect):
        frozen_old = ("params", (("branch", ("repr", "CHECK")), ("name", "ck")))
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=(frozen_old,), new_constraints=()
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 1
        assert isinstance(operations[0].actions[0], DropTableConstraintAction)
        assert _sql(operations) == ["ALTER TABLE `events` DROP CONSTRAINT IF EXISTS `ck`"]

    def test_changed_declaration_drops_then_adds(self, dialect):
        old = _check(dialect)
        new = _check(dialect)
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=(old,), new_constraints=(new,)
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 2
        assert _sql(operations) == [
            "ALTER TABLE `events` DROP CONSTRAINT IF EXISTS `ck`",
            "ALTER TABLE `events` ADD CONSTRAINT `ck` CHECK (`a` = `b`)",
        ]

    def test_non_check_add_is_declined(self, dialect):
        unique = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["a"]), name="uq"
        )
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=(), new_constraints=(unique,)
            )
        )
        assert answer.operations is False

    def test_frozen_add_is_declined_without_a_partial_chain(self, dialect):
        frozen = ("params", (("name", "ck"),))
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=(), new_constraints=(frozen,)
            )
        )
        assert answer.operations is False

    def test_missing_table_is_declined(self, dialect):
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                old_constraints=(), new_constraints=(_check(dialect),)
            )
        )
        assert answer.operations is False

    def test_evidence_add_drop_exist_and_modify_does_not(self, dialect):
        assert dialect.supports_add_constraint() is True
        assert dialect.supports_drop_constraint() is True
        assert dialect.supports_alter_constraint() is False


# -- Table index change -----------------------------------------------------


class TestTableIndexChange:
    def test_change_is_declined_and_no_change_has_no_answer(self, dialect):
        changed = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events", old_indexes=("old",), new_indexes=("new",)
            )
        )
        assert changed.operations is False
        assert changed.state == "unaddressable"
        unchanged = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events", old_indexes=("i",), new_indexes=("i",)
            )
        )
        assert unchanged.operations is None
        assert unchanged.state == "absent"

    def test_evidence_skip_index_alter_exists_but_has_no_node(self, dialect):
        """ALTER INDEX is real on ClickHouse; the missing piece is a node.

        ``supports_index_if_not_exists`` / ``supports_index_if_exists`` are the
        probes for the real skip-index commands, while the core ALTER INDEX
        actions render MySQL's form and are gated off by this dialect. The only
        index node here is the inline CREATE TABLE definition.
        """
        assert dialect.supports_index_if_not_exists() is True
        assert dialect.supports_index_if_exists() is True
        assert dialect.supports_alter_table_index_actions() is False
        index = ClickHouseIndexDefinition(
            dialect, "idx", ["a"], type="minmax", granularity=4
        )
        assert index.to_sql()[0] == "INDEX `idx` (`a`) TYPE minmax GRANULARITY 4"
        with pytest.raises(UnsupportedFeatureError, match="ALTER TABLE ADD INDEX"):
            AddIndexAction(dialect, index).to_sql()


# -- Partition scheme change ------------------------------------------------


def _scheme(old, new, table="visits"):
    return PartitionSchemeChangeSuggestion(
        table_name=table, old_partition=old, new_partition=new
    )


class TestPartitionSchemeChange:
    def test_bare_declaration_change_is_declined(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            _scheme({"key": "toYYYYMM(ts)"}, {"key": "toYYYY(year(ts))"})
        )
        assert answer.operations is False
        assert answer.state == "unaddressable"

    def test_no_change_has_no_answer(self, dialect):
        declaration = {"key": "toYYYYMM(ts)"}
        answer = dialect.suggest_partition_scheme_change(_scheme(declaration, declaration))
        assert answer.operations is None

    def test_supported_chain_renders_exact_sql(self, dialect):
        point = _scheme(
            {"operations": [{"operation": "freeze", "backup_name": "before"}]},
            {
                "operations": [
                    {"operation": "detach", "partition_id": "202601"},
                    {"operation": "attach", "partition_id": "202601"},
                    {
                        "operation": "replace",
                        "partition_id": "202601",
                        "source_table": "visits_stage",
                    },
                    {
                        "operation": "move",
                        "partition_id": "202601",
                        "destination": "TABLE",
                        "target": "visits_archive",
                    },
                    {"operation": "unfreeze", "backup_name": "before"},
                    {"operation": "clear", "kind": "INDEX", "name": "idx", "partition_id": "202601"},
                    {"operation": "optimize"},
                ]
            },
        )
        answer = dialect.suggest_partition_scheme_change(point)
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 8
        assert all(isinstance(node, BaseExpression) for node in operations)
        assert [type(node) for node in operations] == [
            ClickHouseFreezePartitionStatement,
            ClickHouseDetachPartitionStatement,
            ClickHouseAttachPartitionStatement,
            ClickHouseReplacePartitionStatement,
            ClickHouseMovePartitionStatement,
            ClickHouseUnfreezePartitionStatement,
            ClickHouseClearInPartitionStatement,
            ClickHouseOptimizePartitionStatement,
        ]
        assert _sql(operations) == [
            "ALTER TABLE `visits` FREEZE WITH NAME 'before'",
            "ALTER TABLE `visits` DETACH PARTITION ID '202601'",
            "ALTER TABLE `visits` ATTACH PARTITION ID '202601'",
            "ALTER TABLE `visits` REPLACE PARTITION ID '202601' FROM `visits_stage`",
            "ALTER TABLE `visits` MOVE PARTITION ID '202601' TO TABLE `visits_archive`",
            "ALTER TABLE `visits` UNFREEZE WITH NAME 'before'",
            "ALTER TABLE `visits` CLEAR INDEX `idx` IN PARTITION ID '202601'",
            "OPTIMIZE TABLE `visits` FINAL",
        ]

    def test_drop_is_reused(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            _scheme(None, {"operations": [{"operation": "drop", "partition_id": "202601"}]})
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 1
        assert isinstance(operations[0], ClickHouseDropPartitionStatement)
        assert _sql(operations) == ["ALTER TABLE `visits` DROP PARTITION ID '202601'"]

    @pytest.mark.parametrize(
        "refused",
        ["REORGANIZE", "EXCHANGE", "COALESCE", "REMOVE PARTITIONING", "SUBPARTITION"],
    )
    def test_refused_verbs_never_emit_an_operation(self, dialect, refused):
        answer = dialect.suggest_partition_scheme_change(
            _scheme(
                None,
                {
                    "operations": [
                        {"operation": "freeze", "backup_name": "before"},
                        {"operation": refused},
                    ]
                },
            )
        )
        assert answer.operations is False
        assert not isinstance(answer.operations, tuple)

    def test_refused_set_is_exactly_the_five_absent_verbs(self):
        from rhosocial.activerecord.backend.impl.clickhouse.suggestion import (
            partition_scheme_change_suggestion as module,
        )

        assert module.REFUSED_OPERATIONS == {
            "reorganize",
            "exchange",
            "coalesce",
            "remove_partitioning",
            "subpartition",
        }

    def test_no_emitted_statement_contains_a_refused_verb(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            _scheme(
                None,
                {
                    "operations": [
                        {"operation": "freeze", "backup_name": "before"},
                        {"operation": "detach", "partition_id": "202601"},
                        {"operation": "attach", "partition_id": "202601"},
                        {"operation": "optimize"},
                    ]
                },
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple)
        for sql in _sql(operations):
            assert not any(
                verb in sql.upper()
                for verb in ("REORGANIZE", "EXCHANGE", "COALESCE", "REMOVE PARTITIONING", "SUBPARTITION")
            )

    def test_unknown_or_malformed_request_is_declined(self, dialect):
        for request in ({"operation": "vacuum"}, {"partition_id": "202601"}, 42):
            answer = dialect.suggest_partition_scheme_change(
                _scheme(None, {"operations": [request]})
            )
            assert answer.operations is False

    def test_missing_parameters_are_not_guessed(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            _scheme(None, {"operations": [{"operation": "detach"}]})
        )
        assert answer.operations is False

    def test_each_operation_is_gated_by_its_probe(self, dialect, monkeypatch):
        monkeypatch.setattr(dialect, "supports_detach_partition", lambda: False)
        answer = dialect.suggest_partition_scheme_change(
            _scheme(
                None,
                {
                    "operations": [
                        {"operation": "detach", "partition_id": "202601"},
                        {"operation": "optimize"},
                    ]
                },
            )
        )
        assert answer.operations is False

    def test_missing_table_is_declined(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            PartitionSchemeChangeSuggestion(
                old_partition=None,
                new_partition={"operations": [{"operation": "optimize"}]},
            )
        )
        assert answer.operations is False
