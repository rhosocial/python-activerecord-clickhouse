# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_create_table_expression_diff.py
"""
CreateTableExpression.diff() coverage for the ClickHouse dialect.

The generic ``CreateTableExpressionDiffMixin`` lives in the core library and is
composed into ``SQLDialectBase``; ClickHouse overrides the capability hooks to
match the engine's DDL reality:

- ``_supports_alter_column_type()`` → True: ClickHouse supports in-place type
  changes via ``ALTER TABLE ... MODIFY COLUMN``, so type changes emit a
  ``ModifyColumn`` action (no rebuild).
- ``_supports_alter_column_properties()`` → False: ClickHouse has no
  ``ALTER COLUMN SET/DROP DEFAULT`` or ``SET/DROP NOT NULL``. DEFAULT is part
  of the column definition and nullability is part of the type
  (``Nullable(T)``); both require ``MODIFY COLUMN``, so property changes
  rebuild.
- ``_supports_alter_table_index_actions()`` → False: ClickHouse has no
  traditional secondary indexes — only data skipping indexes, which require
  ``TYPE ... GRANULARITY ...`` clauses the generic ``ADD INDEX`` action cannot
  express. Index changes rebuild; the recreated table renders skip indexes
  inline (``INDEX name (cols) TYPE minmax GRANULARITY 1``).
- ``_diff_table_constraints()`` override: any named/unnamed constraint change
  rebuilds, because ``ALTER TABLE ADD/DROP CONSTRAINT`` is unsupported and the
  generic drop/add actions would raise ``UnsupportedFeatureError`` on render.

These tests are pure expression-level (no live server needed) and pin:
- DiffPlan/RebuildPlan shapes for ClickHouse
- rendered ``to_sql()`` text for ALTER TABLE actions
- regressions for the pre-override behaviors (rebuild-forced type changes,
  invalid ``ALTER COLUMN SET DEFAULT``, type-less ``ADD INDEX``,
  unrenderable constraint actions)
"""

import pytest

from rhosocial.activerecord.backend.dialect.protocols import CreateTableExpressionDiffSupport
from rhosocial.activerecord.backend.expression import DiffPlan, RebuildPlan
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTableExpression,
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    AlterTableExpression,
    DropColumn,
    ModifyColumn,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import TableOptions
from rhosocial.activerecord.backend.expression.types import (
    IntegerType,
    TextType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.sqlite.dialect import SQLiteDialect


def _col(name, dtype, *constraints):
    return ColumnDefinition(name=name, data_type=dtype, constraints=list(constraints))


def _pk():
    return ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY)


def _not_null():
    return ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL)


def _expr(dialect, columns, indexes=None, constraints=None, **kwargs):
    return CreateTableExpression(
        dialect=dialect,
        table=kwargs.pop("table", "items"),
        columns=columns,
        indexes=indexes,
        table_constraints=constraints,
        **kwargs,
    )


@pytest.fixture
def dialect():
    return ClickHouseDialect((23, 8, 1))


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestProtocolConformance:

    def test_dialect_satisfies_diff_protocol(self, dialect):
        assert isinstance(dialect, CreateTableExpressionDiffSupport)

    def test_expression_diff_delegates_to_dialect(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType()), _col("b", TextType())])
        via_expression = old.diff(new)
        via_dialect = dialect.diff_create_table(old, new)
        assert via_expression.rebuild is None and via_dialect.rebuild is None
        assert [a.to_sql() for a in via_expression.alters] == [a.to_sql() for a in via_dialect.alters]
        assert [type(x) for x in via_expression.alters[0].actions] == \
            [type(x) for x in via_dialect.alters[0].actions]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:

    def test_cross_dialect_raises(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(SQLiteDialect(), [_col("id", IntegerType(), _pk())])
        with pytest.raises(ValueError, match="different dialects"):
            old.diff(new)

    def test_cross_table_raises(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk())], table="other")
        with pytest.raises(ValueError, match="different tables"):
            old.diff(new)


# ---------------------------------------------------------------------------
# No change
# ---------------------------------------------------------------------------

class TestNoChange:

    def test_identical_definitions_empty_plan(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("name", TextType())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("name", TextType())])
        plan = old.diff(new)
        assert not plan.has_changes
        assert plan.rebuild is None
        assert plan.alters == []


# ---------------------------------------------------------------------------
# Column add / drop
# ---------------------------------------------------------------------------

