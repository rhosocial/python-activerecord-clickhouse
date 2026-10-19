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


class NoWriteToBinlogOption(str, Enum):
    """NO_WRITE_TO_BINLOG / LOCAL synonym selector.

    A ``str`` enum whose ``__str__`` is ``str.__str__``: a member *is* the word
    it carries, so an artifact names the option as a plain JSON string and the
    constructors below normalise the word back to the member. ``Enum.__str__``
    would otherwise win and spell members as ``NoWriteToBinlogOption.LOCAL`` --
    the spelling the XML channel writes, and no reader accepts it.
    """

    __str__ = str.__str__

    NONE = ""
    NO_WRITE_TO_BINLOG = "NO_WRITE_TO_BINLOG"
    LOCAL = "LOCAL"


class CheckTableOption(str, Enum):
    """CHECK TABLE optional modes. A ``str`` enum -- see :class:`NoWriteToBinlogOption`."""

    __str__ = str.__str__

    FOR_UPGRADE = "FOR UPGRADE"
    QUICK = "QUICK"
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    EXTENDED = "EXTENDED"
    CHANGED = "CHANGED"


class ChecksumTableOption(str, Enum):
    """CHECKSUM TABLE optional modes. A ``str`` enum -- see :class:`NoWriteToBinlogOption`."""

    __str__ = str.__str__

    QUICK = "QUICK"
    EXTENDED = "EXTENDED"


class RepairTableOption(str, Enum):
    """REPAIR TABLE optional modes. A ``str`` enum -- see :class:`NoWriteToBinlogOption`."""

    __str__ = str.__str__

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
        # Normalise: the artifact carries the word, and the restored instance
        # must hold the member the original held, not the bare string.
        self.no_write_to_binlog: NoWriteToBinlogOption = NoWriteToBinlogOption(
            no_write_to_binlog
        )
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
        self.options: list[CheckTableOption] = [
            CheckTableOption(o) for o in (options or [])
        ]


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
        self.option: Optional[ChecksumTableOption] = (
            ChecksumTableOption(option) if option is not None else None
        )


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
        self.options: list[RepairTableOption] = [
            RepairTableOption(o) for o in (options or [])
        ]
