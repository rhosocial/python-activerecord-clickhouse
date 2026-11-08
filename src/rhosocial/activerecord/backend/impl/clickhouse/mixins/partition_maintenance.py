# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/partition_maintenance.py
"""Backend-level entry point for ClickHouse partition maintenance.

The maintenance layer is deliberately not part of ``PartitionSupport`` (that
protocol answers capability questions and renders ``PARTITION BY`` clauses, not
lifecycle), and it is not part of ``ClickHousePartitionMixin`` either: that
mixin belongs to the dialect, while maintenance executes statements against a
connection. It therefore lives in ``partition_maintenance.py`` beside the
backend and is reachable through the single property this mixin adds.

The service is built on first access and holds only a reference to the backend;
it opens no connection at construction time.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..partition_maintenance import ClickHousePartitionMaintenance


class ClickHousePartitionMaintenanceMixin:
    """Expose ``backend.partition_maintenance``.

    Example:
        >>> service = backend.partition_maintenance
        >>> service.drop("visits", "202601")
    """

    @property
    def partition_maintenance(self) -> "ClickHousePartitionMaintenance":
        """The lazily built partition-maintenance service for this backend."""
        instance = getattr(self, "_partition_maintenance_instance", None)
        if instance is None:
            from ..partition_maintenance import ClickHousePartitionMaintenance

            instance = ClickHousePartitionMaintenance(self)
            self._partition_maintenance_instance = instance
        return instance
