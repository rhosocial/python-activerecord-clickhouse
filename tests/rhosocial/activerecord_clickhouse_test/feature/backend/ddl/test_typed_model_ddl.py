# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_typed_model_ddl.py
"""Cross-backend UseSqlType demonstration — ClickHouse rendering.

ClickHouse has no AUTO_INCREMENT, so the shared ``TypedUser`` auto-increment
PK cannot render there; this is asserted explicitly. A variant subclass with
the auto-generated flag disabled renders the same generic column types to
their ClickHouse-native forms.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.examples.ddl_types import TypedUser


class ClickHouseUser(TypedUser):
    __pk_auto_generated__ = False


def test_clickhouse_rejects_auto_increment_pk():
    dialect = ClickHouseDialect()
    with pytest.raises(UnsupportedFeatureError, match="AUTO_INCREMENT"):
        TypedUser.generate_create_table(dialect=dialect).to_sql()


def test_clickhouse_typed_user_ddl_columns():
    dialect = ClickHouseDialect()
    sql, _ = ClickHouseUser.generate_create_table(dialect=dialect).to_sql()
    assert "CREATE TABLE `typed_users`" in sql
    assert "`id` Int32 PRIMARY KEY" in sql
    assert "`username` String NOT NULL" in sql
    assert "`email` String NOT NULL" in sql
    assert "`is_active` Bool NOT NULL" in sql
    assert "`balance` Decimal(10, 2)" in sql
    assert "`birthday` Date" in sql
    assert "`created_at` DateTime NOT NULL" in sql
    assert "`bio` String" in sql
    assert "`metadata` String" in sql
    assert "`big_counter` Int64" in sql
    assert "`avatar` String" in sql
    assert "`wake_up_time` DateTime" in sql


def test_clickhouse_typed_user_no_per_dialect_string_keys():
    for _field_name, marker in TypedUser.__table_field_sql_types__.items():
        assert not hasattr(marker, "dialect_types")
        assert marker.data_type is not None