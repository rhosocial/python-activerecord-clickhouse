# tests/rhosocial/activerecord_clickhouse_test/feature/basic/crud_composite_pk/test_composite_pk_crud.py
"""Bridge file: runs the shared ``basic/crud_composite_pk`` sync tests."""

from rhosocial.activerecord.testsuite.feature.basic.crud_composite_pk.test_composite_pk_crud import *  # noqa: F401,F403
from rhosocial.activerecord.testsuite.feature.basic.crud_composite_pk.test_composite_pk_crud import (  # noqa: E402
    TestCompositePKInsert,
    TestCompositePKWithColumnMapping,
)

import pytest  # noqa: E402


# ClickHouse's MergeTree engine does not enforce PRIMARY KEY / UNIQUE at write
# time: a duplicate-key INSERT succeeds (the engine only deduplicates
# eventually, at merge). The shared tests expect an IntegrityError, so skip
# the two that rely on write-time uniqueness. This is a capability gap, not a
# bug in the backend's CRUD path.
def _clickhouse_skip_no_write_time_uniqueness(self, *args, **kwargs):  # noqa: F811,ARG001
    pytest.skip("ClickHouse has no write-time PRIMARY KEY/UNIQUE enforcement (MergeTree)")


TestCompositePKInsert.test_insert_duplicate_pk = _clickhouse_skip_no_write_time_uniqueness
TestCompositePKWithColumnMapping.test_insert_duplicate_pk_raises = (
    _clickhouse_skip_no_write_time_uniqueness
)
