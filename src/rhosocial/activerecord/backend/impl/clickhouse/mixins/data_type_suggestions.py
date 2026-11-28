# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/data_type_suggestions.py
"""ClickHouse's **suggested data types**: what a bare field is declared as here.

The DDL half of the type answer, separate from :mod:`.types` (how a ``DataType``
is rendered) and :mod:`.column_type` (what a column class can do). A field that
declares only a Python type gets one of these declarations.

Four properties of this server shape the answers:

* **nullability is part of the type, not of the column.** ClickHouse's plain
  types coerce ``NULL`` to a default instead of storing it, so an optional
  field is a ``Nullable(T)`` column. The suggestion is the inner ``T``; adding
  the wrapper is the column's decision, and a suggestion that already wrapped
  every entry would change the type of a required field.
* **text is one unbounded byte string.** ``String`` stores the bytes as given
  and has no declared width, so ``str``, ``bytes`` and ``bytearray`` all land
  on it. ``ClickHouseStringType`` is named rather than core ``TextType``
  because the column really is ClickHouse's own word — the two render the
  identical ``String``, so this is a naming choice, not a different storage.
* **arrays are native and always one dimension** (``Array(T)``). The four
  sequence entries share the container, and the element is ``String``: a bare
  annotation does not say what the elements are, so the shared default is the
  text one. A field that knows its element type declares it with ``UseSqlType``.
* **microseconds are the timestamp default.** ``ClickHouseDateTime64Type(
  precision=6)`` renders ``DateTime64(6)``; plain ``DateTime`` is whole
  seconds and ``DateTime64(3)`` keeps only milliseconds, both of which would
  silently truncate Python's microseconds. The dialect answers
  ``supports_microsecond_timestamp() == True``, so a bare ``datetime`` field
  must be backed by a type that actually keeps the six fractional digits.

The families this server cannot spell at all name a carrier rather than
``None``: ``dict`` is stored as text (the native ``JSON`` column type arrived
in 24.10 and this dialect does not check the server version for it, which is
also why ``jsonb`` is substituted by a text type in ``.types``); an
``enum.Enum`` needs a label set (``Enum8``/``Enum16`` take explicit integers and
cannot be ``NULL``, so a bare enum has nothing to render); there is no
``INTERVAL`` type, so ``datetime.timedelta`` is the adapter's text form; there
is no MAC type, so an ``AA:BB:CC:DD:EE:FF`` address spends a 17-character
``VARCHAR`` (which renders ``String`` — the width is dropped); there are no
``Range``/``Multirange`` types, so the neutral adapter's literal text
round-trips; and ``Vector`` is text because ``QBit`` needs a dimension a bare
annotation does not carry.

**Geometry is the exception, and it is native.** ``Geometry`` is a ClickHouse
``GEOMETRY`` column with no SRID and no shape parameter — the seven concrete
classes (``Point`` … ``GeometryCollection``) are the shape-specific
declarations, and ``GEOMETRY`` accepts any of them. So the suggestion answers
with ``ClickHouseGeometryType()`` rather than a text carrier.

Each call returns a **fresh dict** whose values are this module's read-only
templates; the derivation binds a dialect on a copy of the single entry it
uses, never on the template itself.
"""
from __future__ import annotations

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, Optional

