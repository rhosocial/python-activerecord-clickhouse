# tests/rhosocial/activerecord_clickhouse_test/feature/query/conftest.py
"""Fixtures for the query feature tests.

The topic conftest supplies the shared fixtures; every leaf directory declares
its own minimal test set (its tables and its database) by importing the group
the shared suite defines for it.
"""
from rhosocial.activerecord.testsuite.feature.query.conftest import *  # noqa: F401,F403
