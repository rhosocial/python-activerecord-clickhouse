# tests/rhosocial/activerecord_clickhouse_test/feature/basic/connection/test_active_record_context.py
"""
Basic ActiveRecord Context Test Module for ClickHouse backend.

This module imports and runs the shared tests from the testsuite package,
ensuring ClickHouse backend compatibility for connection pool context awareness.
"""


# Import shared tests from testsuite package
from rhosocial.activerecord.testsuite.feature.basic.connection.test_active_record_context import *  # noqa: F403

import pytest  # noqa: E402


# test_deeply_nested_contexts uses pool.transaction() which requires
# transaction begin/commit/rollback semantics (unsupported in ClickHouse).
def _clickhouse_deeply_nested_contexts(self, sync_pool_and_model):
    pytest.skip("ClickHouse does not support pool.transaction()")


TestSyncActiveRecordContext.test_deeply_nested_contexts = _clickhouse_deeply_nested_contexts

