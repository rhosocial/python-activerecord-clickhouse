# src/rhosocial/activerecord/backend/impl/clickhouse/registry.py
"""The ClickHouse backend's expression registry.

ClickHouse owns the kinds its own expression package declares. It does not own
core's kinds and it does not list any other backend's: the overlap with core is
expressed by composition -- ``base=core_registry()`` -- and there is no
cross-backend merge anywhere.

The registry is built on first use, cached, and frozen. Freezing is what lets
the dialect hand the same table to every reader without one caller's
registration changing what another caller resolves.
"""

from rhosocial.activerecord.backend.expression.registry import ExpressionRegistry
from rhosocial.activerecord.backend.expression.serialization import (
    core_registry,
    registry_for_packages,
)

#: The ClickHouse backend's own expression package.
_CLICKHOUSE_EXPRESSION_PACKAGE = "rhosocial.activerecord.backend.impl.clickhouse.expression"

_backend_registry = None


def backend_registry() -> ExpressionRegistry:
    """ClickHouse's registry: core's kinds plus ClickHouse's own, frozen and cached.

    Returns:
        The frozen registry ``ClickHouseDialect.artifact_registry()`` exposes.
    """
    global _backend_registry
    if _backend_registry is None:
        # Build into a local and publish only on success: a half-populated
        # instance cached under the module global would make every later call
        # fail with a confusing "no such kind" instead of the real cause.
        _backend_registry = registry_for_packages(
            _CLICKHOUSE_EXPRESSION_PACKAGE,
            base=core_registry(),
        )
    return _backend_registry