class TestColumnChanges:

    def test_added_column_yields_add_action(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("bio", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.has_changes
        (alter,) = plan.alters
        assert len(alter.actions) == 1
        action = alter.actions[0]
        assert isinstance(action, AddColumn)
        assert action.column.name == "bio"

    def test_added_column_renders_clickhouse_sql(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("bio", TextType())])
        sql, _ = old.diff(new).alters[0].to_sql()
        assert "ADD COLUMN" in sql
        assert "`bio`" in sql
        assert "String" in sql

    def test_removed_column_yields_drop_action(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("bio", TextType())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk())])
        plan = old.diff(new)
        assert plan.rebuild is None
        (alter,) = plan.alters
        action = alter.actions[0]
        assert isinstance(action, DropColumn)
        assert action.column_name == "bio"
        sql, _ = alter.to_sql()
        assert "DROP COLUMN" in sql
        assert "`bio`" in sql


# ---------------------------------------------------------------------------
# Column property changes (default / nullability) → rebuild
# ---------------------------------------------------------------------------

class TestColumnPropertyChanges:

    def test_hook_reports_no_property_support(self, dialect):
        assert dialect._supports_alter_column_properties() is False

    def test_set_default_rebuilds(self, dialect):
        old = _expr(dialect, [_col("status", TextType())])
        new = _expr(dialect, [_col(
            "status", TextType(),
            ColumnConstraint(constraint_type=ColumnConstraintType.DEFAULT, default_value="ok"),
        )])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None
        assert "property change" in plan.rebuild.reason

    def test_drop_default_rebuilds(self, dialect):
        old = _expr(dialect, [_col(
            "status", TextType(),
            ColumnConstraint(constraint_type=ColumnConstraintType.DEFAULT, default_value="ok"),
        )])
        new = _expr(dialect, [_col("status", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "property change" in plan.rebuild.reason

    def test_set_not_null_rebuilds(self, dialect):
        # Nullability is part of the ClickHouse type (Nullable(T)): switching
        # between Nullable and non-Nullable is a MODIFY COLUMN type rewrite,
        # not ALTER COLUMN SET NOT NULL.
        old = _expr(dialect, [_col("name", TextType())])
        new = _expr(dialect, [_col("name", TextType(), _not_null())])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "property change" in plan.rebuild.reason

    def test_drop_not_null_rebuilds(self, dialect):
        old = _expr(dialect, [_col("name", TextType(), _not_null())])
        new = _expr(dialect, [_col("name", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "property change" in plan.rebuild.reason


# ---------------------------------------------------------------------------
# Column type change → MODIFY COLUMN (ClickHouse override; no rebuild)
#
# The class name follows the cross-backend test taxonomy. On ClickHouse a
# type change is expressible in place (MODIFY COLUMN), so these tests pin the
# in-place path; the rebuild variant is unreachable for pure type changes and
# is covered by TestTableConstraintChanges / TestStructuralChanges instead.
# ---------------------------------------------------------------------------

class TestTypeChangeRebuild:

    def test_hook_reports_type_change_support(self, dialect):
        assert dialect._supports_alter_column_type() is True

    def test_alter_column_type_action_returns_modify_column(self, dialect):
        old_col = _col("code", IntegerType())
        new_col = _col("code", VarCharType(length=100))
        action = dialect.alter_column_type_action(old_col, new_col)
        assert isinstance(action, ModifyColumn)
        assert action.column is new_col

    def test_type_change_yields_modify_column(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", VarCharType(length=100))])
        plan = old.diff(new)
        assert plan.rebuild is None
        (alter,) = plan.alters
        action = alter.actions[0]
        assert isinstance(action, ModifyColumn)
        assert action.column.name == "code"

    def test_type_change_renders_modify_column_sql(self, dialect):
        old = _expr(dialect, [_col("code", IntegerType())])
        new = _expr(dialect, [_col("code", VarCharType(length=100))])
        plan = old.diff(new)
        sql, _ = plan.alters[0].to_sql()
        assert "MODIFY COLUMN" in sql
        assert "`code`" in sql
        assert "String" in sql

    def test_varchar_length_change_is_in_place(self, dialect):
        # ClickHouse renders VarCharType as String, but the expression-level
        # data types still differ structurally, so the diff must report it.
        old = _expr(dialect, [_col("name", VarCharType(length=50))])
        new = _expr(dialect, [_col("name", VarCharType(length=100))])
        plan = old.diff(new)
        assert plan.rebuild is None
        assert isinstance(plan.alters[0].actions[0], ModifyColumn)


# ---------------------------------------------------------------------------
# Index changes → rebuild (no traditional indexes on ClickHouse)
# ---------------------------------------------------------------------------

class TestIndexChanges:

    def test_hook_reports_no_index_actions(self, dialect):
        assert dialect._supports_alter_table_index_actions() is False

    def test_added_index_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())],
                    indexes=[IndexDefinition(name="idx_code", columns=["code"])])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None
        assert "index change" in plan.rebuild.reason

    def test_removed_index_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())],
                    indexes=[IndexDefinition(name="idx_code", columns=["code"])])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "index change" in plan.rebuild.reason

    def test_rebuilt_table_renders_skip_index_inline(self, dialect):
        # The rebuild CREATE TABLE must carry the skip index with the mandatory
        # TYPE/GRANULARITY clauses (rendered by format_inline_index).
        old = _expr(dialect, [_col("code", IntegerType())])
        new = _expr(dialect, [_col("code", IntegerType())],
                    indexes=[IndexDefinition(name="idx_code", columns=["code"])])
        rp = old.diff(new).rebuild
        sql, _ = rp.create.to_sql()
        assert "CREATE TABLE" in sql.upper()
        assert "`items__rebuild__`" in sql
        assert "INDEX" in sql
        assert "TYPE minmax GRANULARITY 1" in sql


# ---------------------------------------------------------------------------
# Table constraint changes → rebuild (no ADD/DROP CONSTRAINT on ClickHouse)
# ---------------------------------------------------------------------------

class TestTableConstraintChanges:

    def test_pk_change_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType()), _col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(dialect, [_col("id", IntegerType()), _col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        plan = old.diff(new)
        assert plan.alters == []
        rp = plan.rebuild
        assert isinstance(rp, RebuildPlan)
        assert "primary key" in rp.reason

    def test_named_constraint_add_rebuilds(self, dialect):
        # ALTER TABLE ADD CONSTRAINT is unsupported: the generic Add action
        # would raise UnsupportedFeatureError on render, so rebuild instead.
        old = _expr(dialect, [_col("id", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.UNIQUE, name="uq_id", columns=["id"])])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "constraint" in plan.rebuild.reason

    def test_named_constraint_drop_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.UNIQUE, name="uq_id", columns=["id"])])
        new = _expr(dialect, [_col("id", IntegerType())])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "constraint" in plan.rebuild.reason

    def test_unnamed_constraint_change_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.UNIQUE, columns=["id"])])
        new = _expr(dialect, [_col("id", IntegerType())])
        plan = old.diff(new)
        assert plan.rebuild is not None

    def test_rebuild_plan_shape(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(dialect, [_col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        rp = old.diff(new).rebuild
        assert rp.create.table_name == "items__rebuild__"
        assert rp.drop_old.table.name == "items"
        assert rp.rename.table == "items__rebuild__"
        assert rp.copy_columns == []

    def test_rebuild_plan_renders_sql(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(dialect, [_col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        rp = old.diff(new).rebuild
        create_sql, _ = rp.create.to_sql()
        drop_sql, _ = rp.drop_old.to_sql()
        rename_sql, _ = rp.rename.to_sql()
        assert "CREATE TABLE" in create_sql.upper()
        assert "DROP TABLE" in drop_sql.upper()
        assert "RENAME" in rename_sql.upper()


# ---------------------------------------------------------------------------
# Structural fields → rebuild
# ---------------------------------------------------------------------------

class TestStructuralChanges:

    def test_temporary_flag_change_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType())], temporary=True)
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "structural" in plan.rebuild.reason

    def test_storage_options_change_rebuilds(self, dialect):
        # ENGINE / ORDER BY / PARTITION BY live in storage_options; a change
        # there is structural (ClickHouse cannot ALTER an ENGINE in place).
        old = _expr(dialect, [_col("id", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType())],
                    storage_options={"ENGINE": "MergeTree()"})
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "structural" in plan.rebuild.reason

    def test_partition_clause_change_rebuilds(self, dialect):
        from rhosocial.activerecord.backend.expression.core import Column
        from rhosocial.activerecord.backend.expression.statements import PartitionClause
        from rhosocial.activerecord.backend.expression.statements.ddl_partition import PartitionStrategy

        old = _expr(dialect, [_col("id", IntegerType())])
        partition = PartitionClause(
            dialect, PartitionStrategy.HASH, [Column(dialect, "ts")]
        )
        new = _expr(dialect, [_col("id", IntegerType())], partition=partition)
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "structural" in plan.rebuild.reason

    def test_table_options_change_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType())], table_options=TableOptions(comment="x"))
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "structural" in plan.rebuild.reason

    def test_rebuild_preserves_storage_options(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType())],
                    storage_options={"ENGINE": "MergeTree()", "ORDER BY": "id"})
        rp = old.diff(new).rebuild
        sql, _ = rp.create.to_sql()
        assert "ENGINE = MergeTree()" in sql
        assert "ORDER BY = id" in sql or "ORDER BY id" in sql


