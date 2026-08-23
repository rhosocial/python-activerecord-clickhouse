# tests/rhosocial/activerecord_clickhouse_test/feature/basic/type_adapter/test_type_adapter.py
"""
This is a "bridge" file for the basic features test group, specifically for
type adapter tests.

Its purpose is to import the generic tests from the `rhosocial-activerecord-testsuite`
package and make them discoverable by `pytest` within this project's test run.
"""

# Import all tests from the generic testsuite file.
from rhosocial.activerecord.testsuite.feature.basic.type_adapter.test_type_adapter import *  # noqa: F403

import pytest  # noqa: E402


# Inserting NULL into a NOT NULL column raises IntegrityError on SQL databases.
# ClickHouse does not enforce NOT NULL for String columns: NULL values are
# silently coerced to empty strings, so no error is raised.
def _clickhouse_test_db_null(self, type_adapter_fixtures):
    pytest.skip("ClickHouse coerces NULL to empty string for String columns (no NOT NULL violation)")


TestTypeAdapter.test_db_null_with_non_optional_field_raises_error = _clickhouse_test_db_null