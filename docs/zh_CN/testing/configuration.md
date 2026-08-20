# 测试配置

## 概述

本节介绍如何配置 ClickHouse 后端的测试环境。

## 使用 Dummy 后端进行单元测试

推荐使用 `dummy` 后端进行单元测试，它不需要实际的数据库连接：

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


# 配置 Dummy 后端
config = DummyConnectionConfig()
User.configure(config, DummyBackend)
```

## 使用 SQLite 后端进行集成测试

对于需要真实数据库行为的测试，可以使用 SQLite 后端：

```python
from rhosocial.activerecord.backend.impl.sqlite import SQLiteBackend, SQLiteConnectionConfig


class User(ActiveRecord):
    name: str
    email: str
    
    c: ClassVar[FieldProxy] = FieldProxy()
    
    @classmethod
    def table_name(cls) -> str:
        return 'users'


# 配置 SQLite 内存数据库
config = SQLiteConnectionConfig(database=':memory:')
User.configure(config, SQLiteBackend)
```

## 使用 ClickHouse 后端进行端到端测试

对于完整的 ClickHouse 行为测试，使用 ClickHouse 后端：

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


# 从环境变量读取配置
config = ClickHouseConnectionConfig(
    host=os.environ.get('CLICKHOUSE_HOST', 'localhost'),
    port=int(os.environ.get('CLICKHOUSE_PORT', 3306)),
    database=os.environ.get('CLICKHOUSE_DATABASE', 'test'),
    username=os.environ.get('CLICKHOUSE_USER', 'root'),
    password=os.environ.get('CLICKHOUSE_PASSWORD', ''),
)
User.configure(config, ClickHouseBackend)
```

## 测试夹具 (Fixtures)

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

💡 *AI 提示词：* "单元测试、集成测试和端到端测试有什么区别？"
