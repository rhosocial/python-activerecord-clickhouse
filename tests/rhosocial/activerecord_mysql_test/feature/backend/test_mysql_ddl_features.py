# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_clickhouse_ddl_features.py
"""
ClickHouse DDL features tests.

This module tests ClickHouse-specific DDL features including:
- Storage options (ENGINE, CHARSET, COLLATE)
- Table-level COMMENT
- Column-level COMMENT
- AUTO_INCREMENT
- Inline index definitions
- ENUM type helper
"""

import pytest
from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    DateTimeType,
    IntegerType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.types import ClickHouseEnumType, ClickHouseSetType


class TestClickHouseStorageOptions:
    """Tests for ClickHouse storage options (ENGINE, CHARSET, COLLATE)."""

    def test_engine_option(self):
        """Test ENGINE storage option."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect, table="test_table", columns=columns, storage_options={"ENGINE": "InnoDB"}
        )
        sql, params = expr.to_sql()
        assert "ENGINE='InnoDB'" in sql

    def test_charset_option(self):
        """Test DEFAULT CHARSET storage option."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect, table="test_table", columns=columns, storage_options={"DEFAULT CHARSET": "utf8mb4"}
        )
        sql, params = expr.to_sql()
        assert "DEFAULT CHARSET='utf8mb4'" in sql

    def test_collate_option(self):
        """Test COLLATE storage option."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect, table="test_table", columns=columns, storage_options={"COLLATE": "utf8mb4_unicode_ci"}
        )
        sql, params = expr.to_sql()
        assert "COLLATE='utf8mb4_unicode_ci'" in sql

    def test_multiple_storage_options(self):
        """Test multiple storage options combined."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect,
            table="test_table",
            columns=columns,
            storage_options={"ENGINE": "InnoDB", "DEFAULT CHARSET": "utf8mb4", "COLLATE": "utf8mb4_unicode_ci"},
        )
        sql, params = expr.to_sql()
        assert "ENGINE='InnoDB'" in sql
        assert "DEFAULT CHARSET='utf8mb4'" in sql
        assert "COLLATE='utf8mb4_unicode_ci'" in sql

    def test_storage_options_with_if_not_exists(self):
        """Test storage options with IF NOT EXISTS."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect,
            table="test_table",
            columns=columns,
            if_not_exists=True,
            storage_options={"ENGINE": "InnoDB"},
        )
        sql, params = expr.to_sql()
        assert "IF NOT EXISTS" in sql
        assert "ENGINE='InnoDB'" in sql


class TestClickHouseTableComment:
    """Tests for ClickHouse table-level COMMENT."""

    def test_table_comment(self):
        """Test table-level COMMENT."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect, table="users", columns=columns, dialect_options={"comment": "用户信息表"}
        )
        sql, params = expr.to_sql()
        assert "COMMENT '用户信息表'" in sql

    def test_table_comment_with_storage_options(self):
        """Test table COMMENT with storage options."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect,
            table="users",
            columns=columns,
            storage_options={"ENGINE": "InnoDB", "DEFAULT CHARSET": "utf8mb4"},
            dialect_options={"comment": "用户信息表"},
        )
        sql, params = expr.to_sql()
        assert "ENGINE='InnoDB'" in sql
        assert "DEFAULT CHARSET='utf8mb4'" in sql
        assert "COMMENT '用户信息表'" in sql

    def test_table_comment_special_characters(self):
        """Test table COMMENT with special characters."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)])]
        expr = CreateTableExpression(
            dialect=dialect, table="test", columns=columns, dialect_options={"comment": "测试's表"}
        )
        sql, params = expr.to_sql()
        assert "COMMENT" in sql


class TestClickHouseColumnComment:
    """Tests for ClickHouse column-level COMMENT."""

    def test_column_comment(self):
        """Test column-level COMMENT."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition(
                "id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)], comment="主键ID"
            ),
            ColumnDefinition("name", VarCharType(100), comment="用户名"),
        ]
        expr = CreateTableExpression(dialect=dialect, table="users", columns=columns)
        sql, params = expr.to_sql()
        assert "COMMENT '主键ID'" in sql
        assert "COMMENT '用户名'" in sql

    def test_column_comment_with_table_comment(self):
        """Test column COMMENT with table COMMENT."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition(
                "id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)], comment="主键"
            ),
            ColumnDefinition("name", VarCharType(100), comment="名称"),
        ]
        expr = CreateTableExpression(
            dialect=dialect, table="users", columns=columns, dialect_options={"comment": "用户表"}
        )
        sql, params = expr.to_sql()
        assert "COMMENT '主键'" in sql
        assert "COMMENT '名称'" in sql
        assert "COMMENT '用户表'" in sql


