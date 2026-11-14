# tests/rhosocial/activerecord_clickhouse_test/feature/basic/core/conftest.py
"""The mapped-model fixture group this directory owns.

The shared test this directory runs asserts the fixture shape only: that
``mapped_models_fixtures`` yields the three mapped models, each an
``ActiveRecord`` subclass.  It performs no DDL and no DML, so the directory
owns its database (reset once per scenario) but no tables.

Creating the testsuite's generic ``users`` / ``posts`` / ``comments`` tables
here would be unnecessary: table definitions that need their own storage
choices belong with the directory that actually reads and writes them.
"""

GROUP_TABLES = ()


def ensure_database(environment):
    """Create the directory's database, or clear it when it already exists."""
    environment.reset_database()


def prepare(environment):
    """No group tables: the mapped-model test only inspects the fixtures."""


def teardown(environment):
    """No group tables: nothing to drop."""
