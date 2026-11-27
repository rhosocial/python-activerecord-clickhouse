# tests/rhosocial/activerecord_clickhouse_test/feature/rules/backend/__init__.py
"""ClickHouse's own formal rule suite.

Every bridge here is driven by the shared testsuite rule library against
``backend/impl/clickhouse`` and this repository's tests only. No core source
and no other backend is scanned.
"""
