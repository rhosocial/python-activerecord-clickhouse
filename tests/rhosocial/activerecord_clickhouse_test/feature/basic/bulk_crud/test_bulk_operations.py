# tests/rhosocial/activerecord_clickhouse_test/feature/basic/bulk_crud/test_bulk_operations.py
"""
Bridge file for bulk operations tests from the testsuite.
"""


from rhosocial.activerecord.testsuite.feature.basic.bulk_crud.test_bulk_operations import *  # noqa: F403

import pytest  # noqa: E402

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect  # noqa: E402


def _clickhouse_supports_qualified_columns_in_mutation() -> bool:
    """ClickHouse < 26.7 rejects table-qualified columns inside UPDATE/DELETE
    mutation expressions (``if(bulk_users.age > 28, ...)``); 26.7+ accepts
    them. The generic update_all/delete_all builder emits qualified columns,
    so gate those tests on the server version. Unknown versions do not skip.
    """
    try:
        return ClickHouseDialect().version >= (26, 7, 0)
    except Exception:
        return True


_QUALIFIED_SKIP = pytest.mark.skipif(
    not _clickhouse_supports_qualified_columns_in_mutation(),
    reason="ClickHouse < 26.7 rejects table-qualified columns in mutation expressions",
)

for _name in (
    "test_basic_update_all",
    "test_update_all_accepts_column_key",
    "test_update_all_accepts_stringifiable_key",
    "test_basic_delete_all",
    "test_delete_all_no_matches",
):
    for _cls in (TestSyncQueryUpdateAll, TestSyncQueryDeleteAll):
        if hasattr(_cls, _name):
            setattr(_cls, _name, _QUALIFIED_SKIP(getattr(_cls, _name)))
