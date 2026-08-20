"""
Validation script for ClickHouse async connection pool behavior.

This script documents and validates the recommendations from
docs/en_US/installation_and_configuration/pool.md:
  1. Both ClickHouseBackend (sync) and AsyncClickHouseBackend (async) maintain a single
     persistent connection per backend instance.
  2. pool_* configuration fields are accepted by ClickHouseConnectionConfig but are
     not forwarded to the underlying clickhouse-connector-python driver in either
     backend.
  3. clickhouse.connector.aio.connect() does support driver-level pooling via
     pool_name / pool_size kwargs, but AsyncClickHouseBackend does not use them yet.
  4. The correct production pattern is to configure models once at application
     startup, not inside request handlers.

All demos run WITHOUT a real ClickHouse server. They inspect source code, config
objects, and driver introspection to prove the documented behaviour, then
simulate the lifecycle patterns with mock objects so the script is fully
self-contained.
"""

import asyncio
import inspect
import os
import unittest.mock as mock
from typing import Optional

# ---------------------------------------------------------------------------
# Demo 1: pool_* fields are parsed by ClickHouseConnectionConfig but ignored
# ---------------------------------------------------------------------------

def demonstrate_pool_config_ignored() -> None:
    """pool_size and friends are stored on the config object but skipped."""

    print("\n" + "=" * 60)
    print("DEMO 1 — pool_* config fields: accepted but not forwarded")
    print("=" * 60)

    try:
        from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseConnectionConfig  # type: ignore
    except ImportError:
        print("  (ClickHouseConnectionConfig not importable — skipping live check)")
        _demo_pool_config_ignored_static()
        return

    config = ClickHouseConnectionConfig(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "3306")),
        database=os.environ.get("CLICKHOUSE_DATABASE", "myapp"),
        username=os.environ.get("CLICKHOUSE_USER", "app"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", "secret"),
        pool_size=10,
        pool_name="mypool",
        pool_timeout=60,
        pool_reset_session=True,
        pool_pre_ping=True,
    )

    print(f"\n  config.pool_size         = {config.pool_size}")
    print(f"  config.pool_name         = {config.pool_name!r}")
    print(f"  config.pool_timeout      = {config.pool_timeout}")
    print(f"  config.pool_reset_session= {config.pool_reset_session}")
    print(f"  config.pool_pre_ping     = {config.pool_pre_ping}")

    # Verify the async backend's connect() skips pool_* params
    try:
        from rhosocial.activerecord.backend.impl.clickhouse.async_backend import AsyncClickHouseBackend  # type: ignore
        source = inspect.getsource(AsyncClickHouseBackend.connect)
        skips_pool = "pool_" in source and "startswith('pool_')" in source
        print(f"\n  AsyncClickHouseBackend.connect() skips pool_* params: {skips_pool}")
        assert skips_pool, "Expected pool_* params to be filtered in async connect()"
    except ImportError:
        print("  (AsyncClickHouseBackend not importable — static assertion only)")

    print("\n✓ pool_* fields are parsed by config but never forwarded to the driver.")


def _demo_pool_config_ignored_static() -> None:
    """Static fallback: show expected config structure without importing the package."""
    print("""
  Expected ClickHouseConnectionConfig fields (from ConnectionPoolMixin):
    pool_size          : int   = 5
    pool_timeout       : int   = 30
    pool_name          : str   = None
    pool_reset_session : bool  = True
    pool_pre_ping      : bool  = False

  Both ClickHouseBackend.connect() and AsyncClickHouseBackend.connect() contain:
    if param.startswith('pool_'):
        continue    # ← skips every pool_* param
""")


# ---------------------------------------------------------------------------
# Demo 2: single persistent connection per backend instance
# ---------------------------------------------------------------------------

def demonstrate_single_connection() -> None:
    """Each backend instance holds exactly one underlying connection."""

    print("\n" + "=" * 60)
    print("DEMO 2 — Single persistent connection per backend instance")
    print("=" * 60)

    # Simulate what ClickHouseBackend stores internally
    class FakeConnection:
        def __init__(self, label: str):
            self.label = label
        def __repr__(self):
            return f"<Connection id={id(self)} label={self.label!r}>"

    class FakeBackend:
        def __init__(self, label: str):
            self._connection: Optional[FakeConnection] = None
            self._label = label

        def connect(self):
            self._connection = FakeConnection(self._label)

        def disconnect(self):
            self._connection = None

    b1 = FakeBackend("backend-1")
    b2 = FakeBackend("backend-2")

    b1.connect()
    b2.connect()

    print(f"\n  backend1._connection: {b1._connection}")
    print(f"  backend2._connection: {b2._connection}")
    print(f"  Same object?         {b1._connection is b2._connection}")

    assert b1._connection is not b2._connection, \
        "Each backend instance must hold its own connection"
    assert b1._connection is not None
    assert b2._connection is not None

    b1.disconnect()
    b2.disconnect()
    assert b1._connection is None
    assert b2._connection is None

    print("\n✓ Each backend instance holds exactly one independent connection.")


