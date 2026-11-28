# tests/test_change_suggestion_contract.py
"""Contract for ClickHouse's four migration change-point suggestions.

Offline only: a ``ClickHouseDialect`` renders expression nodes without a
connection, so this module runs with ``--noconftest`` next to the existing
partition-suggestion contract. For each protocol it pins the tri-state value,
the exact SQL of any supported chain, the evidence behind an explicit
``False``, and -- for partition scheme changes -- both a guard against the
verbs ClickHouse's reference refuses and a structural assertion that no chain
destroys data or leaves it outside the table.
"""

import re

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases.bases import BaseExpression
from rhosocial.activerecord.backend.expression.column_types.column import Column
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
    ClickHouseAddIndexStatement,
    ClickHouseAttachPartitionStatement,
    ClickHouseClearInPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseDropIndexStatement,
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
        add_statement = AlterTableStatement(dialect, Table(dialect, "t"), add)
        assert add_statement.to_sql()[0] == ("ALTER TABLE `t` ADD COLUMN `age` Int32 AFTER `name`")
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
    return TableConstraint(dialect, branch=TableCheckConstraint(dialect, condition), name=name)


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
        assert operations[0].action is not None
        assert isinstance(operations[0].action, AddTableConstraintAction)
        assert all(isinstance(node, BaseExpression) for node in operations)
        assert _sql(operations) == ["ALTER TABLE `events` ADD CONSTRAINT `ck` CHECK (`a` = `b`)"]

    def test_drop_from_a_frozen_projection_renders_if_exists(self, dialect):
        frozen_old = ("params", (("branch", ("repr", "CHECK")), ("name", "ck")))
        answer = dialect.suggest_table_constraint_change(
            TableConstraintChangeSuggestion(
                table_name="events", old_constraints=(frozen_old,), new_constraints=()
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 1
        assert isinstance(operations[0].action, DropTableConstraintAction)
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
        unique = TableConstraint(dialect, branch=TableUniqueConstraint(dialect, ["a"]), name="uq")
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
            TableConstraintChangeSuggestion(old_constraints=(), new_constraints=(_check(dialect),))
        )
        assert answer.operations is False

    def test_evidence_add_drop_exist_and_modify_does_not(self, dialect):
        assert dialect.supports_add_constraint() is True
        assert dialect.supports_drop_constraint() is True
        assert dialect.supports_alter_constraint() is False


# -- Table index change -----------------------------------------------------


def _index(dialect, name="idx", columns=None, type="minmax", granularity=4, **kwargs):
    index = ClickHouseIndexDefinition(
        dialect, name, columns if columns is not None else ["val"],
        type=type, granularity=granularity,
    )
    # The inline ClickHouse definition does not declare core's statement flags
    # in its own constructor; they arrive on the declaration from the model
    # layer, so set them the same way here.
    for flag, value in kwargs.items():
        setattr(index, flag, value)
    return index


def _frozen(name="idx", type="minmax", granularity=4):
    """A frozen index projection: the shape ``schema_change._freeze`` produces."""
    return (
        "params",
        (
            ("name", name),
            ("columns", ("val",)),
            ("type", type),
            ("granularity", granularity),
            ("unique", False),
        ),
    )


class TestTableIndexChange:
    def test_no_change_has_no_answer(self, dialect):
        unchanged = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events", old_indexes=(_frozen(),), new_indexes=(_frozen(),)
            )
        )
        assert unchanged.operations is None
        assert unchanged.state == "absent"

    def test_add_renders_a_real_chain(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events",
                old_indexes=(),
                new_indexes=(_frozen(),),
                new_index_declarations=(_index(dialect),),
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 1
        assert isinstance(operations[0], ClickHouseAddIndexStatement)
        assert all(isinstance(node, BaseExpression) for node in operations)
        assert _sql(operations) == [
            "ALTER TABLE `events` ADD INDEX `idx` `val` TYPE minmax GRANULARITY 4"
        ]
        assert answer.state == "actions"

    def test_drop_renders_if_exists(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events", old_indexes=(_frozen(),), new_indexes=()
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 1
        assert isinstance(operations[0], ClickHouseDropIndexStatement)
        assert _sql(operations) == ["ALTER TABLE `events` DROP INDEX IF EXISTS `idx`"]

    def test_changed_declaration_drops_then_adds(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events",
                old_indexes=(_frozen(type="minmax", granularity=1),),
                new_indexes=(_frozen(type="set", granularity=2),),
                old_index_declarations=(_index(dialect, type="minmax", granularity=1),),
                new_index_declarations=(_index(dialect, type="set", granularity=2),),
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 2
        assert _sql(operations) == [
            "ALTER TABLE `events` DROP INDEX IF EXISTS `idx`",
            "ALTER TABLE `events` ADD INDEX `idx` `val` TYPE set GRANULARITY 2",
        ]

    def test_declaration_if_not_exists_reaches_the_sql(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events",
                old_indexes=(),
                new_indexes=(_frozen(),),
                new_index_declarations=(_index(dialect, if_not_exists=True),),
            )
        )
        operations = answer.operations
        assert isinstance(operations, tuple)
        assert _sql(operations) == [
            "ALTER TABLE `events` ADD INDEX IF NOT EXISTS `idx` `val` "
            "TYPE minmax GRANULARITY 4"
        ]

    @pytest.mark.parametrize("declaration", ["frozen-only", "unique", "no-type"])
    def test_unexpressible_add_is_declined_without_a_partial_chain(
        self, dialect, declaration
    ):
        if declaration == "frozen-only":
            decls = ()  # a frozen projection carries no body to rebuild
        elif declaration == "unique":
            from rhosocial.activerecord.backend.expression.statements.ddl_table import (
                IndexDefinition,
            )

            decls = (IndexDefinition(dialect, "idx", ["val"], unique=True, type="minmax"),)
        else:
            decls = (_index(dialect, type=None),)
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events",
                old_indexes=(_frozen("old"),),
                new_indexes=(_frozen("idx"),),
                new_index_declarations=decls,
            )
        )
        assert answer.operations is False
        assert not isinstance(answer.operations, tuple)

    def test_multi_column_declaration_is_declined(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events",
                old_indexes=(),
                new_indexes=(_frozen(),),
                new_index_declarations=(_index(dialect, columns=["a", "b"]),),
            )
        )
        assert answer.operations is False

    def test_missing_table_is_declined(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                old_indexes=(),
                new_indexes=(_frozen(),),
                new_index_declarations=(_index(dialect),),
            )
        )
        assert answer.operations is False

    def test_unnamed_index_is_declined(self, dialect):
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events", old_indexes=("old",), new_indexes=("new",)
            )
        )
        assert answer.operations is False

    @pytest.mark.parametrize(
        "probe",
        [
            "supports_create_index",
            "supports_drop_index",
            "supports_index_if_not_exists",
        ],
    )
    def test_each_operation_is_gated_by_its_probe(self, dialect, monkeypatch, probe):
        point = TableIndexChangeSuggestion(
            table_name="events",
            old_indexes=(_frozen("old"),),
            new_indexes=(_frozen("idx"),),
            old_index_declarations=(_index(dialect, name="old"),),
            new_index_declarations=(_index(dialect, if_not_exists=True),),
        )
        assert isinstance(dialect.suggest_table_index_change(point).operations, tuple)
        monkeypatch.setattr(dialect, probe, lambda: False)
        assert dialect.suggest_table_index_change(point).operations is False

    def test_drop_degrades_to_plain_form_when_if_exists_is_absent(self, dialect, monkeypatch):
        monkeypatch.setattr(dialect, "supports_index_if_exists", lambda: False)
        answer = dialect.suggest_table_index_change(
            TableIndexChangeSuggestion(
                table_name="events", old_indexes=(_frozen(),), new_indexes=()
            )
        )
        assert _sql(answer.operations) == ["ALTER TABLE `events` DROP INDEX `idx`"]

    def test_no_returned_chain_destroys_or_moves_data(self, dialect):
        """The index chain touches metadata only: no table drop, no data move."""
        point = TableIndexChangeSuggestion(
            table_name="events",
            old_indexes=(_frozen("old"),),
            new_indexes=(_frozen("idx"),),
            old_index_declarations=(_index(dialect, name="old"),),
            new_index_declarations=(_index(dialect),),
        )
        operations = dialect.suggest_table_index_change(point).operations
        assert isinstance(operations, tuple) and operations
        for sql in _sql(operations):
            upper = sql.upper()
            assert not any(
                verb in upper
                for verb in (
                    "DROP TABLE", "DROP SCHEMA", "DROP DATABASE",
                    "REPLACE PARTITION", "MOVE PARTITION", "DELETE FROM", "INSERT INTO",
                )
            ), sql

    def test_evidence_skip_index_alter_has_its_own_nodes(self, dialect):
        """The probes are True, and the proprietary nodes render that spelling.

        Core's ``AddIndexAction`` still renders MySQL's form and stays gated
        off; the inline definition keeps its CREATE TABLE shape.
        """
        assert dialect.supports_index_if_not_exists() is True
        assert dialect.supports_index_if_exists() is True
        assert dialect.supports_alter_table_index_actions() is False
        index = ClickHouseIndexDefinition(dialect, "idx", ["a"], type="minmax", granularity=4)
        assert index.to_sql()[0] == "INDEX `idx` (`a`) TYPE minmax GRANULARITY 4"
        with pytest.raises(UnsupportedFeatureError, match="ALTER TABLE ADD INDEX"):
            AddIndexAction(dialect, index).to_sql()
        assert _index(dialect).to_sql()[0] == (
            "INDEX `idx` (`val`) TYPE minmax GRANULARITY 4"
        )


