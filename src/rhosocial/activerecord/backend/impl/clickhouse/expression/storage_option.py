# src/rhosocial/activerecord/backend/impl/clickhouse/expression/storage_option.py
"""ClickHouse table storage clauses as expression nodes.

``CREATE TABLE`` in ClickHouse ends with a run of storage clauses:

    ENGINE = MergeTree PARTITION BY toYYYYMM(ts) ORDER BY (ts, id)
    TTL ts + INTERVAL 90 DAY DELETE SETTINGS index_granularity = 8192

The generic ``StorageOptionsExpression`` models this with a ``Dict[str, Any]``
bag, which cannot express the clauses' types, their canonical order, or their
own spellings. This module gives each clause its own node:

* :class:`ClickHouseTableStorageOption` -- one clause, an ``option`` member
  plus a ``value`` whose shape the enum member decides.
* :class:`ClickHouseEngineSpec` -- an engine name and its parameters, the
  value of ``ENGINE`` (``ReplacingMergeTree(version)``).
* :class:`ClickHouseSetting` -- one ``name = value`` pair, an item of
  ``SETTINGS``.

Every node declares its own formatting entry (``format_clickhouse_*``) and
therefore its own kind, so none of them collides with a core kind the way
``ClickHouseColumnDefinition`` does. ``ClickHouse`` is declared as a reserved
word in the package ``__init__``, so the derived kinds keep it whole.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Sequence, Tuple, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "CLICKHOUSE_STORAGE_CLAUSE_ORDER",
    "ClickHouseEngineSpec",
    "ClickHouseSetting",
    "ClickHouseStorageOptionKind",
    "ClickHouseTableStorageOption",
]


class ClickHouseStorageOptionKind(str, Enum):
    """The storage clauses ClickHouse accepts after the column list.

    The members are ordered as ClickHouse's grammar orders them; a renderer
    emits them in this order regardless of the order the caller supplied.
    """

    ENGINE = "ENGINE"
    PRIMARY_KEY = "PRIMARY KEY"
    PARTITION_BY = "PARTITION BY"
    ORDER_BY = "ORDER BY"
    SAMPLE_BY = "SAMPLE BY"
    TTL = "TTL"
    SETTINGS = "SETTINGS"

    @property
    def keyword(self) -> str:
        """The SQL keyword(s) this member renders as."""
        return self.value

    @property
    def rank(self) -> int:
        """Position in the canonical clause order."""
        return CLICKHOUSE_STORAGE_CLAUSE_ORDER.index(self)

    #: ``enum.StrEnum`` is 3.11+, and this project supports 3.10. Without this
    #: line ``str(member)`` is ``"ClickHouseStorageOptionKind.ENGINE"``, which
    #: is what the artifact would then carry -- a Python class name crossing
    #: the wire. With it the wire says ``"ENGINE"``, the SQL keyword itself.
    __str__ = str.__str__


#: ClickHouse's clause order. Derived from the member declaration order so the
#: two cannot drift apart.
CLICKHOUSE_STORAGE_CLAUSE_ORDER: Tuple[ClickHouseStorageOptionKind, ...] = tuple(
    ClickHouseStorageOptionKind
)


class ClickHouseEngineSpec(BaseExpression):
    """A ClickHouse table engine and its parameters.

    ``ENGINE = MergeTree`` has no parameters; ``ReplacingMergeTree(version)``
    and ``Distributed('cluster', 'db', 'table', rand())`` do. The name is the
    fixed engine vocabulary, so it is emitted verbatim; each parameter is an
    expression node, never a raw fragment.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        engine: str,
        *,
        parameters: Sequence[BaseExpression] = (),
    ):
        super().__init__(dialect)
        if not isinstance(engine, str) or not engine:
            raise TypeError(f"engine must be a non-empty string, got {type(engine).__name__}")
        for parameter in parameters:
            if not isinstance(parameter, BaseExpression):
                raise TypeError(
                    f"parameters must be expression nodes, " f"got {type(parameter).__name__}"
                )
        self.engine = engine
        self.parameters = tuple(parameters)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_engine_spec"


