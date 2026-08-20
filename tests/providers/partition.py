"""ClickHouse provider for shared partition testsuite scenarios."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type

from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend
from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.testsuite.feature.partition.interfaces import IPartitionProvider

from .scenarios import get_enabled_scenarios, get_scenario


class PartitionProvider(IPartitionProvider):
    """Concrete partition provider backed by real ClickHouse scenarios."""

    TABLE_NAME = "ar_testsuite_partition_events"
    PARTITIONS = {
        "p2026_01": ("p2026_01", "2026-02-01"),
        "p2026_02": ("p2026_02", "2026-03-01"),
        "p2026_03": ("p2026_03", "2026-04-01"),
    }

    def __init__(self):
        self._active_backends = []
        self._active_async_backends = []

    def get_test_scenarios(self) -> List[str]:
        """Return ClickHouse scenarios configured for real backend tests."""
        return list(get_enabled_scenarios().keys())

    def get_partition_capabilities(self, scenario_name: str) -> Dict[str, bool]:
        backend = self._ensure_backend(scenario_name)
        return self._capabilities(backend)

    async def async_get_partition_capabilities(self, scenario_name: str) -> Dict[str, bool]:
        backend = await self._ensure_async_backend(scenario_name)
        return self._capabilities(backend)

    def setup_range_partitioned_event_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], ...]:
        backend = self._ensure_backend(scenario_name)
        self._reset_partition_table(backend)
        return (self._event_model(backend),)

    async def setup_async_range_partitioned_event_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], ...]:
        backend = await self._ensure_async_backend(scenario_name)
        await self._reset_partition_table_async(backend)
        return (self._async_event_model(backend),)

    def add_future_range_partition(self, scenario_name: str) -> None:
        backend = self._ensure_backend(scenario_name)
        backend.execute(
            f"ALTER TABLE `{self.TABLE_NAME}` ADD PARTITION (PARTITION p2026_03 VALUES LESS THAN ('2026-04-01'))"
        )

    async def async_add_future_range_partition(self, scenario_name: str) -> None:
        backend = await self._ensure_async_backend(scenario_name)
        await backend.execute(
            f"ALTER TABLE `{self.TABLE_NAME}` ADD PARTITION (PARTITION p2026_03 VALUES LESS THAN ('2026-04-01'))"
        )

    def truncate_partition(self, scenario_name: str, partition_key: str) -> None:
        backend = self._ensure_backend(scenario_name)
        backend.execute(f"ALTER TABLE `{self.TABLE_NAME}` TRUNCATE PARTITION {partition_key}")

    async def async_truncate_partition(self, scenario_name: str, partition_key: str) -> None:
        backend = await self._ensure_async_backend(scenario_name)
        await backend.execute(f"ALTER TABLE `{self.TABLE_NAME}` TRUNCATE PARTITION {partition_key}")

    def detach_partition(self, scenario_name: str, partition_key: str) -> None:
        raise NotImplementedError("ClickHouse does not support DETACH PARTITION")

    async def async_detach_partition(self, scenario_name: str, partition_key: str) -> None:
        raise NotImplementedError("ClickHouse does not support DETACH PARTITION")

    def attach_partition(self, scenario_name: str, partition_key: str) -> None:
        raise NotImplementedError("ClickHouse does not support ATTACH PARTITION")

    async def async_attach_partition(self, scenario_name: str, partition_key: str) -> None:
        raise NotImplementedError("ClickHouse does not support ATTACH PARTITION")

    def get_partition_metadata(self, scenario_name: str) -> Dict[str, Any]:
        backend = self._ensure_backend(scenario_name)
        rows = backend.fetch_all(self._metadata_sql(), (self.TABLE_NAME,))
        return self._metadata_dict(rows)

    async def async_get_partition_metadata(self, scenario_name: str) -> Dict[str, Any]:
        backend = await self._ensure_async_backend(scenario_name)
        rows = await backend.fetch_all(self._metadata_sql(), (self.TABLE_NAME,))
        return self._metadata_dict(rows)

    def create_valid_unique_constraint(self, scenario_name: str) -> None:
        backend = self._ensure_backend(scenario_name)
        backend.execute(
            f"CREATE UNIQUE INDEX `{self.TABLE_NAME}_id_created_at_uq` ON `{self.TABLE_NAME}` (id, created_at)"
        )

    async def async_create_valid_unique_constraint(self, scenario_name: str) -> None:
        backend = await self._ensure_async_backend(scenario_name)
        await backend.execute(
            f"CREATE UNIQUE INDEX `{self.TABLE_NAME}_id_created_at_uq` ON `{self.TABLE_NAME}` (id, created_at)"
        )

    def create_invalid_unique_constraint(self, scenario_name: str) -> None:
        backend = self._ensure_backend(scenario_name)
        backend.execute(f"CREATE UNIQUE INDEX `{self.TABLE_NAME}_id_only_uq` ON `{self.TABLE_NAME}` (id)")

    async def async_create_invalid_unique_constraint(self, scenario_name: str) -> None:
        backend = await self._ensure_async_backend(scenario_name)
        await backend.execute(f"CREATE UNIQUE INDEX `{self.TABLE_NAME}_id_only_uq` ON `{self.TABLE_NAME}` (id)")

    def cleanup_after_test(self, scenario_name: str) -> None:
        for backend in self._active_backends:
            try:
                self._drop_partition_table(backend)
            finally:
                backend.disconnect()
        self._active_backends.clear()

    async def cleanup_after_test_async(self, scenario_name: str) -> None:
        for backend in self._active_async_backends:
            try:
                await self._drop_partition_table_async(backend)
            finally:
                await backend.disconnect()
        self._active_async_backends.clear()

    def _ensure_backend(self, scenario_name: str):
        if self._active_backends:
            return self._active_backends[0]
        backend_class, config = get_scenario(scenario_name)
        backend = backend_class(connection_config=config)
        backend.connect()
        backend.introspect_and_adapt()
        self._active_backends.append(backend)
        return backend

    async def _ensure_async_backend(self, scenario_name: str):
        if self._active_async_backends:
            return self._active_async_backends[0]
        _, config = get_scenario(scenario_name)
        backend = AsyncClickHouseBackend(connection_config=config)
        await backend.connect()
        await backend.introspect_and_adapt()
        self._active_async_backends.append(backend)
        return backend

    def _capabilities(self, backend) -> Dict[str, bool]:
        return {
            "range_partitioning": backend.dialect.supports_range_table_partitioning(),
            "range_columns_partitioning": backend.dialect.supports_range_columns_partitioning(),
            "list_partitioning": backend.dialect.supports_list_table_partitioning(),
            "hash_partitioning": backend.dialect.supports_hash_table_partitioning(),
            "key_partitioning": backend.dialect.supports_key_table_partitioning(),
            "subpartitioning": backend.dialect.supports_subpartitioning(),
            "add_partition": backend.dialect.supports_add_partition(),
            "truncate_partition": backend.dialect.supports_truncate_partition(),
            "detach_partition": backend.dialect.supports_detach_partition(),
            "attach_partition": backend.dialect.supports_attach_partition(),
            "partition_introspection": True,
            "partition_metadata": backend.dialect.supports_partition_metadata_introspection(),
            "partition_explain": backend.dialect.supports_explain_format("TEXT"),
            "partition_pruning_explain": backend.dialect.supports_explain_format("TEXT"),
            "partition_bounds": True,
            "partitioned_unique_constraint": True,
            "unique_requires_partition_key": True,
        }

    def _reset_partition_table(self, backend) -> None:
        self._drop_partition_table(backend)
        backend.execute(self._create_table_sql())

    async def _reset_partition_table_async(self, backend) -> None:
        await self._drop_partition_table_async(backend)
        await backend.execute(self._create_table_sql())

    def _drop_partition_table(self, backend) -> None:
        backend.execute(f"DROP TABLE IF EXISTS `{self.TABLE_NAME}`")

    async def _drop_partition_table_async(self, backend) -> None:
        await backend.execute(f"DROP TABLE IF EXISTS `{self.TABLE_NAME}`")

    def _create_table_sql(self) -> str:
        return f"""
        CREATE TABLE `{self.TABLE_NAME}` (
            id BIGINT NOT NULL AUTO_INCREMENT,
            created_at DATETIME NOT NULL,
            tenant_id INT NOT NULL,
            payload TEXT,
            amount DECIMAL(12, 2),
            KEY idx_created_at (created_at),
            KEY idx_id (id)
        )
        PARTITION BY RANGE COLUMNS (created_at) (
            PARTITION p2026_01 VALUES LESS THAN ('2026-02-01'),
            PARTITION p2026_02 VALUES LESS THAN ('2026-03-01')
        )
        """

    def _metadata_sql(self) -> str:
        return """
        SELECT PARTITION_NAME AS name,
               PARTITION_METHOD AS strategy,
               PARTITION_EXPRESSION AS partition_key,
               PARTITION_DESCRIPTION AS bound
        FROM information_schema.PARTITIONS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND PARTITION_NAME IS NOT NULL
        ORDER BY PARTITION_NAME
        """

    def _metadata_dict(self, rows) -> Dict[str, Any]:
        return {
            "is_partitioned": bool(rows),
            "strategy": "range",
            "key_columns": ["created_at"],
            "partitions": [{"name": row["name"], "bound": str(row["bound"])} for row in rows],
        }

    def _event_model(self, backend):
        table_name = self.TABLE_NAME

        class PartitionEvent(ActiveRecord):
            __table_name__ = table_name
            __primary_key__ = "id"
            __backend__ = backend
            c: ClassVar[FieldProxy] = FieldProxy()

            id: Optional[int] = None
            created_at: datetime
            tenant_id: int
            payload: Optional[str] = None
            amount: Optional[Decimal] = None

        return PartitionEvent

    def _async_event_model(self, backend):
        table_name = self.TABLE_NAME

        class AsyncPartitionEvent(AsyncActiveRecord):
            __table_name__ = table_name
            __primary_key__ = "id"
            __backend__ = backend
            c: ClassVar[FieldProxy] = FieldProxy()

            id: Optional[int] = None
            created_at: datetime
            tenant_id: int
            payload: Optional[str] = None
            amount: Optional[Decimal] = None

        return AsyncPartitionEvent