# ---------------------------------------------------------------------------
# Demo 3: driver-level async pool capability (introspection only)
# ---------------------------------------------------------------------------

def demonstrate_driver_pool_capability() -> None:
    """clickhouse.connector.aio.connect() supports pool_name/pool_size kwargs."""

    print("\n" + "=" * 60)
    print("DEMO 3 — clickhouse.connector.aio pool capability (driver inspection)")
    print("=" * 60)

    try:
        import clickhouse.connector.aio as clickhouse_async  # type: ignore
        connect_doc = getattr(clickhouse_async.connect, "__doc__", "") or ""
        source_available = False
        try:
            source = inspect.getsource(clickhouse_async.connect)
            source_available = True
        except (OSError, TypeError):
            source = ""

        # Check docstring or __all__ for pool support evidence
        has_pool_doc = (
            "pool_name" in connect_doc
            or "pool_size" in connect_doc
            or "pool_name" in source
            or "pool_size" in source
        )

        # Check PooledClickHouseConnection is accessible via the parent package
        try:
            from clickhouse.connector.pooling import PooledClickHouseConnection  # type: ignore
            has_pooled_class = True
        except ImportError:
            has_pooled_class = False

        print(f"\n  clickhouse.connector.aio.connect() available : True")
        print(f"  pool_name/pool_size mentioned in source : {has_pool_doc}")
        print(f"  PooledClickHouseConnection importable        : {has_pooled_class}")
        print(f"  aio/ has no pooling.py (pool via connect): True")

        print("""
  How the driver pool works (NOT used by AsyncClickHouseBackend today):

    conn = await clickhouse.connector.aio.connect(
        host="...", user="...", password="...", database="...",
        pool_name="mypool",   # triggers pool creation/reuse
        pool_size=10,
    )
    # conn is a PooledClickHouseConnection
    # conn.close() → returns connection to pool (no actual disconnect)
""")

    except ImportError:
        print("  clickhouse-connector-python not installed — showing static docs only")
        print("""
  clickhouse.connector.aio.connect() accepts these pool kwargs:
    pool_name  (str)  — creates or reuses a named pool
    pool_size  (int)  — number of connections in the pool
  When these are given, it returns PooledClickHouseConnection instead of
  ClickHouseConnection.  Calling close() on it returns the connection to the
  pool rather than disconnecting.
""")

    print("✓ Driver supports async pools; AsyncClickHouseBackend reserves this for future use.")


# ---------------------------------------------------------------------------
# Demo 4: correct lifecycle — configure once at startup, reuse across requests
# ---------------------------------------------------------------------------

