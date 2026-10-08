# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/__init__.py
"""ClickHouse dialect-specific protocol definitions.
One module per concern, mirroring the layout of the other backends. Each
protocol covers a feature ClickHouse has and the SQL standard either does
not define or defines differently. Where a ClickHouse protocol narrows a
generic protocol it *derives* from it, so ``isinstance(dialect,
GenericSupport)`` keeps working for dialects that implement only the
ClickHouse-specific variant.

Namespace concerns (catalog / schema / qualified names) are **not** here:
ClickHouse has a database and no inner schema, so ``mixins/namespace.py``
answers the catalog switches and leaves schema qualification off.
"""

from .dml import ClickHouseDMLOperationSupport
from .trigger import ClickHouseTriggerSupport
from .table import ClickHouseTableSupport
from .partition import ClickHousePartitionSupport
from .set_type import ClickHouseSetTypeSupport
from .json import ClickHouseJSONFunctionSupport
from .spatial import ClickHouseSpatialSupport
from .vector import ClickHouseVectorSupport
from .fulltext_search import ClickHouseFullTextSearchSupport
from .locking import ClickHouseLockingSupport
from .modify_column import ClickHouseModifyColumnSupport
from .json_duality_view import ClickHouseJsonDualityViewSupport
from .optimizer_hint import ClickHouseOptimizerHintSupport
from .rename_table import ClickHouseRenameTableSupport
from .table_statement import ClickHouseTableStatementSupport
from .maintenance import ClickHouseMaintenanceSupport
from .routine import ClickHouseRoutineSupport
from .load_xml import ClickHouseLoadXMLSupport
from .admin import ClickHouseAdminCommandSupport

__all__ = [
    "ClickHouseDMLOperationSupport",
    "ClickHouseTriggerSupport",
    "ClickHouseTableSupport",
    "ClickHousePartitionSupport",
    "ClickHouseSetTypeSupport",
    "ClickHouseJSONFunctionSupport",
    "ClickHouseSpatialSupport",
    "ClickHouseVectorSupport",
    "ClickHouseFullTextSearchSupport",
    "ClickHouseLockingSupport",
    "ClickHouseModifyColumnSupport",
    "ClickHouseJsonDualityViewSupport",
    "ClickHouseOptimizerHintSupport",
    "ClickHouseRenameTableSupport",
    "ClickHouseTableStatementSupport",
    "ClickHouseMaintenanceSupport",
    "ClickHouseRoutineSupport",
    "ClickHouseLoadXMLSupport",
    "ClickHouseAdminCommandSupport",
]
