# tests/rhosocial/activerecord_clickhouse_test/feature/basic/test_crud.py
"""
This is a "bridge" file for the basic features test group.

Its purpose is to import the generic tests from the `rhosocial-activerecord-testsuite`
package and make them discoverable by `pytest` within this project's test run.

This approach allows us to keep the actual test logic separate and reusable across
different backends, while this file acts as the entry point for running those
tests against our specific (SQLite) backend.
"""

# IMPORTANT: These imports are essential for pytest to work correctly.
# Even though they may be flagged as "unused" by some IDEs or linters,
# they must not be removed. They are the mechanism by which pytest discovers
# the fixtures and the tests from the external testsuite package.

# Although the root conftest.py sets up the environment, explicitly importing
# the fixtures here makes the dependency clear and can help with test discovery
# in some IDEs. These fixtures are defined in the testsuite package and are
# parameterized to run against the scenarios defined in `providers/scenarios.py`.

# By importing *, we bring all the test functions (e.g., `test_create_user`)
# from the generic testsuite file into this module's scope. `pytest` then
# discovers and runs them as if they were defined directly in this file.
from rhosocial.activerecord.testsuite.feature.basic.crud.test_crud import *  # noqa: F403

import pytest  # noqa: E402


# ClickHouse does not support ACID transactions (no BEGIN/COMMIT/ROLLBACK), so
# the generic rollback-based transaction test cannot apply. The backend's
# transaction() context manager degrades to a no-op for compatibility with
# generic operations (e.g. bulk_create), but rollback guarantees are absent.
def _clickhouse_test_transaction_crud(self, user_class):  # noqa: F811
    pytest.skip("ClickHouse does not support ACID transactions (rollback unavailable)")


TestSyncCRUD.test_transaction_crud = _clickhouse_test_transaction_crud
# Async tests are not imported (clickhouse-connect is sync-only; the conftest
# hook skips them), so there is no TestAsyncCRUD to patch here.

