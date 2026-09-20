# src/rhosocial/activerecord/backend/impl/clickhouse/expression/maintenance.py
"""ClickHouse table maintenance statement expressions.

ClickHouse supports table maintenance statements that operate at the whole-table
level (as opposed to the partition-level variants in ``partition.py``):

    ANALYZE TABLE [NO_WRITE_TO_BINLOG | LOCAL] table [, table ...]
    CHECK TABLE table [, table ...] [FOR UPGRADE] [QUICK] [FAST] [MEDIUM] [EXTENDED] [CHANGED]
    CHECKSUM TABLE table [, table ...] [QUICK | EXTENDED]
    OPTIMIZE TABLE [NO_WRITE_TO_BINLOG | LOCAL] table [, table ...]
    REPAIR TABLE [NO_WRITE_TO_BINLOG | LOCAL] table [, table ...] [QUICK] [EXTENDED] [USE_FRM]
"""

from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class NoWriteToBinlogOption(Enum):
    """NO_WRITE_TO_BINLOG / LOCAL synonym selector."""

    NONE = ""
    NO_WRITE_TO_BINLOG = "NO_WRITE_TO_BINLOG"
    LOCAL = "LOCAL"


class CheckTableOption(Enum):
    """CHECK TABLE optional modes."""

    FOR_UPGRADE = "FOR UPGRADE"
    QUICK = "QUICK"
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    EXTENDED = "EXTENDED"
    CHANGED = "CHANGED"


class ChecksumTableOption(Enum):
    """CHECKSUM TABLE optional modes."""

    QUICK = "QUICK"
    EXTENDED = "EXTENDED"


class RepairTableOption(Enum):
    """REPAIR TABLE optional modes."""

    QUICK = "QUICK"
    EXTENDED = "EXTENDED"
    USE_FRM = "USE_FRM"


class ClickHouseTableMaintenanceExpression(BaseExpression):
    """Base class for whole-table maintenance statements.

    Attributes:
        operation: Statement keyword (ANALYZE / CHECK / CHECKSUM / OPTIMIZE / REPAIR).
        tables: List of table names (may be schema-qualified tuples).
        no_write_to_binlog: NO_WRITE_TO_BINLOG / LOCAL selector (where supported).
    """

    operation: str = ""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        tables: List[Any],
        *,
        no_write_to_binlog: "NoWriteToBinlogOption" = NoWriteToBinlogOption.NONE,
    ):
        super().__init__(dialect)
        self.tables: List[Any] = list(tables)
        self.no_write_to_binlog: NoWriteToBinlogOption = no_write_to_binlog

    def validate(self, strict: bool = True) -> None:
        """Validate table list.

        Raises:
            ValueError: If the table list is empty or malformed.
        """
        if not strict:
            return
        if not self.tables:
            raise ValueError(f"{self.operation} TABLE requires at least one table")
        for table in self.tables:
            if isinstance(table, tuple):
                if len(table) != 2 or not all(isinstance(part, str) for part in table):
                    raise ValueError(f"Invalid schema-qualified table: {table!r}")
            elif not isinstance(table, str):
                raise TypeError(f"table must be str or (schema, table) tuple, got {type(table)}")

    @property
    def format_method(self) -> str:
        return "format_table_maintenance_statement"


class ClickHouseAnalyzeTableExpression(ClickHouseTableMaintenanceExpression):
    """Represent ``ANALYZE TABLE``."""

    operation: str = "ANALYZE"


class ClickHouseCheckTableExpression(ClickHouseTableMaintenanceExpression):
    """Represent ``CHECK TABLE`` with optional modes."""

    operation: str = "CHECK"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        tables: List[Any],
        *,
        options: Optional[List[CheckTableOption]] = None,
    ):
        super().__init__(
            dialect,
            tables,
            no_write_to_binlog=NoWriteToBinlogOption.NONE,
        )
        self.options: List[CheckTableOption] = list(options or [])


class ClickHouseChecksumTableExpression(ClickHouseTableMaintenanceExpression):
    """Represent ``CHECKSUM TABLE`` with optional mode."""

    operation: str = "CHECKSUM"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        tables: List[Any],
        *,
        option: Optional[ChecksumTableOption] = None,
    ):
        super().__init__(
            dialect,
            tables,
            no_write_to_binlog=NoWriteToBinlogOption.NONE,
        )
        self.option: Optional[ChecksumTableOption] = option


class ClickHouseOptimizeTableExpression(ClickHouseTableMaintenanceExpression):
    """Represent ``OPTIMIZE TABLE``."""

    operation: str = "OPTIMIZE"


class ClickHouseRepairTableExpression(ClickHouseTableMaintenanceExpression):
    """Represent ``REPAIR TABLE`` with optional modes."""

    operation: str = "REPAIR"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        tables: List[Any],
        *,
        no_write_to_binlog: "NoWriteToBinlogOption" = NoWriteToBinlogOption.NONE,
        options: Optional[List[RepairTableOption]] = None,
    ):
        super().__init__(
            dialect,
            tables,
            no_write_to_binlog=no_write_to_binlog,
        )
        self.options: List[RepairTableOption] = list(options or [])