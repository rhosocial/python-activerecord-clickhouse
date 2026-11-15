# tests/rhosocial/activerecord_clickhouse_test/feature/basic/core/conftest.py
"""L2 backend fixtures for the ``basic/core`` directory.

The shared test this directory runs asserts the fixture shape only: that
``mapped_models_fixtures`` yields the three mapped models, each an
``ActiveRecord`` subclass.  That fixture is the testsuite ``basic`` topic's
own, and it configures the models against ``database_config``, so this
directory owns the database and the tables the mapped models read and write.

The definitions are the testsuite basic topic's: ClickHouse's storage clause
is appended by the table renderer, so nothing ClickHouse-specific appears in
this conftest.  Table definitions that need their own storage choices belong
with the directory that actually creates them.
"""

from pathlib import Path

import pytest

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    CommentDefinition,
    PostDefinition,
    UserDefinition,
)

DDL = ExecutionOptions(stmt_type=StatementType.DDL)

DEFINITIONS = (
    UserDefinition,
    PostDefinition,
    CommentDefinition,
)


def _database_name() -> str:
    """Database name from this directory's namespace (below ``feature``)."""
    parts = Path(__file__).parent.parts
    start = parts.index("feature") + 1
    return "test_" + "_".join(parts[start:])


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
    fixtures = [definition(database.dialect) for definition in DEFINITIONS]
    for fixture in fixtures:
        database.execute(*fixture.create_table.to_sql(), options=DDL)
    yield
    for fixture in reversed(fixtures):
        database.execute(*fixture.drop_table.to_sql(), options=DDL)
