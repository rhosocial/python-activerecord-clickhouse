# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_ddl_spec_protocol.py
"""ClickHouse DDL feature-spec claiming tests (``build_spec``).

Generic Specs translate via the core ``DDLSpecBuildingMixin`` (inherited from
``SQLDialectBase``); the ClickHouse dialect claims them without any backend-side
override. Spec claiming and expression building are asserted independently of
rendering: ClickHouse uses MySQL-style partition fail-fast (partition rendering
is its own feature area) and rejects UNIQUE/FOREIGN KEY table constraints at
render time, while its table-constraint renderer does not emit generic CHECK
text — so the model-integration tests assert on the built expression rather
than rendered SQL for constraint kinds ClickHouse renders differently. The
base ``PartitionSpec`` marker stays unclaimed and the generated table remains
unpartitioned. Foreign/unclaimed Specs return ``None`` (silently ignored).
"""

import pytest

from rhosocial.activerecord.base import (
    CheckSpec, DefaultSpec, ForeignKeySpec, IndexSpec,
    NotNullSpec, PartitionSpec, PrimaryKeySpec, UniqueSpec,
)
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect


@pytest.fixture
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


class TestProtocolConformance:
    def test_build_spec_returns_none_for_unknown(self, dialect):
        assert dialect.build_spec(object()) is None

    def test_build_spec_returns_none_for_base_partition_marker(self, dialect):
        # ClickHouse partitioning is MySQL-style fail-fast (rendering is gated
        # by its own partition feature area); the base PartitionSpec marker is
        # not claimed by the generic implementation and the core default
        # (None) holds.
        assert dialect.build_spec(PartitionSpec()) is None


class TestGenericSpecTranslation:
    def test_unique_spec(self, dialect):
        result = dialect.build_spec(UniqueSpec(["a", "b"], name="uq_ab"))
        assert result.columns == ["a", "b"]

    def test_check_spec_lazy(self, dialect):
        result = dialect.build_spec(
            CheckSpec(lambda d: Column(d, "age") >= 18, name="ck_age")
        )
        assert result.check_condition is not None

    def test_not_null_spec(self, dialect):
        result = dialect.build_spec(NotNullSpec(column="a"))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraint, ColumnConstraintType)
        assert isinstance(result, ColumnConstraint)
        assert result.constraint_type == ColumnConstraintType.NOT_NULL

    def test_primary_key_single(self, dialect):
        result = dialect.build_spec(PrimaryKeySpec(["id"]))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraint, ColumnConstraintType)
        assert isinstance(result, ColumnConstraint)
        assert result.constraint_type == ColumnConstraintType.PRIMARY_KEY

    def test_primary_key_composite(self, dialect):
        result = dialect.build_spec(PrimaryKeySpec(["a", "b"]))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import TableConstraint
        assert isinstance(result, TableConstraint)
        assert result.columns == ["a", "b"]

    def test_default_spec(self, dialect):
        result = dialect.build_spec(DefaultSpec(column="status", value="active"))
        assert result.constraint_type.name == "DEFAULT"

    def test_foreign_key_spec(self, dialect):
        result = dialect.build_spec(
            ForeignKeySpec(["user_id"], "users", ["id"], on_delete="CASCADE")
        )
        from rhosocial.activerecord.backend.expression.statements.ddl_table import ForeignKeyConstraint
        assert isinstance(result, ForeignKeyConstraint)
        assert result.columns == ["user_id"]

    def test_index_spec(self, dialect):
        result = dialect.build_spec(IndexSpec(columns=["email"], name="ix_email"))
        from rhosocial.activerecord.backend.expression.statements.ddl_table import IndexDefinition
        assert isinstance(result, IndexDefinition)


class TestModelIntegration:
    def test_model_spec_constraints(self, dialect):
        # ClickHouse rejects UNIQUE table constraints at render time; assert
        # claiming at the expression level instead of rendered SQL.
        from rhosocial.activerecord.backend.expression.statements.ddl_table import TableConstraintType
        from rhosocial.activerecord.model import ActiveRecord

        class T(ActiveRecord):
            __table_name__ = "t"
            __table_constraints__ = [
                UniqueSpec(columns=["a", "b"], name="uq_ab"),
                CheckSpec(lambda d: Column(d, "x") >= 0, name="ck_x"),
            ]
            a: int
            b: int
            x: int

        expr = T.generate_create_table(dialect)
        by_type = {c.constraint_type: c for c in expr.table_constraints}
        assert TableConstraintType.UNIQUE in by_type
        assert by_type[TableConstraintType.UNIQUE].columns == ["a", "b"]
        assert TableConstraintType.CHECK in by_type
        assert by_type[TableConstraintType.CHECK].check_condition is not None

    def test_model_unclaimed_partition_is_ignored(self, dialect):
        from rhosocial.activerecord.model import ActiveRecord

        class T(ActiveRecord):
            __table_name__ = "t"
            __table_partition__ = [PartitionSpec()]
            x: int

        expr = T.generate_create_table(dialect)
        assert expr.partition is None