from rhosocial.activerecord.backend.adapters import (
    AwareDatetime,
    BitString,
    Geometry,
    IPAddress,
    MacAddress,
    Multirange,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.suggestion.definitions import (
    DataTypeSuggestion,
    ExtraDataTypeSuggestion,
)
from rhosocial.activerecord.backend.expression.types import (
    DecimalType,
    JsonType,
    TextType,
    TimeType,
    VarCharType,
)
from ..expression.types.types import (
    ClickHouseArrayType,
    ClickHouseBoolType,
    ClickHouseDateType,
    ClickHouseDateTime64Type,
    ClickHouseFloat64Type,
    ClickHouseGeometryType,
    ClickHouseInt64Type,
    ClickHouseStringType,
    ClickHouseUUIDType,
)

#: The element every bare sequence gets: the same text type ``str`` lands on.
_ARRAY_ELEMENT = ClickHouseStringType()

#: ClickHouse's suggested declaration per framework-modelled Python type.
CLICKHOUSE_DATA_TYPE_SUGGESTIONS: Dict[Any, Optional[Any]] = {
    # -- common scalars --------------------------------------------------
    bool: ClickHouseBoolType(),
    # Python's int is unbounded; ClickHouse's widest signed integer is the
    # honest default, and it is also the storage this backend gives a
    # client-generated primary key.
    int: ClickHouseInt64Type(),
    # Python's float is a double.
    float: ClickHouseFloat64Type(),
    # A bare ``Decimal`` must keep fractional digits: the core default
    # ``Decimal(10, 0)`` truncates every value to an integer and silently
    # loses money-like data such as ``Decimal("10.99")``. ``Decimal(10, 2)``
    # renders through the same core concept but keeps two fractional digits.
    decimal.Decimal: DecimalType(precision=10, scale=2),
    str: ClickHouseStringType(),
    bytes: ClickHouseStringType(),
    bytearray: ClickHouseStringType(),
    datetime.date: ClickHouseDateType(),
    # ClickHouse has no time-of-day type; ``TimeType`` renders ``DateTime``
    # here, which is documented on ``format_data_type_time``.
    datetime.time: TimeType(),
    # ClickHouse has no TIMESTAMP WITH TIME ZONE type: an aware instant is
    # stored in the same DateTime64 column and the application keeps the value
    # in UTC. Declaring a tz type this dialect cannot render would be a lie, so
    # the storage declaration is the honest, renderable one (see C1's
    # "semantics same, representation may differ" boundary).
    AwareDatetime: ClickHouseDateTime64Type(precision=6),
    datetime.datetime: ClickHouseDateTime64Type(precision=6),
    # No INTERVAL type; the adapter's text form is the carrier.
    datetime.timedelta: TextType(),
    uuid.UUID: ClickHouseUUIDType(),
    # A document: ``JsonType`` renders ``String`` on this dialect (see
    # ``format_data_type_json`` for why the native JSON type is not chosen).
    dict: JsonType(),
    list: ClickHouseArrayType(element_type=_ARRAY_ELEMENT),
    tuple: ClickHouseArrayType(element_type=_ARRAY_ELEMENT),
    set: ClickHouseArrayType(element_type=_ARRAY_ELEMENT),
    frozenset: ClickHouseArrayType(element_type=_ARRAY_ELEMENT),
    # Enum8/16 need an explicit label-to-integer mapping; a bare enum has none.
    enum.Enum: ClickHouseStringType(),
    # -- Complex families ------------------------------------------------
    # Native ``GEOMETRY``; the concrete shape is the column's declaration.
    Geometry: ClickHouseGeometryType(),
    # ``QBit`` needs a dimension the annotation does not carry.
    Vector: TextType(),
    # ``BitString`` is stored as its digits text by the adapter.
    BitString: TextType(),
    # No range types; the neutral adapter's literal text round-trips.
    Range: TextType(),
    Multirange: TextType(),
    # No MAC type; the canonical ``AA:BB:CC:DD:EE:FF`` form is 17 characters,
    # and ``VARCHAR`` renders ``String`` here (the width is dropped).
    MacAddress: VarCharType(length=17),
    # Native IPv4/IPv6 types exist but are split by version; a single
    # IPAddress field can hold either, so the canonical text in String is the
    # honest common carrier (VARCHAR renders String on this dialect).
    IPAddress: VarCharType(length=45),
}


class ClickHouseDataTypeSuggestionsMixin:
    """ClickHouse's answer to "what declaration does a bare field get here"."""

    def suggest_data_types(self) -> DataTypeSuggestion:
        return DataTypeSuggestion(table=dict(CLICKHOUSE_DATA_TYPE_SUGGESTIONS))

    def suggest_extra_data_types(self) -> ExtraDataTypeSuggestion:
        """No backend-owned extra data types beyond the framework's value classes."""
        return ExtraDataTypeSuggestion(table={})


__all__ = ["CLICKHOUSE_DATA_TYPE_SUGGESTIONS", "ClickHouseDataTypeSuggestionsMixin"]
