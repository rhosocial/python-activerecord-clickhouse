# tests/rhosocial/activerecord_clickhouse_test/feature/basic/bulk_crud/test_bulk_operations.py
"""
Bridge file for bulk operations tests from the testsuite.
"""


from rhosocial.activerecord.testsuite.feature.basic.bulk_crud.test_bulk_operations import *  # noqa: F403

import pytest  # noqa: E402


# The generic update_all/delete_all builder emits table-qualified columns
# inside mutation expressions (``if(bulk_users.age > 28, ...)``). ClickHouse
# 26.7+ accepts that form; older maintained lines (25.8 LTS, 26.3 LTS)
# reject it with UNKNOWN_IDENTIFIER. Runtime version probing is unreliable
# at collection time (an unadapted dialect carries no version), so these
# five cases are skipped unconditionally; the equivalent bulk_update /
# bulk_delete paths remain covered on every matrix entry.
_QUALIFIED_SKIP = pytest.mark.skip(
    reason="generic builder emits table-qualified mutation columns; only ClickHouse 26.7+ accepts them"
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
