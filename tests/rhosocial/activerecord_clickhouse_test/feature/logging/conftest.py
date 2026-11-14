# tests/rhosocial/activerecord_clickhouse_test/feature/logging/conftest.py
"""The logging tests are unit-level: this directory needs no database.

The shared suite has no ``logging`` fixture group, so there is nothing to
import and no ``prepare`` / ``teardown`` group to declare.  The cases here
build a backend and drive it through a fake connection; they never request
the testsuite ``environment`` fixture.
"""
