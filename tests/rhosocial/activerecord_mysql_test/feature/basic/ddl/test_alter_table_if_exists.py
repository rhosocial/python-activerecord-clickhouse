# tests/rhosocial/activerecord_clickhouse_test/feature/basic/ddl/test_alter_table_if_exists.py
"""
ALTER TABLE IF [NOT] EXISTS tests (sync) for the ClickHouse backend.

Thin bridge that runs the shared testsuite contract against the ClickHouse
dialect, which supports none of the three modifiers (all ``supports_*``
switches return ``False``).
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.test_alter_table_if_exists import *  # noqa: F403
