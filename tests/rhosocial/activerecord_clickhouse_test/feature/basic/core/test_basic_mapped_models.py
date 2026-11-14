# tests/rhosocial/activerecord_clickhouse_test/feature/basic/core/test_basic_mapped_models.py
"""
This bridge file imports all test cases related to mapped models from the
testsuite.

The fixtures those cases request (including ``mapped_models_fixtures``) come
from the shared ``basic`` topic conftest inherited from the parent directory.

IMPORTANT:
- Do NOT add any test logic directly in this file.
- This file is solely responsible for wiring up the testsuite's generic tests
  with the backend's fixtures and configuration.
"""

# Wildcard import all test cases from the testsuite's test file.
from rhosocial.activerecord.testsuite.feature.basic.fields.test_example_basic_fixtures import *  # noqa: F403
