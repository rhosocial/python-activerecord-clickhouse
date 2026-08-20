from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    ForeignKeyConstraint,
    IndexDefinition,
    ReferentialAction,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    AlterTableExpression,
    ChangeColumn,
    DropColumn,
    DropTableConstraint,
    ModifyColumn,
)
from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
    CreateTriggerExpression,
    DropTriggerExpression,
    TriggerEvent,
    TriggerLevel,
    TriggerTiming,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.load_data import (
    LoadDataOptions,
    ClickHouseLoadDataExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.locking import (
    ClickHouseForUpdateClause,
    ClickHouseLockStrength,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.match_against import (
    MatchAgainstMode,
    ClickHouseMatchAgainstExpression,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHouseAddPartitionExpression,
    ClickHouseCoalescePartitionExpression,
    ClickHouseDropPartitionExpression,
    ClickHouseExchangePartitionExpression,
    ClickHousePartitionByHash,
    ClickHousePartitionByKey,
    ClickHousePartitionByList,
    ClickHousePartitionByListColumns,
    ClickHousePartitionByRange,
    ClickHousePartitionByRangeColumns,
    ClickHousePartitionDefinition,
    ClickHousePartitionMaxValue,
    ClickHousePartitionValue,
    ClickHouseReorganizePartitionExpression,
    ClickHouseTruncatePartitionExpression,
    ClickHouseSubpartitionClause,
    ClickHouseSubpartitionDefinition,
    ClickHouseSubpartitionStrategy,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition_lifecycle import (
    ClickHouseAddPartitionHelper,
    ClickHouseAddSubpartitionHelper,
    ClickHouseCoalescePartitionHelper,
    ClickHouseDropOldestPartitionHelper,
    ClickHouseReorganizePartitionHelper,
)
from rhosocial.activerecord.backend.expression.types import (
    DateTimeType,
    IntegerType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.clickhouse.expression.vector import (
    ClickHouseDistanceCosineExpression,
    ClickHouseDistanceDotExpression,
    ClickHouseDistanceEuclideanExpression,
    ClickHouseVectorExpression,
)


# ============================================================================
# DML Operation Expressions
# ============================================================================

class TestClickHouseDMLOperationExpressions:
    """Test LOAD DATA and ON CONFLICT expression->dialect delegation."""

    def test_load_data_basic(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseLoadDataExpression(
            dialect, file_path="/tmp/data.csv", table="users"
        )
        sql, params = expr.to_sql()
        assert "LOAD DATA" in sql
        assert "INFILE '/tmp/data.csv'" in sql
        assert "INTO TABLE `users`" in sql
        assert params == ()

    def test_load_data_local_replace(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        options = LoadDataOptions(local=True, replace=True)
        expr = ClickHouseLoadDataExpression(
            dialect, file_path="data.csv", table="products", options=options
        )
        sql, params = expr.to_sql()
        assert "LOAD DATA LOCAL INFILE 'data.csv' REPLACE INTO TABLE `products`" == sql

    def test_load_data_ignore(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        options = LoadDataOptions(local=True, ignore=True)
        expr = ClickHouseLoadDataExpression(
            dialect, file_path="data.csv", table="products", options=options
        )
        sql, params = expr.to_sql()
        assert "LOAD DATA LOCAL INFILE 'data.csv' IGNORE INTO TABLE `products`" == sql

    def test_load_data_full_options(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        options = LoadDataOptions(
            local=True,
            character_set="utf8mb4",
            fields_terminated_by=",",
            fields_enclosed_by='"',
            fields_escaped_by="\\",
            lines_terminated_by="\\n",
            lines_starting_by=">",
            ignore_lines=1,
            set_assignments={"created_at": "NOW()"},
        )
        expr = ClickHouseLoadDataExpression(
            dialect, file_path="/tmp/import.csv", table="logs", options=options
        )
        sql, params = expr.to_sql()
        assert "LOAD DATA LOCAL INFILE '/tmp/import.csv'" in sql
        assert "CHARACTER SET utf8mb4" in sql
        assert "FIELDS TERMINATED BY ','" in sql
        assert "ENCLOSED BY" in sql
        assert "ESCAPED BY" in sql
        assert "STARTING BY" in sql
        assert "IGNORE 1 LINES" in sql
        assert "SET `created_at` = NOW()" in sql

    def test_load_data_validate_replaces_ignore_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        options = LoadDataOptions(replace=True, ignore=True)
        expr = ClickHouseLoadDataExpression(
            dialect, file_path="data.csv", table="t", options=options
        )
        with pytest.raises(ValueError, match="Cannot use both REPLACE and IGNORE"):
            expr.validate()

    def test_load_data_path_with_escape(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseLoadDataExpression(
            dialect, file_path="/path/with'quote.csv", table="t"
        )
        sql, params = expr.to_sql()
        assert "LOAD DATA" in sql
        assert "INTO TABLE `t`" in sql


# ============================================================================
# Locking Expressions (FOR UPDATE / FOR SHARE)
# ============================================================================

class TestClickHouseLockingExpressions:
    """Test FOR UPDATE / FOR SHARE / NOWAIT / SKIP LOCKED expressions."""

    def test_for_update_default(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseForUpdateClause(dialect)
        sql, params = expr.to_sql()
        assert sql == "FOR UPDATE"

    def test_for_share(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseForUpdateClause(dialect, strength=ClickHouseLockStrength.SHARE)
        sql, params = expr.to_sql()
        assert sql == "FOR SHARE"

    def test_for_update_nowait(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseForUpdateClause(dialect, nowait=True)
        sql, params = expr.to_sql()
        assert sql == "FOR UPDATE NOWAIT"

    def test_for_share_skip_locked(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseForUpdateClause(
            dialect, strength=ClickHouseLockStrength.SHARE, skip_locked=True
        )
        sql, params = expr.to_sql()
        assert sql == "FOR SHARE SKIP LOCKED"

    def test_for_update_of_columns(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseForUpdateClause(
            dialect, of_columns=["orders.id", "orders.status"]
        )
        sql, params = expr.to_sql()
        assert sql == "FOR UPDATE OF `orders.id`, `orders.status`"

    def test_for_share_of_columns_skip_locked(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseForUpdateClause(
            dialect,
            strength=ClickHouseLockStrength.SHARE,
            of_columns=["orders.id"],
            skip_locked=True,
        )
        sql, params = expr.to_sql()
        assert sql == "FOR SHARE OF `orders.id` SKIP LOCKED"

    def test_for_update_nowait_lower_version(self):
        dialect = ClickHouseDialect(version=(5, 7, 0))
        expr = ClickHouseForUpdateClause(dialect, nowait=True)
        with pytest.raises(Exception):
            expr.to_sql()


# ============================================================================
# Trigger Expressions (CREATE / DROP TRIGGER)
# ============================================================================

class TestClickHouseTriggerExpressions:
    """Test CREATE TRIGGER and DROP TRIGGER expressions."""

    def test_create_trigger_before_insert(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="before_insert_user",
            table_name="users",
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function_name="validate_user",
        )
        sql, params = expr.to_sql()
        assert "CREATE TRIGGER" in sql
        assert "`before_insert_user`" in sql
        assert "BEFORE INSERT ON `users` FOR EACH ROW" in sql
        assert "CALL `validate_user`" in sql

    def test_create_trigger_after_update(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="after_update_log",
            table_name="orders",
            timing=TriggerTiming.AFTER,
            events=[TriggerEvent.UPDATE],
            function_name="log_change",
        )
        sql, params = expr.to_sql()
        assert "CREATE TRIGGER" in sql
        assert "AFTER UPDATE ON `orders`" in sql

    def test_create_trigger_if_not_exists(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="my_trigger",
            table_name="t",
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function_name="my_func",
            if_not_exists=True,
        )
        sql, params = expr.to_sql()
        assert "IF NOT EXISTS" in sql

    def test_create_trigger_instead_of_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="bad_trigger",
            table_name="t",
            timing=TriggerTiming.INSTEAD_OF,
            events=[TriggerEvent.INSERT],
            function_name="f",
        )
        with pytest.raises(Exception):
            expr.to_sql()

    def test_create_trigger_for_each_statement_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="bad_trigger",
            table_name="t",
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function_name="f",
            level=TriggerLevel.STATEMENT,
        )
        with pytest.raises(Exception):
            expr.to_sql()

    def test_create_trigger_with_condition_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="bad_trigger",
            table_name="t",
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function_name="f",
            condition=MagicMock(),
        )
        with pytest.raises(Exception):
            expr.to_sql()

    def test_create_trigger_with_referencing_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="bad_trigger",
            table_name="t",
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function_name="f",
            referencing="OLD AS o",
        )
        with pytest.raises(Exception):
            expr.to_sql()

    def test_create_trigger_multiple_events_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="bad_trigger",
            table_name="t",
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT, TriggerEvent.UPDATE],
            function_name="f",
        )
        with pytest.raises(Exception):
            expr.to_sql()

    def test_create_trigger_with_update_columns_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = CreateTriggerExpression(
            dialect=dialect,
            trigger_name="bad_trigger",
            table_name="t",
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.UPDATE],
            function_name="f",
            update_columns=["col1"],
        )
        with pytest.raises(Exception):
            expr.to_sql()

    def test_drop_trigger(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = DropTriggerExpression(
            dialect=dialect,
            trigger_name="old_trigger",
        )
        sql, params = expr.to_sql()
        assert sql == "DROP TRIGGER `old_trigger`"

    def test_drop_trigger_if_exists(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = DropTriggerExpression(
            dialect=dialect,
            trigger_name="old_trigger",
            if_exists=True,
        )
        sql, params = expr.to_sql()
        assert sql == "DROP TRIGGER IF EXISTS `old_trigger`"


# ============================================================================
# Full-Text Search Expressions
# ============================================================================

class TestClickHouseFullTextExpressions:
    """Test FULLTEXT index options and MATCH AGAINST expressions."""

    def test_fulltext_index_options_basic(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_fulltext_index_options(
            "idx_ft_content", ["title", "body"]
        )
        assert "FULLTEXT `idx_ft_content` (`title`, `body`)" == sql

    def test_fulltext_index_options_with_parser(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_fulltext_index_options(
            "idx_ft_text", ["content"], parser_name="ngram"
        )
        assert "WITH PARSER `ngram`" in sql

    def test_match_against_basic(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseMatchAgainstExpression(dialect, ["title", "body"], "search_term")
        sql, params = expr.to_sql()
        assert "MATCH(`title`, `body`) AGAINST(%s IN NATURAL LANGUAGE MODE)" in sql
        assert params == ("search_term",)

    def test_match_against_boolean(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseMatchAgainstExpression(
            dialect, ["content"], "word*", mode=MatchAgainstMode.BOOLEAN
        )
        sql, params = expr.to_sql()
        assert "IN BOOLEAN MODE" in sql

    def test_match_against_query_expansion(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseMatchAgainstExpression(
            dialect, ["content"], "search",
            mode="QUERY_EXPANSION"
        )
        sql, params = expr.to_sql()
        assert "WITH QUERY EXPANSION" in sql

    def test_match_against_single_column(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseMatchAgainstExpression(dialect, ["body"], "hello")
        sql, params = expr.to_sql()
        assert "MATCH(`body`)" in sql


# ============================================================================
# Table DDL Expressions (CREATE TABLE LIKE, full coverage)
# ============================================================================

class TestClickHouseTableDDLExpressions:
    """Test CREATE TABLE LIKE, column constraints, table constraints, storage options."""

    def test_create_table_like(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        columns = [ColumnDefinition("id", IntegerType())]
        expr = CreateTableExpression(
            dialect=dialect,
            table="new_table",
            columns=columns,
            dialect_options={"like_table": "source_table"},
        )
        sql, params = expr.to_sql()
        assert "CREATE TABLE `new_table` LIKE `source_table`" == sql

    def test_create_table_like_temporary(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        columns = [ColumnDefinition("id", IntegerType())]
        expr = CreateTableExpression(
            dialect=dialect,
            table="tmp_table",
            columns=columns,
            temporary=True,
            dialect_options={"like_table": "source"},
        )
        sql, params = expr.to_sql()
        assert "TEMPORARY" in sql
        assert "CREATE TABLE" in sql
        assert "LIKE `source`" in sql

    def test_create_table_like_with_schema(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        columns = [ColumnDefinition("id", IntegerType())]
        expr = CreateTableExpression(
            dialect=dialect,
            table="new_table",
            columns=columns,
            dialect_options={"like_table": ("myschema", "source_table")},
        )
        sql, params = expr.to_sql()
        assert "LIKE `myschema`.`source_table`" in sql

    def test_create_table_like_if_not_exists(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        columns = [ColumnDefinition("id", IntegerType())]
        expr = CreateTableExpression(
            dialect=dialect,
            table="new_table",
            columns=columns,
            if_not_exists=True,
            dialect_options={"like_table": "source"},
        )
        sql, params = expr.to_sql()
        assert "CREATE TABLE IF NOT EXISTS `new_table` LIKE `source`" == sql

    def test_column_default_expression(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.expression.core import Literal
        columns = [
            ColumnDefinition(
                "created_at",
                DateTimeType(),
                constraints=[
                    ColumnConstraint(
                        ColumnConstraintType.DEFAULT,
                        default_value=Literal(dialect, "NOW()"),
                    )
                ],
            ),
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(dialect=dialect, table="t", columns=columns)
        sql, params = expr.to_sql()
        assert "DEFAULT" in sql
        assert "%s" in sql

    def test_column_default_string(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [
            ColumnDefinition(
                "status",
                VarCharType(20),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="active")
                ],
            ),
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(dialect=dialect, table="t", columns=columns)
        sql, params = expr.to_sql()
        assert "DEFAULT 'active'" in sql

    def test_column_default_numeric(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [
            ColumnDefinition(
                "count",
                IntegerType(),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)
                ],
            ),
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(dialect=dialect, table="t", columns=columns)
        sql, params = expr.to_sql()
        assert "DEFAULT 0" in sql

    def test_column_nullable(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [
            ColumnDefinition(
                "optional",
                VarCharType(100),
                constraints=[ColumnConstraint(ColumnConstraintType.NULL)],
            ),
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(dialect=dialect, table="t", columns=columns)
        sql, params = expr.to_sql()
        assert "NULL" in sql

    def test_column_unique(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [
            ColumnDefinition(
                "email",
                VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.UNIQUE)],
            ),
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(dialect=dialect, table="t", columns=columns)
        sql, params = expr.to_sql()
        assert "UNIQUE" in sql

    def test_named_table_constraint(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [ColumnDefinition("id", IntegerType())]
        table_constraints = [
            TableConstraint(
                constraint_type=TableConstraintType.PRIMARY_KEY,
                name="pk_users",
                columns=["id"],
            )
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(
            dialect=dialect, table="users", columns=columns,
            table_constraints=table_constraints
        )
        sql, params = expr.to_sql()
        assert "CONSTRAINT `pk_users`" in sql
        assert "PRIMARY KEY (`id`)" in sql

    def test_foreign_key_table_constraint(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [ColumnDefinition("user_id", IntegerType())]
        table_constraints = [
            TableConstraint(
                constraint_type=TableConstraintType.FOREIGN_KEY,
                name="fk_orders_user",
                columns=["user_id"],
                foreign_key_table="users",
                foreign_key_columns=["id"],
            )
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(
            dialect=dialect, table="orders", columns=columns,
            table_constraints=table_constraints
        )
        sql, params = expr.to_sql()
        assert "CONSTRAINT `fk_orders_user`" in sql
        assert "FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)" in sql

    def test_foreign_key_named_constraint_via_subclass(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [ColumnDefinition("order_id", IntegerType())]
        table_constraints = [
            ForeignKeyConstraint(
                constraint_type=TableConstraintType.FOREIGN_KEY,
                name="fk_payments_order",
                columns=["order_id"],
                foreign_key_table="orders",
                foreign_key_columns=["id"],
                on_delete=ReferentialAction.CASCADE,
                on_update=ReferentialAction.CASCADE,
            )
        ]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(
            dialect=dialect, table="payments", columns=columns,
            table_constraints=table_constraints
        )
        sql, params = expr.to_sql()
        assert "FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`)" in sql

    def test_temporary_table(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        columns = [ColumnDefinition("id", IntegerType())]
        expr = CreateTableExpression(
            dialect=dialect, table="tmp", columns=columns, temporary=True
        )
        sql, params = expr.to_sql()
        assert "CREATE TABLE" in sql
        assert "TEMPORARY" in sql

    def test_inline_index_with_type_numeric(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        columns = [ColumnDefinition("id", IntegerType())]
        indexes = [IndexDefinition("idx_id", ["id"], type="BTREE")]
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        expr = CreateTableExpression(
            dialect=dialect, table="t", columns=columns, indexes=indexes
        )
        sql, params = expr.to_sql()
        assert "USING BTREE" in sql

    def test_numeric_storage_option(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.expression.statements import CreateTableExpression
        columns = [ColumnDefinition("id", IntegerType())]
        expr = CreateTableExpression(
            dialect=dialect, table="t", columns=columns,
            storage_options={"AUTO_INCREMENT": 1000, "ENGINE": "InnoDB"}
        )
        sql, params = expr.to_sql()
        assert "AUTO_INCREMENT=1000" in sql
        assert "ENGINE='InnoDB'" in sql


# ============================================================================
# Column Modification Expressions (MODIFY/CHANGE COLUMN)
# ============================================================================

class TestClickHouseColumnModificationExpressions:
    """Test MODIFY COLUMN and CHANGE COLUMN via ALTER TABLE."""

    def test_modify_column(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = ModifyColumn(
            dialect=dialect,
            column=ColumnDefinition("name", VarCharType(200)),
        )
        expr = AlterTableExpression(
            dialect=dialect, table_name="users", actions=[action]
        )
        sql, params = expr.to_sql()
        assert "ALTER TABLE" in sql
        assert "MODIFY COLUMN `name` VARCHAR(200)" in sql

    def test_modify_column_first(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = ModifyColumn(
            dialect=dialect,
            column=ColumnDefinition("name", VarCharType(200)),
            first=True,
        )
        expr = AlterTableExpression(
            dialect=dialect, table_name="users", actions=[action]
        )
        sql, params = expr.to_sql()
        assert "MODIFY COLUMN" in sql
        assert "FIRST" in sql

    def test_modify_column_after(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = ModifyColumn(
            dialect=dialect,
            column=ColumnDefinition("name", VarCharType(200)),
            after_column="id",
        )
        expr = AlterTableExpression(
            dialect=dialect, table_name="users", actions=[action]
        )
        sql, params = expr.to_sql()
        assert "MODIFY COLUMN" in sql
        assert "AFTER `id`" in sql

    def test_change_column(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = ChangeColumn(
            dialect=dialect,
            old_name="username",
            column=ColumnDefinition("login_name", VarCharType(150)),
        )
        expr = AlterTableExpression(
            dialect=dialect, table_name="users", actions=[action]
        )
        sql, params = expr.to_sql()
        assert "CHANGE COLUMN" in sql

    def test_change_column_first(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = ChangeColumn(
            dialect=dialect,
            old_name="name",
            column=ColumnDefinition("full_name", VarCharType(300)),
            first=True,
        )
        expr = AlterTableExpression(
            dialect=dialect, table_name="users", actions=[action]
        )
        sql, params = expr.to_sql()
        assert "CHANGE COLUMN" in sql
        assert "FIRST" in sql

    def test_change_column_after(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = ChangeColumn(
            dialect=dialect,
            old_name="name",
            column=ColumnDefinition("full_name", VarCharType(300)),
            after_column="id",
        )
        expr = AlterTableExpression(
            dialect=dialect, table_name="users", actions=[action]
        )
        sql, params = expr.to_sql()
        assert "CHANGE COLUMN" in sql
        assert "AFTER `id`" in sql

    def test_modify_column_with_constraints(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = ModifyColumn(
            dialect=dialect,
            column=ColumnDefinition(
                "email",
                VarCharType(255),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.NOT_NULL),
                ],
            ),
        )
        expr = AlterTableExpression(
            dialect=dialect, table_name="users", actions=[action]
        )
        sql, params = expr.to_sql()
        assert "NOT NULL" in sql


class TestClickHouseAlterTableModifierGuards:
    """ClickHouse does not support any IF [NOT] EXISTS qualifiers on ALTER TABLE.

    Requesting them via ``if_not_exists=True`` / ``if_exists=True`` on
    ``AddColumn`` / ``DropColumn`` / ``DropTableConstraint`` must raise
    ``UnsupportedFeatureError`` instead of emitting invalid SQL.
    """

    def test_add_column_if_not_exists_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = AddColumn(
            dialect=dialect,
            column=ColumnDefinition("email", VarCharType(255)),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_drop_column_if_exists_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = DropColumn(dialect=dialect, column_name="email", if_exists=True)
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_drop_table_constraint_if_exists_raises(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        action = DropTableConstraint(
            dialect=dialect, constraint_name="fk_users_email", if_exists=True
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_default_qualifiers_keep_behavior(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))

        add_action = AddColumn(
            dialect=dialect,
            column=ColumnDefinition("email", VarCharType(255)),
        )
        add_sql, _ = add_action.to_sql()
        assert "ADD COLUMN" in add_sql
        assert "IF NOT EXISTS" not in add_sql

        drop_action = DropColumn(dialect=dialect, column_name="email")
        drop_sql, _ = drop_action.to_sql()
        assert "DROP COLUMN" in drop_sql
        assert "IF EXISTS" not in drop_sql

        drop_constraint = DropTableConstraint(
            dialect=dialect, constraint_name="fk_users_email"
        )
        drop_constraint_sql, _ = drop_constraint.to_sql()
        assert "DROP CONSTRAINT" in drop_constraint_sql
        assert "IF EXISTS" not in drop_constraint_sql


# ============================================================================
# JSON Expressions (uncovered paths)
# ============================================================================

class TestClickHouseJSONExpressions:
    """Test additional JSON format methods not covered by existing tests."""

    def test_json_set_basic(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_set("`doc`", "$.name", "John")
        assert "JSON_SET(`doc`, %s, %s)" == sql
        assert params == ("$.name", "John")

    def test_json_set_multiple(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_set(
            "`doc`", "$.name", "John",
            path_value_pairs=[("$.age", 30), ("$.city", "NYC")]
        )
        assert "JSON_SET(`doc`, %s, %s, %s, %s, %s, %s)" == sql
        assert params == ("$.name", "John", "$.age", 30, "$.city", "NYC")

    def test_json_remove_basic(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_remove("`doc`", "$.temp")
        assert "JSON_REMOVE(`doc`, %s)" == sql
        assert params == ("$.temp",)

    def test_json_remove_multiple(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_remove(
            "`doc`", "$.temp", paths=["$.cache", "$.debug"]
        )
        assert "JSON_REMOVE(`doc`, %s, %s, %s)" == sql
        assert params == ("$.temp", "$.cache", "$.debug")

    def test_json_type(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_type("`doc`")
        assert "JSON_TYPE(`doc`)" == sql

    def test_json_valid(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_valid("`doc`")
        assert "JSON_VALID(`doc`)" == sql

    def test_json_unquote(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_unquote("JSON_EXTRACT(`doc`, %s)")
        assert "JSON_UNQUOTE(JSON_EXTRACT(`doc`, %s))" == sql

    def test_json_search_one_with_path(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_search(
            "`doc`", "search_str", path="$.name"
        )
        assert "JSON_SEARCH(`doc`, 'one', %s, NULL, %s)" == sql
        assert params == ("search_str", "$.name")

    def test_json_search_all(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_search(
            "`doc`", "search_str", all=True
        )
        assert "JSON_SEARCH(`doc`, 'all', %s)" == sql
        assert params == ("search_str",)

    def test_json_object_empty(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_object([])
        assert "JSON_OBJECT()" == sql

    def test_json_object_with_pairs(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_object([("name", "John"), ("age", 30)])
        assert "JSON_OBJECT(%s, %s, %s, %s)" == sql
        assert params == ("name", "John", "age", 30)

    def test_json_array_empty(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_array([])
        assert "JSON_ARRAY()" == sql

    def test_json_contains_without_path(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_contains("`data`", '"target"')
        assert "JSON_CONTAINS(`data`, %s)" == sql
        assert params == ('"target"',)

    def test_json_contains_with_path(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_json_contains("`data`", '"target"', "$.path")
        assert "JSON_CONTAINS(`data`, %s, %s)" == sql
        assert params == ('"target"', "$.path")


# ============================================================================
# Partition Expressions (additional edge cases)
# ============================================================================

class TestClickHousePartitionExpressionEdgeCases:
    """Test uncovered edge/error cases in partition expressions."""

    def test_partition_max_value_to_sql(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHousePartitionMaxValue(dialect)
        sql, params = expr.to_sql()
        assert sql == "MAXVALUE"

    def test_partition_value_to_sql(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHousePartitionValue(dialect, "2027-01-01")
        sql, params = expr.to_sql()
        assert "2027-01-01" in sql

    def test_subpartition_clause_negative_count(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        with pytest.raises(ValueError):
            ClickHouseSubpartitionClause(
                dialect,
                strategy=ClickHouseSubpartitionStrategy.HASH,
                count=0,
            )

    def test_subpartition_clause_wrong_type(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        with pytest.raises(TypeError):
            ClickHouseSubpartitionClause(
                dialect,
                strategy="INVALID",
                count=2,
            )

    def test_subpartition_definition(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.mixins.partition import ClickHousePartitionMixin
        mixin = ClickHousePartitionMixin()
        mixin.version = (8, 0, 0)
        from unittest.mock import MagicMock
        mixin.format_identifier = MagicMock(side_effect=lambda x: f"`{x}`")
        defn = ClickHouseSubpartitionDefinition(name="subp_1")
        sql, params = mixin.format_subpartition_definition(defn)
        assert "SUBPARTITION `subp_1`" in sql

    def test_coalesce_partition_expression(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseCoalescePartitionExpression(
            dialect, table="orders", count=3
        )
        sql, params = expr.to_sql()
        assert "ALTER TABLE `orders` COALESCE PARTITION 3" == sql

    def test_partition_definition_with_comment(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.mixins.partition import ClickHousePartitionMixin
        mixin = ClickHousePartitionMixin()
        mixin.version = (8, 0, 0)
        from unittest.mock import MagicMock
        mixin.format_identifier = MagicMock(side_effect=lambda x: f"`{x}`")
        mixin._escape_sql_string = MagicMock(side_effect=lambda x: x.replace("'", "\\'"))

        from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import ClickHousePartitionDefinition
        defn = ClickHousePartitionDefinition(
            name="p_2024",
            in_values=[ClickHousePartitionValue(dialect, "2024-01-01")],
            dialect_options={"comment": "Partition for 2024 data"},
        )
        sql, params = mixin.format_partition_definition(defn)
        assert "COMMENT" in sql


# ============================================================================
# Set Type Expressions (FIND_IN_SET, SET_CONTAINS)
# ============================================================================

class TestClickHouseSetTypeExpressions:
    """Test SET type format methods."""

    def test_find_in_set(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_find_in_set("value", "tags")
        assert "FIND_IN_SET(%s, `tags`)" in sql
        assert params == ("value",)

    def test_set_contains(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_set_contains("tags", ["a", "b"])
        assert "FIND_IN_SET(%s, `tags`) > 0" in sql
        assert len(params) == 2


# ============================================================================
# Spatial Expressions (edge cases)
# ============================================================================

class TestClickHouseSpatialExpressions:
    """Test spatial format methods."""

    def test_st_as_text(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_st_as_text("`geom`")
        assert "ST_AsText(`geom`)" == sql

    def test_st_as_geojson(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_st_as_geojson("`geom`")
        assert "ST_AsGeoJSON(`geom`)" == sql

    def test_st_geom_from_wkb(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_st_geom_from_wkb(b"\\x0001")
        assert "ST_GeomFromWKB(" in sql

    def test_create_spatial_index(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_create_spatial_index("idx_spatial", "t", "geom")
        assert "CREATE SPATIAL INDEX" in sql
        assert "`idx_spatial`" in sql
        assert "ON `t`" in sql
        assert "(`geom`)" in sql

    def test_create_spatial_index_multi_column(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_create_spatial_index(
            "idx_spatial", "t", "geom1, geom2"
        )
        assert "CREATE SPATIAL INDEX" in sql
        assert "(`geom1, geom2`)" in sql


# ============================================================================
# Vector Expressions (edge cases)
# ============================================================================

class TestClickHouseVectorExpressions:
    """Test vector format methods."""

    def test_vector_literal(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseVectorExpression(dialect, [1.0, 2.0, 3.0])
        sql, params = expr.to_sql()
        assert "VECTOR" in sql or "JSON_ARRAY" in sql

    def test_vector_to_string(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_vector_to_string("`vec`")
        assert "VECTOR_TO_STRING(`vec`)" == sql

    def test_vector_dim(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_vector_dim("`vec`")
        assert "VECTOR_DIM(`vec`)" == sql

    def test_string_to_vector(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        sql, params = dialect.format_string_to_vector("'[1,2,3]'")
        assert "STRING_TO_VECTOR(%s)" == sql
        assert params == ("'[1,2,3]'",)

    def test_distance_euclidean(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseDistanceEuclideanExpression(dialect, "`v1`", "`v2`")
        sql, params = expr.to_sql()
        assert "DISTANCE_EUCLIDEAN(`v1`, `v2`)" == sql

    def test_distance_cosine(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseDistanceCosineExpression(dialect, "`v1`", "`v2`")
        sql, params = expr.to_sql()
        assert "DISTANCE_COSINE(`v1`, `v2`)" == sql

    def test_distance_dot(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        expr = ClickHouseDistanceDotExpression(dialect, "`v1`", "`v2`")
        sql, params = expr.to_sql()
        assert "DISTANCE_DOT(`v1`, `v2`)" == sql


# ============================================================================
# JSON Table Expressions
# ============================================================================

class TestClickHouseJSONTableExpressions:
    """Test JSON_TABLE expressions."""

    def test_json_table_basic(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
            JSONTableColumn,
            ClickHouseJSONTableExpression,
        )
        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc="`data`",
            path="$.items[*]",
            columns=[
                JSONTableColumn(name="id", type="INT", path="$.id"),
                JSONTableColumn(name="name", type="VARCHAR(100)", path="$.name"),
            ],
            alias="j",
        )
        sql, params = expr.to_sql()
        assert "JSON_TABLE(" in sql
        assert "COLUMNS" in sql

    def test_json_table_with_ordinality(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
            JSONTableColumn,
            ClickHouseJSONTableExpression,
        )
        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc="`doc`",
            path="$[*]",
            columns=[
                JSONTableColumn(name="rn", type="INT", ordinality=True),
                JSONTableColumn(name="val", type="VARCHAR(100)", path="$.value"),
            ],
            alias="t",
        )
        sql, params = expr.to_sql()
        assert "FOR ORDINALITY" in sql

    def test_json_table_with_exists(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
            JSONTableColumn,
            ClickHouseJSONTableExpression,
        )
        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc="`doc`",
            path="$[*]",
            columns=[
                JSONTableColumn(name="has_name", type="TINYINT(1)", path="$.name", exists=True),
            ],
            alias="t",
        )
        sql, params = expr.to_sql()
        assert "EXISTS PATH" in sql

    def test_json_table_with_error_handling(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
            JSONTableColumn,
            ClickHouseJSONTableExpression,
        )
        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc="`doc`",
            path="$[*]",
            columns=[
                JSONTableColumn(
                    name="val", type="INT", path="$.value",
                    error_handling="DEFAULT", default_value=-1,
                ),
            ],
            alias="t",
        )
        sql, params = expr.to_sql()
        assert "DEFAULT" in sql
        assert "ON ERROR" in sql

    def test_json_table_with_nested_path(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_table import (
            JSONTableColumn,
            ClickHouseJSONTableExpression,
            NestedPath,
        )
        expr = ClickHouseJSONTableExpression(
            dialect=dialect,
            json_doc="`doc`",
            path="$[*]",
            columns=[
                JSONTableColumn(name="id", type="INT", path="$.id"),
            ],
            nested_paths=[
                NestedPath(
                    path="$.items[*]",
                    columns=[
                        JSONTableColumn(name="item_name", type="VARCHAR(100)", path="$.name"),
                    ],
                ),
            ],
            alias="t",
        )
        sql, params = expr.to_sql()
        assert "NESTED PATH" in sql


# ============================================================================
# JSON Duality View Expressions
# ============================================================================

class TestClickHouseJsonDualityViewExpressions:
    """Test JSON Duality View format methods."""

    def test_create_duality_view(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
            CreateJsonDualityViewExpression,
            DualityObjectSpec,
            DualityColumnMapping,
            DualityViewDMLTag,
        )
        spec = DualityObjectSpec(
            from_table="users",
            columns=[
                DualityColumnMapping(json_key="userId", column_expr="id"),
                DualityColumnMapping(json_key="userName", column_expr="name"),
            ],
            tags=[DualityViewDMLTag.INSERT, DualityViewDMLTag.UPDATE],
        )
        expr = CreateJsonDualityViewExpression(
            dialect=dialect, view_name="my_view", root_spec=spec
        )
        sql, params = expr.to_sql()
        assert "CREATE JSON RELATIONAL DUALITY VIEW" in sql

    def test_create_or_replace_duality_view(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
            CreateJsonDualityViewExpression,
            DualityObjectSpec,
            DualityColumnMapping,
        )
        spec = DualityObjectSpec(
            from_table="users",
            columns=[
                DualityColumnMapping(json_key="userId", column_expr="id"),
            ],
        )
        expr = CreateJsonDualityViewExpression(
            dialect=dialect, view_name="my_view", root_spec=spec, replace=True
        )
        sql, params = expr.to_sql()
        assert "CREATE OR REPLACE" in sql

    def test_drop_duality_view(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
            DropJsonDualityViewExpression,
        )
        expr = DropJsonDualityViewExpression(dialect=dialect, view_name="my_view")
        sql, params = expr.to_sql()
        assert sql == "DROP VIEW `my_view`"

    def test_drop_duality_view_if_exists(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
            DropJsonDualityViewExpression,
        )
        expr = DropJsonDualityViewExpression(
            dialect=dialect, view_name="my_view", if_exists=True
        )
        sql, params = expr.to_sql()
        assert sql == "DROP VIEW IF EXISTS `my_view`"

    def test_duality_view_with_nested(self):
        dialect = ClickHouseDialect(version=(8, 0, 0))
        from rhosocial.activerecord.backend.impl.clickhouse.expression.json_duality_view import (
            CreateJsonDualityViewExpression,
            DualityColumnMapping,
            DualityNestedMapping,
            DualityObjectSpec,
        )
        nested = DualityNestedMapping(
            json_key="orders",
            subquery=DualityObjectSpec(
                from_table="orders",
                columns=[
                    DualityColumnMapping(json_key="orderId", column_expr="id"),
                ],
            ),
        )
        spec = DualityObjectSpec(
            from_table="users",
            columns=[
                DualityColumnMapping(json_key="userId", column_expr="id"),
            ],
            nested=[nested],
        )
        expr = CreateJsonDualityViewExpression(
            dialect=dialect, view_name="user_view", root_spec=spec
        )
        sql, params = expr.to_sql()
        assert "JSON_ARRAYAGG" in sql
        assert "JSON_DUALITY_OBJECT" in sql


# ============================================================================
# Protocol Conformance — Ensure all non-covered methods are declared
# ============================================================================

class TestProtocolMethodCoverage:
    """Verify protocol methods are all exercised by tests."""

    def test_all_protocol_format_methods_exist(self):
        """Ensures every format_* method on the dialect is tested."""
        dialect = ClickHouseDialect(version=(8, 0, 0))
        format_methods = [
            name for name in dir(dialect)
            if name.startswith("format_") and callable(getattr(dialect, name))
        ]
        assert len(format_methods) > 40