# ---------------------------------------------------------------------------
# DiffPlan invariants
# ---------------------------------------------------------------------------

class TestDiffPlanInvariants:

    def test_alters_and_rebuild_mutually_exclusive(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("x", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.alters
        old2 = _expr(dialect, [_col("id", IntegerType())],
                     constraints=[TableConstraint(
                         constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new2 = _expr(dialect, [_col("code", TextType())],
                     constraints=[TableConstraint(
                         constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        plan2 = old2.diff(new2)
        assert plan2.rebuild is not None and plan2.alters == []

    def test_plan_rejects_both_fields(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(dialect, [_col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        rp = old.diff(new).rebuild
        assert rp is not None
        alter = AlterTableExpression(dialect, table="t", actions=[])
        with pytest.raises(ValueError, match="mutually exclusive"):
            DiffPlan(alters=[alter], rebuild=rp)

    def test_rebuild_plan_copy_columns_lists_survivors(self, dialect):
        # Column rename is not detected (rendered as drop + add) by the
        # generic mixin; survivors keep data via copy_columns.
        old = _expr(dialect, [_col("id", IntegerType()), _col("name", TextType())])
        new = _expr(dialect, [_col("id", IntegerType()), _col("name", TextType()),
                              _col("extra", TextType())],
                    constraints=None)
        # Force a rebuild path via a PK table-constraint change.
        old = _expr(dialect, [_col("id", IntegerType()), _col("name", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(dialect, [_col("id", IntegerType()), _col("name", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["name"])])
        rp = old.diff(new).rebuild
        assert rp.copy_columns == ["id", "name"]

    def test_ordered_statements_are_structural_steps(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(dialect, [_col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        rp = old.diff(new).rebuild
        assert rp.ordered_statements() == [rp.create, rp.drop_old, rp.rename]


# ---------------------------------------------------------------------------
# Defect regressions (pre-override ClickHouse behaviors)
# ---------------------------------------------------------------------------

class TestDefectRegressions:

    def test_type_change_no_longer_forces_rebuild(self, dialect):
        # Before the override, ClickHouseDialect inherited the strict default
        # _supports_alter_column_type() == False even though the public
        # capability supports_alter_column_type() reported True, so a type
        # change wrongly rebuilt the table.
        assert dialect._supports_alter_column_type() is True
        assert dialect.supports_alter_column_type() is True
        old = _expr(dialect, [_col("code", IntegerType())])
        new = _expr(dialect, [_col("code", VarCharType(length=100))])
        plan = old.diff(new)
        assert plan.rebuild is None
        assert isinstance(plan.alters[0].actions[0], ModifyColumn)

    def test_property_change_no_longer_emits_invalid_alter_column(self, dialect):
        # Before the override, a SET DEFAULT diff emitted
        # ``ALTER TABLE t ALTER COLUMN c SET DEFAULT 'x'`` — ClickHouse has no
        # ALTER COLUMN SET DEFAULT (DEFAULT belongs to the column definition,
        # changed via MODIFY COLUMN). It must rebuild instead.
        old = _expr(dialect, [_col("status", TextType())])
        new = _expr(dialect, [_col(
            "status", TextType(),
            ColumnConstraint(constraint_type=ColumnConstraintType.DEFAULT, default_value="ok"),
        )])
        plan = old.diff(new)
        assert plan.alters == [] and plan.rebuild is not None
        for alter in plan.alters:
            sql, _ = alter.to_sql()
            assert "ALTER COLUMN" not in sql

    def test_index_change_no_longer_emits_typeless_add_index(self, dialect):
        # Before the override, an index diff emitted
        # ``ALTER TABLE t ADD INDEX `idx` (`code`)`` — invalid ClickHouse SQL:
        # skip indexes require TYPE ... GRANULARITY ..., and ClickHouse has no
        # traditional indexes at all. It must rebuild instead.
        old = _expr(dialect, [_col("code", IntegerType())])
        new = _expr(dialect, [_col("code", IntegerType())],
                    indexes=[IndexDefinition(name="idx_code", columns=["code"])])
        plan = old.diff(new)
        assert plan.alters == [] and plan.rebuild is not None
        sql, _ = plan.rebuild.create.to_sql()
        assert "ADD INDEX" not in sql
        assert "TYPE minmax GRANULARITY 1" in sql

    def test_constraint_change_no_longer_emits_unrenderable_actions(self, dialect):
        # Before the override, a named constraint drop produced a
        # DropTableConstraint action whose to_sql() raises
        # UnsupportedFeatureError on ClickHouse (no ADD/DROP CONSTRAINT).
        # The plan must be executable: rebuild instead.
        old = _expr(dialect, [_col("id", IntegerType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.UNIQUE, name="uq_id", columns=["id"])])
        new = _expr(dialect, [_col("id", IntegerType())])
        plan = old.diff(new)
        assert plan.alters == [] and plan.rebuild is not None
        # Every structural statement renders without UnsupportedFeatureError.
        for stmt in plan.rebuild.ordered_statements():
            stmt.to_sql()