class TestClickHouseAutoIncrement:
    """Tests for ClickHouse AUTO_INCREMENT."""

    def test_auto_increment_primary_key(self):
        """Test AUTO_INCREMENT with PRIMARY KEY."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition(
                "id",
                BigIntType(),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.NOT_NULL),
                    ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
                ],
            )
        ]
        expr = CreateTableExpression(dialect=dialect, table="users", columns=columns)
        sql, params = expr.to_sql()
        assert "AUTO_INCREMENT" in sql
        assert "PRIMARY KEY" in sql

    def test_auto_increment_with_comment(self):
        """Test AUTO_INCREMENT with column COMMENT."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition(
                "id",
                BigIntType(),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.NOT_NULL),
                    ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
                ],
                comment="自增主键",
            )
        ]
        expr = CreateTableExpression(dialect=dialect, table="users", columns=columns)
        sql, params = expr.to_sql()
        assert "AUTO_INCREMENT" in sql
        assert "COMMENT '自增主键'" in sql

    def test_auto_increment_not_null(self):
        """Test that AUTO_INCREMENT requires NOT NULL."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition(
                "id",
                BigIntType(),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.NOT_NULL),
                    ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
                ],
            )
        ]
        expr = CreateTableExpression(dialect=dialect, table="test", columns=columns)
        sql, params = expr.to_sql()
        assert "NOT NULL" in sql
        assert "AUTO_INCREMENT" in sql


class TestClickHouseInlineIndex:
    """Tests for ClickHouse inline index definitions."""

    def test_simple_index(self):
        """Test simple INDEX definition."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(100)),
        ]
        indexes = [IndexDefinition("idx_name", ["name"])]
        expr = CreateTableExpression(dialect=dialect, table="users", columns=columns, indexes=indexes)
        sql, params = expr.to_sql()
        assert "INDEX `idx_name`" in sql
        assert "(`name`)" in sql

    def test_unique_index(self):
        """Test UNIQUE INDEX definition."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("email", VarCharType(100)),
        ]
        indexes = [IndexDefinition("idx_email", ["email"], unique=True)]
        expr = CreateTableExpression(dialect=dialect, table="users", columns=columns, indexes=indexes)
        sql, params = expr.to_sql()
        assert "UNIQUE INDEX" in sql
        assert "idx_email" in sql

    def test_composite_index(self):
        """Test composite index on multiple columns."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("user_id", IntegerType()),
            ColumnDefinition("created_at", DateTimeType()),
        ]
        indexes = [IndexDefinition("idx_user_created", ["user_id", "created_at"])]
        expr = CreateTableExpression(dialect=dialect, table="orders", columns=columns, indexes=indexes)
        sql, params = expr.to_sql()
        assert "`user_id`, `created_at`" in sql or "`user_id`,`created_at`" in sql

    def test_index_with_type(self):
        """Test INDEX with USING clause."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("name", VarCharType(100)),
        ]
        indexes = [IndexDefinition("idx_name", ["name"], type="BTREE")]
        expr = CreateTableExpression(dialect=dialect, table="users", columns=columns, indexes=indexes)
        sql, params = expr.to_sql()
        assert "USING BTREE" in sql

    def test_hash_index(self):
        """Test HASH index type."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("key", VarCharType(100)),
        ]
        indexes = [IndexDefinition("idx_key", ["key"], type="HASH")]
        expr = CreateTableExpression(dialect=dialect, table="cache", columns=columns, indexes=indexes)
        sql, params = expr.to_sql()
        assert "USING HASH" in sql

    def test_multiple_indexes(self):
        """Test multiple inline indexes."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("email", VarCharType(100)),
            ColumnDefinition("username", VarCharType(50)),
        ]
        indexes = [IndexDefinition("idx_email", ["email"], unique=True), IndexDefinition("idx_username", ["username"])]
        expr = CreateTableExpression(dialect=dialect, table="users", columns=columns, indexes=indexes)
        sql, params = expr.to_sql()
        assert "UNIQUE INDEX `idx_email`" in sql
        assert "INDEX `idx_username`" in sql


class TestClickHouseEnumType:
    """Tests for ClickHouse ENUM type helper."""

    def test_simple_enum(self):
        """Test simple ENUM SQL representation via to_sql()."""
        dialect = ClickHouseDialect()
        enum_type = ClickHouseEnumType(["pending", "processing", "completed"])
        sql, _ = enum_type.to_sql(dialect)
        assert sql == "ENUM('pending','processing','completed')"

    def test_enum_with_charset(self):
        """Test ENUM with CHARACTER SET via to_sql()."""
        dialect = ClickHouseDialect()
        enum_type = ClickHouseEnumType(["active", "inactive"], charset="utf8mb4")
        sql, _ = enum_type.to_sql(dialect)
        assert "CHARACTER SET utf8mb4" in sql

    def test_enum_with_collation(self):
        """Test ENUM with COLLATE via to_sql()."""
        dialect = ClickHouseDialect()
        enum_type = ClickHouseEnumType(["a", "b"], collation="utf8mb4_bin")
        sql, _ = enum_type.to_sql(dialect)
        assert "COLLATE utf8mb4_bin" in sql

    def test_enum_with_charset_and_collation(self):
        """Test ENUM with both CHARACTER SET and COLLATE via to_sql()."""
        dialect = ClickHouseDialect()
        enum_type = ClickHouseEnumType(["pending", "done"], charset="utf8mb4", collation="utf8mb4_unicode_ci")
        sql, _ = enum_type.to_sql(dialect)
        assert "CHARACTER SET utf8mb4" in sql
        assert "COLLATE utf8mb4_unicode_ci" in sql

    def test_enum_str_representation(self):
        """Test ENUM SQL representation via to_sql()."""
        dialect = ClickHouseDialect()
        enum_type = ClickHouseEnumType(["yes", "no"])
        sql, _ = enum_type.to_sql(dialect)
        assert sql == "ENUM('yes','no')"

    def test_enum_repr(self):
        """Test ENUM repr."""
        enum_type = ClickHouseEnumType(["a", "b"])
        repr_str = repr(enum_type)
        assert "ClickHouseEnumType" in repr_str
        assert "a" in repr_str

    def test_enum_empty_values_raises_error(self):
        """Test that empty values list raises ValueError."""
        with pytest.raises(ValueError, match="ENUM must have at least one value"):
            ClickHouseEnumType([])

    def test_enum_in_column_definition(self):
        """Test ENUM type used in column definition."""
        dialect = ClickHouseDialect()
        status_enum = ClickHouseEnumType(["draft", "published", "archived"])
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(
                "status", status_enum, constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]
            ),
        ]
        expr = CreateTableExpression(dialect=dialect, table="articles", columns=columns)
        sql, params = expr.to_sql()
        assert "ENUM('draft','published','archived')" in sql


class TestClickHouseSetType:
    """Tests for ClickHouse SET type helper."""

    def test_simple_set(self):
        """Test simple SET SQL representation via to_sql()."""
        dialect = ClickHouseDialect()
        set_type = ClickHouseSetType(["read", "write", "execute"])
        sql, _ = set_type.to_sql(dialect)
        assert sql == "SET('read','write','execute')"

    def test_set_with_charset(self):
        """Test SET with CHARACTER SET via to_sql()."""
        dialect = ClickHouseDialect()
        set_type = ClickHouseSetType(["tag1", "tag2"], charset="utf8mb4")
        sql, _ = set_type.to_sql(dialect)
        assert "CHARACTER SET utf8mb4" in sql

    def test_set_with_collation(self):
        """Test SET with COLLATE via to_sql()."""
        dialect = ClickHouseDialect()
        set_type = ClickHouseSetType(["a", "b"], collation="utf8mb4_bin")
        sql, _ = set_type.to_sql(dialect)
        assert "COLLATE utf8mb4_bin" in sql

    def test_set_str_representation(self):
        """Test SET SQL representation via to_sql()."""
        dialect = ClickHouseDialect()
        set_type = ClickHouseSetType(["x", "y"])
        sql, _ = set_type.to_sql(dialect)
        assert sql == "SET('x','y')"

    def test_set_repr(self):
        """Test SET repr."""
        set_type = ClickHouseSetType(["a", "b"])
        repr_str = repr(set_type)
        assert "ClickHouseSetType" in repr_str

    def test_set_empty_values_raises_error(self):
        """Test that empty values list raises ValueError."""
        with pytest.raises(ValueError, match="SET must have at least one value"):
            ClickHouseSetType([])


class TestClickHouseTableConstraints:
    """Tests for ClickHouse table-level constraints."""

    def test_primary_key_constraint(self):
        """Test PRIMARY KEY table constraint."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("id", IntegerType()), ColumnDefinition("name", VarCharType(100))]
        table_constraints = [TableConstraint(TableConstraintType.PRIMARY_KEY, columns=["id"])]
        expr = CreateTableExpression(
            dialect=dialect, table="users", columns=columns, table_constraints=table_constraints
        )
        sql, params = expr.to_sql()
        assert "PRIMARY KEY (`id`)" in sql

    def test_unique_constraint(self):
        """Test UNIQUE table constraint."""
        dialect = ClickHouseDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition("email", VarCharType(100)),
        ]
        table_constraints = [TableConstraint(TableConstraintType.UNIQUE, columns=["email"])]
        expr = CreateTableExpression(
            dialect=dialect, table="users", columns=columns, table_constraints=table_constraints
        )
        sql, params = expr.to_sql()
        assert "UNIQUE (`email`)" in sql

    def test_composite_primary_key(self):
        """Test composite PRIMARY KEY."""
        dialect = ClickHouseDialect()
        columns = [ColumnDefinition("user_id", IntegerType()), ColumnDefinition("role_id", IntegerType())]
        table_constraints = [TableConstraint(TableConstraintType.PRIMARY_KEY, columns=["user_id", "role_id"])]
        expr = CreateTableExpression(
            dialect=dialect, table="user_roles", columns=columns, table_constraints=table_constraints
        )
        sql, params = expr.to_sql()
        assert "PRIMARY KEY" in sql
        assert "`user_id`" in sql
        assert "`role_id`" in sql


