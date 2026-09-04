# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_default_model_ddl.py
"""Default-type model rendering — ClickHouse.

``DefaultUser`` declares plain Python types with no ``UseSqlType``; ClickHouse
derives the column types via its own suggestion mapping. ClickHouse has no
AUTO_INCREMENT, so the shared auto-increment PK cannot render; this is asserted
explicitly and a variant subclass is used for the column-type assertions.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.examples.ddl_default_types import DefaultUser


class ClickHouseDefaultUser(DefaultUser):
    __pk_auto_generated__ = False


def test_default_user_has_no_explicit_sql_types():
    assert DefaultUser.__table_field_sql_types__ == {}


def test_clickhouse_rejects_auto_increment_pk():
    dialect = ClickHouseDialect()
    with pytest.raises(UnsupportedFeatureError, match="AUTO_INCREMENT"):
        DefaultUser.generate_create_table(dialect=dialect).to_sql()


def test_clickhouse_default_user_ddl_columns():
    dialect = ClickHouseDialect()
    sql, _ = ClickHouseDefaultUser.generate_create_table(dialect=dialect).to_sql()
    assert "CREATE TABLE `default_users`" in sql
    assert "`id` Int32 PRIMARY KEY" in sql
    assert "`username` String NOT NULL" in sql
    assert "`email` String NOT NULL" in sql
    assert "`is_active` Bool NOT NULL" in sql
    assert "`balance` Float64 NOT NULL" in sql
    assert "`created_at` DateTime NOT NULL" in sql
    assert "`metadata` String NOT NULL" in sql
    assert "`avatar` String NOT NULL" in sql
    assert "`birthday` Date" in sql