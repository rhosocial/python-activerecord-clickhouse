# tests/rhosocial/activerecord_clickhouse_test/feature/basic/core/conftest.py
"""L2 backend fixtures for the ``basic/core`` directory.

The shared test this directory runs asserts the fixture shape only: that
``mapped_models_fixtures`` yields the three mapped models, each an
``ActiveRecord`` subclass.  That fixture is the testsuite ``basic`` topic's
own, and it configures the models against ``database_config``, so this
directory owns the database and the tables the mapped models read and write.

The fixture definitions are the testsuite basic topic's: ClickHouse's storage
clause is appended by the table renderer, so nothing ClickHouse-specific
appears in this conftest.
"""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

from pathlib import Path

import pytest

from rhosocial.activerecord.testsuite.feature.basic.fixtures.field_models import (
    FIELD_FIXTURES,
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.operations import (
    create_schema,
    drop_schema,
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.user_models import (
    USER_FIXTURES,
)

FIXTURES = USER_FIXTURES + FIELD_FIXTURES


def _database_name() -> str:
    """Database name from this directory's namespace (below ``feature``)."""
    parts = Path(__file__).parent.parts
    start = parts.index("feature") + 1
    return "test_" + "_".join(parts[start:])




# This directory owns a database shared by all its tests within a scenario;
# pin them to one worker so setup/teardown never races on the same database.
DECLARATION = Declaration(
    parallel=True,
    purpose="Directory-owned database shared by this test group.",
)

@pytest.fixture(scope="session")
def database_config(backend_scenario):
    """Scenario, connection configuration, and the directory database name."""
    name = _database_name()
    return backend_scenario, backend_scenario.make_config(name), name


@pytest.fixture(scope="session")
def database(database_config):
    """The directory's database, prepared once and left for later files."""
    scenario, config, name = database_config
    scenario.reset_database(name)
    backend = scenario.backend_class(connection_config=config)
    backend.connect()
    backend.introspect_and_adapt()
    yield backend
    backend.disconnect()


@pytest.fixture(scope="function", autouse=True)
def schema(database):
    """Drop and recreate the tables this directory uses, before every test."""
    create_schema(database, FIXTURES)
    yield
    drop_schema(database, FIXTURES)
