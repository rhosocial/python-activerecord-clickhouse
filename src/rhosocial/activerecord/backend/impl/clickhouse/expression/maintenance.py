# src/rhosocial/activerecord/backend/impl/clickhouse/expression/maintenance.py
"""ClickHouse table maintenance statement expressions.

ClickHouse supports table maintenance statements that operate at the whole-table
level (as opposed to the partition-level variants in ``partition.py``):

    ANALYZE TABLE [NO_WRITE_TO_BINLOG | LOCAL] table [, table ...]
    CHECK TABLE table [, table ...] [FOR UPGRADE] [QUICK] [FAST] [MEDIUM] [EXTENDED] [CHANGED]
    CHECKSUM TABLE table [, table ...] [QUICK | EXTENDED]
    OPTIMIZE TABLE [NO_WRITE_TO_BINLOG | LOCAL] table [, table ...]
    REPAIR TABLE [NO_WRITE_TO_BINLOG | LOCAL] table [, table ...] [QUICK] [EXTENDED] [USE_FRM]

Each ``table`` is a schema object carrying its own ``catalog_name``; a bare
string is refused because it cannot say which database it names.
"""

from enum import Enum
from typing import Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.objects import RelationObject, Table

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
        tables: The tables the statement acts on, each a :class:`Table` carrying
            its own ``catalog_name``. A bare string is rejected: it cannot say
            which database it lives in, and the ClickHouse database is the only
            namespace there is.
        no_write_to_binlog: NO_WRITE_TO_BINLOG / LOCAL selector (where supported).

    Raises:
        TypeError: An entry is not a relation object (see :meth:`validate`).
    """

    operation: str = ""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        tables: Sequence[Table],
        *,
        no_write_to_binlog: "NoWriteToBinlogOption" = NoWriteToBinlogOption.NONE,
    ):
        super().__init__(dialect)
        self.tables: list = list(tables)
        self.no_write_to_binlog: NoWriteToBinlogOption = no_write_to_binlog
        self.validate()

    def validate(self, strict: bool = True) -> None:
        """Validate the table list.

        Raises:
            ValueError: The table list is empty.
            TypeError: An entry is not a relation object. A ``str`` or a
                ``(database, table)`` tuple is refused: both can only be
                interpreted by guessing, and a guess that drops the database
                produces a statement aimed at the wrong table.
        """
        if not strict:
            return
        if not self.tables:
            raise ValueError(f"{self.operation} TABLE requires at least one table")
        for table in self.tables:
            if not isinstance(table, RelationObject):
                raise TypeError(
                    f"{self.operation} TABLE requires Table objects carrying their "
                    f"own catalog_name, got {type(table).__name__}"
                )

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
        tables: Sequence[Table],
        *,
        options: Optional[list[CheckTableOption]] = None,
    ):
        super().__init__(
            dialect,
            tables,
            no_write_to_binlog=NoWriteToBinlogOption.NONE,
        )
        self.options: list[CheckTableOption] = list(options or [])


class ClickHouseChecksumTableExpression(ClickHouseTableMaintenanceExpression):
    """Represent ``CHECKSUM TABLE`` with optional mode."""

    operation: str = "CHECKSUM"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        tables: Sequence[Table],
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
        tables: Sequence[Table],
        *,
        no_write_to_binlog: "NoWriteToBinlogOption" = NoWriteToBinlogOption.NONE,
        options: Optional[list[RepairTableOption]] = None,
    ):
        super().__init__(
            dialect,
            tables,
            no_write_to_binlog=no_write_to_binlog,
        )
        self.options: list[RepairTableOption] = list(options or [])
