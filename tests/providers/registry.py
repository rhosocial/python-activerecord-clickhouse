"""
Test Provider Registry

This module registers concrete implementations of test suite interfaces.
The registry system allows the test suite to be decoupled from specific
backend implementations, enabling the same tests to run against different
database backends.

Capability Negotiation in Testing
---------------------------------
The test suite uses the capability negotiation system to determine which
tests should run against which backends. Each backend declares its capabilities
through the DatabaseCapabilities system, and tests can check for required
capabilities before execution.

This approach enables:
1. Automatic test skipping for unsupported features
2. Backend-specific test execution
3. Fine-grained feature testing
4. Single source of truth for feature support

When a test needs to check for a capability, it can access the backend's
capabilities property and use the appropriate checking methods. Tests that
require specific capabilities will automatically be skipped on backends
that don't support those features.
"""

from rhosocial.activerecord.testsuite.core.registry import ProviderRegistry
from .basic import BasicSyncProvider, BasicAsyncProvider
from .events import EventsSyncProvider, EventsAsyncProvider
from .mixins import MixinsSyncProvider, MixinsAsyncProvider
from .query import QuerySyncProvider, QueryAsyncProvider
from .relation import RelationSyncProvider, RelationAsyncProvider
from .basic_connection import BasicConnectionProvider
from .query_connection import QueryConnectionProvider
from .crud_benchmark import CrudBenchmarkProvider
from .fastapi_benchmark import FastAPIBenchmarkProvider
from .mixin_benchmark import MixinBenchmarkProvider
from .query_benchmark import QueryBenchmarkProvider
from .transaction_benchmark import TransactionBenchmarkProvider

# Importing the pooling module registers the ClickHouse-specific pool reset handler
# (a side effect of the import), mirroring SQLite's tests/providers/pooling.py.
from . import pooling  # noqa: F401

# Create a single, global instance of the ProviderRegistry.
provider_registry = ProviderRegistry()

# Register the concrete `BasicSyncProvider` and `BasicAsyncProvider` as the
# implementations for the basic feature interfaces defined in the testsuite.
# When the testsuite needs to run a "basic" feature test, it will ask the registry
# for either "feature.basic.IBasicSyncProvider" or "feature.basic.IBasicAsyncProvider"
# and will receive `BasicSyncProvider` or `BasicAsyncProvider` respectively.
provider_registry.register("feature.basic.IBasicProvider", BasicSyncProvider)
provider_registry.register("feature.basic.IBasicSyncProvider", BasicSyncProvider)
provider_registry.register("feature.basic.IBasicAsyncProvider", BasicAsyncProvider)

# Register the concrete `EventsSyncProvider` and `EventsAsyncProvider` as the
# implementations for the events feature interfaces.
provider_registry.register("feature.events.IEventsProvider", EventsSyncProvider)
provider_registry.register("feature.events.IEventsSyncProvider", EventsSyncProvider)
provider_registry.register("feature.events.IEventsAsyncProvider", EventsAsyncProvider)

# Register the concrete `MixinsSyncProvider` and `MixinsAsyncProvider` as the
# implementations for the mixins feature interfaces.
provider_registry.register("feature.mixins.IMixinsProvider", MixinsSyncProvider)
provider_registry.register("feature.mixins.IMixinsSyncProvider", MixinsSyncProvider)
provider_registry.register("feature.mixins.IMixinsAsyncProvider", MixinsAsyncProvider)

# Register the concrete `QuerySyncProvider` and `QueryAsyncProvider` as the
# implementations for the query feature interfaces.
provider_registry.register("feature.query.IQueryProvider", QuerySyncProvider)
provider_registry.register("feature.query.IQuerySyncProvider", QuerySyncProvider)
provider_registry.register("feature.query.IQueryAsyncProvider", QueryAsyncProvider)

# Register the concrete `RelationSyncProvider` and `RelationAsyncProvider` as the
# implementations for the relation feature interfaces.
provider_registry.register("feature.relation.IRelationProvider", RelationSyncProvider)
provider_registry.register("feature.relation.IRelationSyncProvider", RelationSyncProvider)
provider_registry.register("feature.relation.IRelationAsyncProvider", RelationAsyncProvider)

# Register the concrete `BasicConnectionProvider` as the implementation for the
# `feature.basic.connection.IBasicConnectionProvider` interface defined in the testsuite.
provider_registry.register("feature.basic.connection.IBasicConnectionProvider", BasicConnectionProvider)

# Register the concrete `QueryConnectionProvider` as the implementation for the
# `feature.query.connection.IQueryConnectionProvider` interface defined in the testsuite.
provider_registry.register(
    "feature.query.connection.IQueryConnectionProvider",
    QueryConnectionProvider,
)

# Register benchmark providers.
provider_registry.register("benchmark.crud.ICrudBenchmarkProvider", CrudBenchmarkProvider)
provider_registry.register("benchmark.query.IQueryBenchmarkProvider", QueryBenchmarkProvider)
provider_registry.register(
    "benchmark.transaction.ITransactionBenchmarkProvider",
    TransactionBenchmarkProvider,
)
provider_registry.register("benchmark.mixin.IMixinBenchmarkProvider", MixinBenchmarkProvider)
provider_registry.register("benchmark.fastapi.IFastAPIBenchmarkProvider", FastAPIBenchmarkProvider)
