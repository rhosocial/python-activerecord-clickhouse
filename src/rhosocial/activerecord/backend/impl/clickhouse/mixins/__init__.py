# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/__init__.py
from .introspection import ClickHouseIntrospectionMixin
from .transaction import ClickHouseTransactionMixin
from .backend_mixin import ClickHouseBackendMixin
from .trigger import ClickHouseTriggerMixin
from .partition import ClickHousePartitionMixin
from .ddl_table import ClickHouseTableMixin
from .set_type import ClickHouseSetTypeMixin
from .json import ClickHouseJSONFunctionMixin
from .spatial import ClickHouseSpatialMixin
from .vector import ClickHouseVectorMixin
from .dml import ClickHouseDMLOperationMixin
from .fulltext import ClickHouseFullTextSearchMixin
from .locking import ClickHouseLockingMixin
from .column import ClickHouseModifyColumnMixin
from .concurrency import ClickHouseConcurrencyMixin, AsyncClickHouseConcurrencyMixin
from .json_duality_view import ClickHouseJsonDualityViewMixin
from .optimizer_hint import ClickHouseOptimizerHintMixin
from .types import ClickHouseTypeSupportMixin
from .ddl_rename_table import ClickHouseRenameTableMixin
from .truncate import ClickHouseTruncateMixin
from .ddl_table_statement import ClickHouseTableStatementMixin
from .maintenance import ClickHouseMaintenanceMixin
from .routine import ClickHouseRoutineMixin
from .load_xml import ClickHouseLoadXMLLMixin
from .admin import ClickHouseAdminCommandMixin
from .ddl_table_engine import (
    ClickHouseTableEngineMixin,
    ClickHouseQueryClauseMixin,
    ClickHouseTableEngineSupport,
)
# New feature-specific mixins
from .datetime import ClickHouseDateTimeMixin
from .collation import ClickHouseCollationMixin
from .cte import ClickHouseCTEMixin
from .auto_increment import ClickHouseAutoIncrementMixin
from .window import ClickHouseWindowMixin
from .grouping import ClickHouseGroupingMixin
from .array import ClickHouseArrayMixin
from .explain import ClickHouseExplainMixin
from .temporal import ClickHouseTemporalMixin
from .upsert import ClickHouseUpsertMixin
from .join import ClickHouseJoinMixin
from .set_operation import ClickHouseSetOperationMixin
from .dql import ClickHouseDQLMixin
from .view import ClickHouseViewMixin
from .schema import ClickHouseSchemaMixin
from .index import ClickHouseIndexMixin
from .sequence import ClickHouseSequenceMixin
from .constraint import ClickHouseConstraintMixin
from .ddl_column import ClickHouseDDLColumnMixin
from .function import ClickHouseFunctionMixin

__all__ = [
    "ClickHouseIntrospectionMixin",
    "ClickHouseTransactionMixin",
    "ClickHouseBackendMixin",
    "ClickHouseTriggerMixin",
    "ClickHousePartitionMixin",
    "ClickHouseTableMixin",
    "ClickHouseSetTypeMixin",
    "ClickHouseJSONFunctionMixin",
    "ClickHouseSpatialMixin",
    "ClickHouseVectorMixin",
    "ClickHouseDMLOperationMixin",
    "ClickHouseFullTextSearchMixin",
    "ClickHouseLockingMixin",
    "ClickHouseModifyColumnMixin",
    "ClickHouseConcurrencyMixin",
    "AsyncClickHouseConcurrencyMixin",
    "ClickHouseJsonDualityViewMixin",
    "ClickHouseOptimizerHintMixin",
    "ClickHouseTypeSupportMixin",
    "ClickHouseRenameTableMixin",
    "ClickHouseTruncateMixin",
    "ClickHouseTableStatementMixin",
    "ClickHouseMaintenanceMixin",
    "ClickHouseRoutineMixin",
    "ClickHouseLoadXMLLMixin",
    "ClickHouseAdminCommandMixin",
    "ClickHouseTableEngineMixin",
    "ClickHouseQueryClauseMixin",
    "ClickHouseTableEngineSupport",
    # New feature-specific mixins
    "ClickHouseDateTimeMixin",
    "ClickHouseCollationMixin",
    "ClickHouseCTEMixin",
    "ClickHouseAutoIncrementMixin",
    "ClickHouseWindowMixin",
    "ClickHouseGroupingMixin",
    "ClickHouseArrayMixin",
    "ClickHouseExplainMixin",
    "ClickHouseTemporalMixin",
    "ClickHouseUpsertMixin",
    "ClickHouseJoinMixin",
    "ClickHouseSetOperationMixin",
    "ClickHouseDQLMixin",
    "ClickHouseViewMixin",
    "ClickHouseSchemaMixin",
    "ClickHouseIndexMixin",
    "ClickHouseSequenceMixin",
    "ClickHouseConstraintMixin",
    "ClickHouseDDLColumnMixin",
    "ClickHouseFunctionMixin",
]