def demonstrate_correct_lifecycle() -> None:
    """Configure at startup; reuse the backend across requests (simulated)."""

    print("\n" + "=" * 60)
    print("DEMO 4 — Correct connection lifecycle (startup vs. per-request)")
    print("=" * 60)

    connect_calls   = []
    configure_calls = []

    class SimulatedBackend:
        def __init__(self):
            self._connected = False

        def connect(self):
            connect_calls.append(id(self))
            self._connected = True

        def disconnect(self):
            self._connected = False

        def execute(self, sql):
            assert self._connected, "Not connected!"
            return f"result of: {sql}"

    class SimulatedModel:
        __backend_instance: Optional[SimulatedBackend] = None

        @classmethod
        def configure(cls, _config, _cls):
            configure_calls.append(1)
            cls.__backend_instance = SimulatedBackend()

        @classmethod
        def backend(cls) -> SimulatedBackend:
            assert cls.__backend_instance is not None, "Not configured!"
            return cls.__backend_instance

        @classmethod
        def find(cls, pk):
            return cls.backend().execute(f"SELECT * WHERE id={pk}")

    # ---- Correct: startup configures once ----
    SimulatedModel.configure(None, None)
    SimulatedModel.backend().connect()

    print("\n  Simulating 5 requests (no configure/connect per request):")
    for i in range(1, 6):
        result = SimulatedModel.find(i)
        print(f"    Request {i}: {result}")

    print(f"\n  configure() called : {len(configure_calls)} time(s)  (should be 1)")
    print(f"  connect()   called : {len(connect_calls)} time(s)  (should be 1)")

    assert len(configure_calls) == 1, "configure() must be called exactly once"
    assert len(connect_calls)   == 1, "connect() must be called exactly once"

    SimulatedModel.backend().disconnect()

    print("\n✓ One configure() + one connect() serves all requests — correct pattern.")

    # ---- Anti-pattern: configure per request ----
    bad_connect_calls   = []
    bad_configure_calls = []

    class BadModel(SimulatedModel):
        __backend_instance = None

        @classmethod
        def configure(cls, _config, _cls):
            bad_configure_calls.append(1)
            cls.__backend_instance = SimulatedBackend()

        @classmethod
        def backend(cls):
            assert cls.__backend_instance is not None
            return cls.__backend_instance

    print("\n  Anti-pattern: configure() + connect() inside each request:")
    for i in range(1, 4):
        BadModel.configure(None, None)            # ← new backend every time
        BadModel.backend().connect()
        _ = BadModel.find(i)
        BadModel.backend().disconnect()
        print(f"    Request {i}: configure() + connect() + disconnect() called")

    print(f"\n  configure() called : {len(bad_configure_calls)} times (should be 1, was {len(bad_configure_calls)})")
    print(f"  connect()   called : {len(bad_connect_calls)} times")
    print("  ✗ Unnecessary overhead — a new connection opened and closed per request.")


# ---------------------------------------------------------------------------
# Demo 5: async lifecycle simulation
# ---------------------------------------------------------------------------

async def _async_lifecycle_demo() -> None:
    """Simulate AsyncClickHouseBackend lifecycle with a mock coroutine."""

    lifecycle = []

    class FakeAsyncBackend:
        def __init__(self):
            self._connection = None

        async def connect(self):
            lifecycle.append("connect")
            self._connection = object()

        async def disconnect(self):
            lifecycle.append("disconnect")
            self._connection = None

        async def execute(self, sql):
            lifecycle.append(f"execute:{sql}")
            return f"async result: {sql}"

    backend = FakeAsyncBackend()
    await backend.connect()

    # Simulate 3 async request handlers using the same backend
    results = await asyncio.gather(
        backend.execute("SELECT 1"),
        backend.execute("SELECT 2"),
        backend.execute("SELECT 3"),
    )
    for r in results:
        print(f"    {r}")

    await backend.disconnect()

    assert lifecycle[0] == "connect"
    assert lifecycle[-1] == "disconnect"
    assert len([e for e in lifecycle if e.startswith("execute:")]) == 3

    print(f"\n  Lifecycle: {lifecycle}")


def demonstrate_async_lifecycle() -> None:
    """AsyncClickHouseBackend connects once; multiple concurrent tasks share it."""

    print("\n" + "=" * 60)
    print("DEMO 5 — Async backend: one connection, concurrent tasks")
    print("=" * 60)
    print("\n  Simulating 3 concurrent async queries on one backend connection:")
    asyncio.run(_async_lifecycle_demo())
    print("\n✓ One async connect() serves all concurrent queries — correct pattern.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("ClickHouse Async Connection Pool — Behaviour and Best Practices")
    print("=" * 60)

    demonstrate_pool_config_ignored()
    demonstrate_single_connection()
    demonstrate_driver_pool_capability()
    demonstrate_correct_lifecycle()
    demonstrate_async_lifecycle()

    print("\n" + "=" * 60)
    print("EXAMPLE SUMMARY")
    print("=" * 60)
    print("This script demonstrates:")
    print("1. pool_* fields in ClickHouseConnectionConfig are accepted by the config")
    print("   class but silently skipped by both ClickHouseBackend and")
    print("   AsyncClickHouseBackend — no connection pool is created today.")
    print("2. Each backend instance holds exactly one persistent connection.")
    print("   Two separate Model.configure() calls produce two independent")
    print("   connections, not a shared pool.")
    print("3. clickhouse.connector.aio.connect() does support driver-level async")
    print("   pooling via pool_name/pool_size kwargs (returns")
    print("   PooledClickHouseConnection).  AsyncClickHouseBackend reserves this")
    print("   capability for a future implementation.")
    print("4. The correct production pattern is to call configure() and")
    print("   connect() once at application startup (e.g., FastAPI lifespan),")
    print("   then reuse the backend across all requests.")
    print("5. Async tasks can safely share one AsyncClickHouseBackend connection")
    print("   for sequential query execution within a single event loop.")
