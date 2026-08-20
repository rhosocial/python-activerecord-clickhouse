# Test Configuration

## Overview

This section describes how to configure the testing environment for the ClickHouse backend.

## Unit Testing with Dummy Backend

The `dummy` backend is recommended for unit tests as it does not require a real database connection:

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.dummy import DummyBackend, DummyConnectionConfig


class User(ActiveRecord):
    name: str
    email: str
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'users'


# Configure Dummy backend
config = DummyConnectionConfig()
User.configure(config, DummyBackend)
```

## Integration Testing with SQLite Backend

For tests requiring real database behavior, use the SQLite backend:

```python
from rhosocial.activerecord.backend.impl.sqlite import SQLiteBackend, SQLiteConnectionConfig


class User(ActiveRecord):
    name: str
    email: str
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'users'


# Configure SQLite in-memory database
config = SQLiteConnectionConfig(database=':memory:')
User.configure(config, SQLiteBackend)
```

## End-to-End Testing with ClickHouse Backend

For complete ClickHouse behavior testing, use the ClickHouse backend:

```python
import os
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig


class User(ActiveRecord):
    name: str
    email: str
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'users'


# Read configuration from environment variables
config = ClickHouseConnectionConfig(
    host=os.environ.get('CLICKHOUSE_HOST', 'localhost'),
    port=int(os.environ.get('CLICKHOUSE_PORT', 3306)),
    database=os.environ.get('CLICKHOUSE_DATABASE', 'test'),
    username=os.environ.get('CLICKHOUSE_USER', 'root'),
    password=os.environ.get('CLICKHOUSE_PASSWORD', ''),
)
User.configure(config, ClickHouseBackend)
```

## Test Fixtures

```python
import pytest
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend, ClickHouseConnectionConfig


@pytest.fixture
def clickhouse_config():
    return ClickHouseConnectionConfig(
        host='localhost',
        port=3306,
        database='test',
        username='root',
        password='password',
    )


@pytest.fixture
def clickhouse_backend(clickhouse_config):
    backend = ClickHouseBackend(connection_config=clickhouse_config)
    backend.connect()
    yield backend
    backend.disconnect()


def test_connection(clickhouse_backend):
    version = clickhouse_backend.get_server_version()
    assert version is not None
```

💡 *AI Prompt:* "What is the difference between unit tests, integration tests, and end-to-end tests?"
