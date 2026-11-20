# tests/rhosocial/activerecord_clickhouse_test/feature/backend/core/test_get_type_adapters.py
"""DB-free tests for the ClickHouse backend's type adapter inventory.

No ClickHouse server is contacted: the inventory is built from the adapter
registry the backend fills in ``__init__``, so a bare, unconnected instance is
enough to exercise it.
"""

from typing import Tuple

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.adapters import (
    ClickHouseArrayAdapter,
)
from rhosocial.activerecord.backend.impl.clickhouse.backend.backend import (
    ClickHouseBackend,
)
from rhosocial.activerecord.backend.impl.clickhouse.config import (
    ClickHouseConnectionConfig,
)
from rhosocial.activerecord.backend.type_adapter import (
    SQLTypeAdapter,
    TypeAdapterCatalogProtocol,
)


def _class_key(adapter: SQLTypeAdapter) -> Tuple[str, str]:
    """Identify an adapter by class, not by instance."""
    adapter_cls = type(adapter)
    return (adapter_cls.__module__, adapter_cls.__qualname__)


@pytest.fixture
def backend() -> ClickHouseBackend:
    """An unconnected backend; the inventory needs no server."""
    return ClickHouseBackend(
        connection_config=ClickHouseConnectionConfig(host="127.0.0.1", port=8123)
    )


def test_backend_implements_the_catalog_protocol(backend):
    assert isinstance(backend, TypeAdapterCatalogProtocol)


def test_inventory_is_a_non_empty_list_of_adapters(backend):
    adapters = backend.get_type_adapters()

    assert isinstance(adapters, list)
    assert adapters, "ClickHouse registers adapters, so the inventory is not empty"
    assert all(isinstance(adapter, SQLTypeAdapter) for adapter in adapters)


def test_inventory_is_unique_by_adapter_class(backend):
    keys = [_class_key(adapter) for adapter in backend.get_type_adapters()]

    assert len(keys) == len(set(keys)), "an adapter class must appear only once"
    assert keys == sorted(keys), "the inventory is sorted by (module, qualname)"


def test_inventory_order_is_deterministic_and_fresh(backend):
    first = backend.get_type_adapters()
    second = backend.get_type_adapters()

    assert first is not second, "every call must return a new list"
    assert [_class_key(adapter) for adapter in second] == [
        _class_key(adapter) for adapter in first
    ]

    first.append(object())  # must not leak into the backend's state
    assert [_class_key(adapter) for adapter in backend.get_type_adapters()] == [
        _class_key(adapter) for adapter in second
    ]


def test_inventory_includes_the_array_adapter(backend):
    """The array adapter is registered, and also named by the suggestion table."""
    adapters = backend.get_type_adapters()

    assert any(isinstance(adapter, ClickHouseArrayAdapter) for adapter in adapters)


def test_default_adapter_suggestions_is_unchanged(backend):
    assert callable(backend.get_default_adapter_suggestions)
    assert backend.get_default_adapter_suggestions()