# -- Partition scheme change ------------------------------------------------


def _scheme(old, new, table="visits"):
    return PartitionSchemeChangeSuggestion(table_name=table, old_partition=old, new_partition=new)


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

    def test_data_preserving_chain_renders_exact_sql(self, dialect):
        point = _scheme(
            {"operations": [{"operation": "freeze", "backup_name": "before"}]},
            {
                "operations": [
                    {"operation": "detach", "partition_id": "202601"},
                    {"operation": "attach", "partition_id": "202601"},
                    {"operation": "unfreeze", "backup_name": "before"},
                    {"operation": "optimize"},
                ]
            },
        )
        answer = dialect.suggest_partition_scheme_change(point)
        operations = answer.operations
        assert isinstance(operations, tuple) and len(operations) == 5
        assert all(isinstance(node, BaseExpression) for node in operations)
        assert [type(node) for node in operations] == [
            ClickHouseFreezePartitionStatement,
            ClickHouseDetachPartitionStatement,
            ClickHouseAttachPartitionStatement,
            ClickHouseUnfreezePartitionStatement,
            ClickHouseOptimizePartitionStatement,
        ]
        assert _sql(operations) == [
            "ALTER TABLE `visits` FREEZE WITH NAME 'before'",
            "ALTER TABLE `visits` DETACH PARTITION ID '202601'",
            "ALTER TABLE `visits` ATTACH PARTITION ID '202601'",
            "ALTER TABLE `visits` UNFREEZE WITH NAME 'before'",
            "OPTIMIZE TABLE `visits` FINAL",
        ]

    @pytest.mark.parametrize(
        ("operation", "params"),
        [
            ("drop", {"partition_id": "202601"}),
            (
                "replace",
                {"partition_id": "202601", "source_table": "visits_stage"},
            ),
            (
                "move",
                {
                    "partition_id": "202601",
                    "destination": "TABLE",
                    "target": "visits_archive",
                },
            ),
            (
                "clear",
                {"kind": "INDEX", "name": "idx", "partition_id": "202601"},
            ),
        ],
    )
    def test_data_changing_operations_are_refused(self, dialect, operation, params):
        request = {"operation": operation, **params}
        answer = dialect.suggest_partition_scheme_change(_scheme(None, {"operations": [request]}))
        assert answer.operations is False
        assert not isinstance(answer.operations, tuple)
        # A safe plan cannot smuggle one of these through as a partial chain.
        answer = dialect.suggest_partition_scheme_change(
            _scheme(
                {"operations": [{"operation": "freeze", "backup_name": "before"}]},
                {"operations": [request, {"operation": "optimize"}]},
            )
        )
        assert answer.operations is False
        assert not isinstance(answer.operations, tuple)

    def test_unmatched_detach_is_refused(self, dialect):
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

    def test_attach_without_its_own_detach_is_refused(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            _scheme(None, {"operations": [{"operation": "attach", "partition_id": "202601"}]})
        )
        assert answer.operations is False

    def test_detach_and_attach_of_different_partitions_are_refused(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            _scheme(
                None,
                {
                    "operations": [
                        {"operation": "detach", "partition_id": "202601"},
                        {"operation": "attach", "partition_id": "202602"},
                    ]
                },
            )
        )
        assert answer.operations is False

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
                for verb in (
                    "REORGANIZE",
                    "EXCHANGE",
                    "COALESCE",
                    "REMOVE PARTITIONING",
                    "SUBPARTITION",
                )
            )

    def test_no_returned_chain_destroys_or_moves_data(self, dialect):
        """Structural invariant, not just a name guard: no emitted chain is destructive.

        Checked by node class and by rendered SQL. A DETACH is only acceptable
        when an ATTACH of that same partition id returns it to the table.
        """
        destructive_types = (
            ClickHouseDropPartitionStatement,
            ClickHouseReplacePartitionStatement,
            ClickHouseMovePartitionStatement,
            ClickHouseClearInPartitionStatement,
        )
        destructive_sql = (
            "DROP PARTITION",
            "REPLACE PARTITION",
            "MOVE PARTITION",
            "CLEAR COLUMN",
            "CLEAR INDEX",
        )
        freeze = {"operation": "freeze", "backup_name": "before"}
        detach = {"operation": "detach", "partition_id": "202601"}
        attach = {"operation": "attach", "partition_id": "202601"}
        plans = [
            None,  # bare declaration
            [{"operation": "drop", "partition_id": "202601"}],
            [{"operation": "replace", "partition_id": "202601", "source_table": "stage"}],
            [
                {
                    "operation": "move",
                    "partition_id": "202601",
                    "destination": "TABLE",
                    "target": "visits_archive",
                }
            ],
            [{"operation": "clear", "kind": "INDEX", "name": "idx", "partition_id": "202601"}],
            [detach],  # unmatched DETACH
            [detach, {"operation": "attach", "partition_id": "202602"}],
            [attach],  # ATTACH without a DETACH in this chain
            [
                freeze,
                detach,
                attach,
                {"operation": "unfreeze", "backup_name": "before"},
                {"operation": "optimize"},
            ],
            [freeze],
            [{"operation": "optimize"}],
        ]
        emitted = 0
        for plan in plans:
            if plan is None:
                point = _scheme({"key": "toYYYYMM(ts)"}, {"key": "toYYYY(year(ts))"})
            else:
                point = _scheme(None, {"operations": plan})
            operations = dialect.suggest_partition_scheme_change(point).operations
            if not isinstance(operations, tuple):
                continue
            emitted += 1
            detached = []
            for node, sql in zip(operations, _sql(operations), strict=True):
                assert not isinstance(node, destructive_types), type(node).__name__
                upper = sql.upper()
                assert not any(verb in upper for verb in destructive_sql), sql
                match = re.search(r"PARTITION ID '([^']+)'", sql)
                if isinstance(node, ClickHouseDetachPartitionStatement):
                    assert match is not None, sql
                    detached.append(match.group(1))
                elif isinstance(node, ClickHouseAttachPartitionStatement):
                    assert match is not None and match.group(1) in detached, (detached, sql)
                    detached.remove(match.group(1))
            assert not detached, f"chain left partitions detached: {detached}"
        assert emitted, "no data-preserving chain was emitted; safety assertion was vacuous"

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

    @pytest.mark.parametrize(
        "probe",
        [
            "supports_detach_partition",
            "supports_attach_partition",
            "supports_freeze_partition",
            "supports_unfreeze_partition",
            "supports_optimize_partition_final",
        ],
    )
    def test_each_safe_operation_is_gated_by_its_probe(self, dialect, monkeypatch, probe):
        point = _scheme(
            None,
            {
                "operations": [
                    {"operation": "freeze", "backup_name": "before"},
                    {"operation": "detach", "partition_id": "202601"},
                    {"operation": "attach", "partition_id": "202601"},
                    {"operation": "unfreeze", "backup_name": "before"},
                    {"operation": "optimize"},
                ]
            },
        )
        assert isinstance(dialect.suggest_partition_scheme_change(point).operations, tuple)
        monkeypatch.setattr(dialect, probe, lambda: False)
        answer = dialect.suggest_partition_scheme_change(point)
        assert answer.operations is False

    def test_missing_table_is_declined(self, dialect):
        answer = dialect.suggest_partition_scheme_change(
            PartitionSchemeChangeSuggestion(
                old_partition=None,
                new_partition={"operations": [{"operation": "optimize"}]},
            )
        )
        assert answer.operations is False