class TestClickHouseDropTable:
    """Tests for ClickHouse DROP TABLE."""

    def test_drop_table_if_exists(self):
        """Test DROP TABLE IF EXISTS."""
        dialect = ClickHouseDialect()
        expr = DropTableExpression(dialect=dialect, table="test_table", if_exists=True)
        sql, params = expr.to_sql()
        assert sql == "DROP TABLE IF EXISTS `test_table`"
        assert params == ()

    def test_drop_table_without_if_exists(self):
        """Test DROP TABLE without IF EXISTS."""
        dialect = ClickHouseDialect()
        expr = DropTableExpression(dialect=dialect, table="test_table", if_exists=False)
        sql, params = expr.to_sql()
        assert sql == "DROP TABLE `test_table`"
        assert params == ()


class TestClickHouseCompleteTableCreation:
    """Tests for complete ClickHouse table creation with all features."""

    def test_complete_table_creation(self):
        """Test complete table creation with all ClickHouse features."""
        dialect = ClickHouseDialect()
        status_enum = ClickHouseEnumType(["active", "inactive", "deleted"])

        columns = [
            ColumnDefinition(
                "id",
                BigIntType(),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.NOT_NULL),
                    ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
                ],
                comment="Primary key",
            ),
            ColumnDefinition(
                "name",
                VarCharType(100),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)],
                comment="User name",
            ),
            ColumnDefinition(
                "email",
                VarCharType(255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)],
                comment="Email address",
            ),
            ColumnDefinition(
                "status",
                status_enum,
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)],
                comment="User status",
            ),
            ColumnDefinition("created_at", DateTimeType(), comment="Creation timestamp"),
        ]

        indexes = [IndexDefinition("idx_email", ["email"], unique=True), IndexDefinition("idx_status", ["status"])]

        expr = CreateTableExpression(
            dialect=dialect,
            table="users",
            columns=columns,
            indexes=indexes,
            if_not_exists=True,
            storage_options={"ENGINE": "InnoDB", "DEFAULT CHARSET": "utf8mb4", "COLLATE": "utf8mb4_unicode_ci"},
            dialect_options={"comment": "User information table"},
        )

        sql, params = expr.to_sql()

        # Verify all components are present
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "`users`" in sql
        assert "BIGINT" in sql
        assert "NOT NULL" in sql
        assert "PRIMARY KEY" in sql
        assert "AUTO_INCREMENT" in sql
        assert "VARCHAR(100)" in sql
        assert "VARCHAR(255)" in sql
        assert "ENUM('active','inactive','deleted')" in sql
        assert "DATETIME" in sql
        assert "UNIQUE INDEX `idx_email`" in sql
        assert "INDEX `idx_status`" in sql
        assert "ENGINE='InnoDB'" in sql
        assert "DEFAULT CHARSET='utf8mb4'" in sql
        assert "COLLATE='utf8mb4_unicode_ci'" in sql
        assert "COMMENT 'User information table'" in sql
        # Column comments
        assert "COMMENT 'Primary key'" in sql
        assert "COMMENT 'User name'" in sql
        assert "COMMENT 'Email address'" in sql
        assert "COMMENT 'User status'" in sql
        assert "COMMENT 'Creation timestamp'" in sql