class ClickHouseSetting(BaseExpression):
    """One ``name = value`` item of a ``SETTINGS`` clause.

    The value is a language-neutral scalar or an expression node. It is not a
    raw string: what the caller wrote is not what gets emitted, the literal
    formatter decides that.
    """

    def __init__(self, dialect: "SQLDialectBase", name: str, value: Any):
        super().__init__(dialect)
        if not isinstance(name, str) or not name:
            raise TypeError(f"name must be a non-empty string, got {type(name).__name__}")
        if not isinstance(value, (str, int, float, bool, BaseExpression)):
            raise TypeError(
                f"value must be a scalar or an expression node, " f"got {type(value).__name__}"
            )
        self.name = name
        self.value = value

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_setting"


class ClickHouseTableStorageOption(BaseExpression):
    """One storage clause of a ClickHouse ``CREATE TABLE``.

    The node is singular on purpose: each clause has its own payload shape, so
    one node carrying the whole run would have to degrade ``value`` to
    ``Any``. A caller declares a sequence of these; the renderer orders them
    by :attr:`ClickHouseStorageOptionKind.rank` and refuses a repeated clause.

    ``value`` is validated against ``option`` here, at construction, and
    nowhere else:

    ==================  =============================================
    ``option``          accepted ``value``
    ==================  =============================================
    ``ENGINE``          :class:`ClickHouseEngineSpec`
    ``PRIMARY_KEY``     sequence of expression nodes
    ``PARTITION_BY``    sequence of expression nodes
    ``ORDER_BY``        sequence of expression nodes
    ``SAMPLE_BY``       expression node
    ``TTL``             expression node
    ``SETTINGS``        sequence of :class:`ClickHouseSetting`
    ==================  =============================================
    """

    #: Members whose payload is a list of expressions.
    LIST_MEMBERS = frozenset(
        {
            ClickHouseStorageOptionKind.PRIMARY_KEY,
            ClickHouseStorageOptionKind.PARTITION_BY,
            ClickHouseStorageOptionKind.ORDER_BY,
        }
    )

    #: Members whose payload is a single expression.
    EXPRESSION_MEMBERS = frozenset(
        {
            ClickHouseStorageOptionKind.SAMPLE_BY,
            ClickHouseStorageOptionKind.TTL,
        }
    )

    def __init__(
        self,
        dialect: "SQLDialectBase",
        option: Union[ClickHouseStorageOptionKind, str],
        *,
        value: Any,
    ):
        super().__init__(dialect)
        # A str-enum is a str on the wire: the artifact carries ``"ENGINE"``,
        # never the member object, so the constructor has to accept the
        # spelling back. Coercing here, at the single validation point, keeps
        # the node reconstructible instead of making every reader special-case
        # it. An unknown spelling raises the enum's own ``ValueError``.
        if not isinstance(option, ClickHouseStorageOptionKind):
            if isinstance(option, str):
                option = ClickHouseStorageOptionKind(option)
            else:
                raise TypeError(
                    f"option must be a ClickHouseStorageOptionKind or its "
                    f"spelling, got {type(option).__name__}"
                )
        self.option = option
        self.value = self._checked_value(option, value)

    @staticmethod
    def _checked_value(option: ClickHouseStorageOptionKind, value: Any) -> Any:
        """Validate ``value`` against ``option`` and return it normalised."""
        if option is ClickHouseStorageOptionKind.ENGINE:
            if not isinstance(value, ClickHouseEngineSpec):
                raise TypeError(
                    f"ENGINE takes a ClickHouseEngineSpec, " f"got {type(value).__name__}"
                )
            return value

        if option in ClickHouseTableStorageOption.EXPRESSION_MEMBERS:
            if not isinstance(value, BaseExpression):
                raise TypeError(
                    f"{option.keyword} takes an expression node, " f"got {type(value).__name__}"
                )
            return value

        if option is ClickHouseStorageOptionKind.SETTINGS:
            items = tuple(value)
            if not items:
                raise ValueError("SETTINGS takes at least one ClickHouseSetting")
            for item in items:
                if not isinstance(item, ClickHouseSetting):
                    raise TypeError(
                        f"SETTINGS takes ClickHouseSetting items, " f"got {type(item).__name__}"
                    )
            return items

        items = tuple(value)
        if not items:
            raise ValueError(f"{option.keyword} takes at least one expression")
        for item in items:
            if not isinstance(item, BaseExpression):
                raise TypeError(
                    f"{option.keyword} takes expression nodes, " f"got {type(item).__name__}"
                )
        return items

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_clickhouse_table_storage_option"
