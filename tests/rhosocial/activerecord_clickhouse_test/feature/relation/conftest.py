# tests/rhosocial/activerecord_clickhouse_test/feature/relation/conftest.py
"""Fixtures for the relation feature tests.

The topic conftest supplies the fixtures and the minimal test set for this
directory's database; leaves without a shared group of their own fall back to
that contract, so they stay pinned to the same database.
"""
from rhosocial.activerecord.testsuite.feature.relation.conftest import *  # noqa: F401,F403
