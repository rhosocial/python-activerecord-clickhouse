# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/types.py
"""ClickHouse DataType formatting and parsing mixin."""

from __future__ import annotations

import re
from typing import Dict, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.data_type import DataTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DataTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    ArrayType,
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    TinyIntType,
    UUIDType,
    VarCharType,
)
from ..expression.types import (
    ClickHouseAggregateFunctionType,
    ClickHouseArrayType,
    ClickHouseBoolType,
    ClickHouseDate32Type,
    ClickHouseDateType,
    ClickHouseDateTime64Type,
    ClickHouseDateTimeType,
    ClickHouseDecimal32Type,
    ClickHouseDecimal64Type,
    ClickHouseDecimal128Type,
    ClickHouseDecimalType,
    ClickHouseEnum16Type,
    ClickHouseEnum8Type,
    ClickHouseFixedStringType,
    ClickHouseFloat32Type,
    ClickHouseFloat64Type,
    ClickHouseGeometryCollectionType,
    ClickHouseGeometryType,
    ClickHouseInt16Type,
    ClickHouseInt32Type,
    ClickHouseInt64Type,
    ClickHouseInt8Type,
    ClickHouseIPv4Type,
    ClickHouseIPv6Type,
    ClickHouseJSONType,
    ClickHouseLineStringType,
    ClickHouseLowCardinalityType,
    ClickHouseMapType,
    ClickHouseMultiLineStringType,
    ClickHouseMultiPointType,
    ClickHouseMultiPolygonType,
    ClickHouseNullableType,
    ClickHousePointType,
    ClickHousePolygonType,
    ClickHouseSimpleAggregateFunctionType,
    ClickHouseStringType,
    ClickHouseTupleType,
    ClickHouseUInt16Type,
    ClickHouseUInt32Type,
    ClickHouseUInt64Type,
    ClickHouseUInt8Type,
    ClickHouseUUIDType,
    ClickHouseVectorType,
)


class ClickHouseTypeSupportMixin(DataTypeMixin, DataTypeSupport):
    """ClickHouse DataType formatting and parsing.

    Implements ``DataTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings and parse raw SQL type strings back into
    ``DataType`` instances.

    Formatting dispatches by the type instance's ``name`` through the
    naming-convention ``format_data_type_<name>`` methods (see
    ``DataTypeMixin``). ClickHouse-specific types carry ``clickhouse_``-prefixed
    names; core types render their real ClickHouse SQL.
    """

    #: First server version on which ClickHouse's ``QBit`` vector type needs no
    #: experimental opt-in. ``QBit`` appeared in 25.10 behind
    #: ``allow_experimental_qbit_type`` and was promoted to General Availability in
    #: 26.2; on 26.7 that setting already defaults to ``1``. So this is the GA
    #: version, and it is what :meth:`format_data_type_clickhouse_vector` gates on.
    _QBIT_MIN_VERSION = (26, 2, 0)

    # ------------------------------------------------------------------
    # DataTypeSupport — formatting
    # ------------------------------------------------------------------

    # --- ClickHouse-specific type formatters (dispatch key = type name) ---

    def _refuse_unsigned_integer(
        self,
        data_type,
        signed_word: str,
        unsigned_class: str,
    ) -> None:
        """Refuse ``unsigned=True`` on a *signed* ClickHouse integer.

        ``unsigned`` is in the integer concepts' ``PARAMETERS``, so it is part of
        their identity: ``ClickHouseInt8Type(unsigned=True)`` is a different
        column from ``ClickHouseInt8Type()``, and the differ compares them as such.
        A dialect may therefore honour the field — the rendered SQL changes when it
        flips — or refuse it, naming the field and why. There is no third option,
        and in particular no "accept it and write the same SQL either way": that
        would create a column that does not match the declaration and report
        success.

        ClickHouse *does* have unsigned integers, so honouring it looks available.
        It is not, and the reason is that ClickHouse spells signedness in the
        **name**, not as a modifier on the name:

        * "ClickHouse offers a number of fixed-length integers, with a sign
          (``Int``) or without a sign (unsigned ``UInt``) ranging from one byte to
          32 bytes." The signed and unsigned forms are two families of type names
          over the same eight storage sizes, with disjoint ranges — ``Int8`` is
          [-128 : 127] and ``UInt8`` is [0 : 255], ``Int16``/``UInt16``,
          ``Int32``/``UInt32``, ``Int64``/``UInt64`` likewise.
          https://clickhouse.com/docs/sql-reference/data-types/int-uint
        * ``UNSIGNED`` is not an attribute a column declaration can carry after the
          native name: ``CREATE TABLE t (a Int8 UNSIGNED)`` fails on 26.7.3.19 with
          ``Unknown data type family: INT8 UNSIGNED``. Nothing to append.
        * The same chapter lists *aliases*, and the unsigned ones —
          ``TINYINT UNSIGNED`` / ``INT1 UNSIGNED``, ``SMALLINT UNSIGNED`` /
          ``YEAR``, ``MEDIUMINT UNSIGNED`` / ``INT UNSIGNED`` /
          ``INTEGER UNSIGNED``, ``UNSIGNED`` / ``BIGINT UNSIGNED`` — resolve to
          ``UInt8``…``UInt64``. Verified on 26.7.3.19:
          ``SELECT toTypeName(CAST(1 AS TINYINT UNSIGNED))`` returns ``UInt8``.
          So rendering one of those aliases *would* honour the flag — and that is
          exactly why honouring is refused.

        **Why the alias is not the answer.** Writing ``TINYINT UNSIGNED`` for
        ``ClickHouseInt8Type(unsigned=True)`` produces a column byte-for-byte
        identical to the one :class:`ClickHouseUInt8Type` renders, because both are
        ``UInt8``. Two declarations for one column is the thing one-concept-one-class
        forbids: the caller would have two ways to name the same storage with no way
        to tell them apart except by reading a docstring, and a differ comparing
        ``ClickHouseUInt8Type()`` against ``ClickHouseInt8Type(unsigned=True)``
        would disagree about whether a column changed. The class already exists for
        this column and pins ``unsigned=True``; the flag on the signed class has
        nowhere honest to go.

        So all eight formatters that can receive the flag — the four
        ``clickhouse_int*`` and the four core ``tinyint``/``smallint``/``integer`` /
        ``bigint`` names, which are the same concepts reached by their own
        dispatch keys — refuse it the same way and point at the class that does own
        the unsigned column.
        """
        if not data_type.unsigned:
            return
        raise UnsupportedFeatureError(
            self.name,
            f"unsigned=True on {signed_word} "
            f"(unsigned is not a modifier on a ClickHouse type name; "
            f"ClickHouse spells the unsigned form of {signed_word} as a different "
            f"type, and {signed_word} itself has no unsigned variant)",
            suggestion=(
                f"Use {unsigned_class}, which declares unsigned=True itself and "
                f"renders the ClickHouse unsigned integer of that width."
            ),
        )

    def _refuse_unsigned_numeric(
        self,
        data_type,
        ch_word: str,
    ) -> None:
        """Refuse ``unsigned=True`` on a ClickHouse float or decimal.

        ``unsigned`` reaches the four numeric concepts here that it reaches the
        integer widths — ``DecimalType``, ``FloatType``, ``DoubleType`` and
        ``RealType`` each carry it in ``PARAMETERS``, so two declarations
        differing only in it are different columns as far as the differ is
        concerned — and ClickHouse's answer is a refusal for a reason the
        integers do not share: **ClickHouse spells signedness in the type
        *name*, and for floats and decimals it does not spell it at all.**

        Every part of that was measured on the wired scenario server, 26.7.3.19.

        * **The server's own type inventory has no unsigned float or decimal.**
          ``system.data_type_families`` names 140 families. The eight whose
          names contain ``UNSIGNED`` are all **integer** aliases and every one
          of them resolves to a ``UInt`` family::

              TINYINT UNSIGNED / INT1 UNSIGNED  -> UInt8
              SMALLINT UNSIGNED                -> UInt16
              MEDIUMINT UNSIGNED / INT UNSIGNED / INTEGER UNSIGNED -> UInt32
              BIGINT UNSIGNED / UNSIGNED       -> UInt64

          There is no ``Decimal ... UNSIGNED``, no ``Float32 UNSIGNED`` and no
          ``Float64 UNSIGNED`` among them. The float and decimal families'
          own ``syntax`` strings are the whole of their grammar and carry no
          attribute at all: ``Float32``, ``Float64``, ``Decimal(P, S)``,
          ``Decimal32(S)``, ``Decimal64(S)``, ``Decimal128(S)``,
          ``Decimal256(S)``, ``BFloat16``.
        * **There is not even a spelling that would parse, and the parser says
          so at the word.** Every one of these is ``SYNTAX_ERROR`` code 62,
          ``failed at position N (UNSIGNED)``:
          ``Decimal(10, 2) UNSIGNED``, ``Decimal(10, 0) UNSIGNED``,
          ``Float32 UNSIGNED``, ``Float32(10) UNSIGNED``, ``Float64 UNSIGNED``.
          The expected-token list the server prints back — ``COLLATE, NOT,
          NULL, DEFAULT, MATERIALIZED, ALIAS, EPHEMERAL, AUTO_INCREMENT,
          COMMENT, CODEC, STATISTICS, TTL, PRIMARY KEY, SETTINGS, token,
          Comma, ClosingRoundBracket`` — is the whole of what may follow a
          column type, and no attribute for signedness is on it.  The
          *inline* ``CHECK (c >= 0)`` is rejected by the **same** rule at the
          **same** position, which is the clearest possible statement that the
          slot does not exist: not "no ``UNSIGNED`` here" but "no attribute
          here at all".
        * **Signedness in the name means the integer columns are a different
          kind of thing, not a decorated one.** ``CAST(-1 AS UInt8)`` is
          ``255``; ``CAST(-1 AS Float32)``, ``CAST(-1 AS Float64)`` and
          ``CAST(-1 AS Decimal(10,2))`` are all ``-1``. So the flag has nothing
          to change on these three: no reachable value differs, and the only
          way to make one differ is to leave the float family entirely.

        **Why the route forward is a named table-level constraint, not the
        ``CHECK`` the other backends suggest** — that is also measured, and it
        is a different answer: ``CREATE TABLE t (c Float32 CHECK (c >= 0))`` is
        rejected with the same code-62 syntax error as ``UNSIGNED``, while
        ``CREATE TABLE t (c Float32, CONSTRAINT cc CHECK (c >= 0))`` is
        accepted and ``INSERT INTO t VALUES (-1)`` then fails with code 469,
        ``Constraint 'cc' ... is violated ... Column values: c = -1``.  So
        ClickHouse does enforce the constraint — it just has nowhere to put an
        inline one, which is the same fact as the missing attribute slot seen
        from the other side.  The ``suggestion`` below therefore names the
        table-level form, because the inline form other backends recommend is
        a syntax error here and telling a caller to write it would be worse
        than saying nothing.

        Writing a bare ``Float32`` / ``Float64`` / ``Decimal(P, S)`` for an
        unsigned request would create a column that accepts the negatives the
        caller declared it would not, and report success: the same silent loss
        as accepting the flag and discarding it.

        ``UnsupportedFeatureError``, not ``ValueError``: this is a declaration
        the grammar cannot express at all rather than a wrong value, and the two
        exceptions do not share a base class.  This method runs **before**
        ``_check_spelling`` in every caller, so a request wrong in two ways is
        told about the signedness first — that one is a stronger and less
        recoverable statement than a misspelled word.
        """
        if not data_type.unsigned:
            return
        raise UnsupportedFeatureError(
            self.name,
            f"unsigned=True on {ch_word} "
            f"(ClickHouse expresses signedness in the type NAME, not as a "
            f"modifier on it, and only for integers: UInt8..UInt64 are their "
            f"own type families, while {ch_word} has no unsigned variant at all "
            f"-- system.data_type_families on 26.7 lists no unsigned float or "
            f"decimal family, and '{ch_word} ... UNSIGNED' is a SYNTAX_ERROR at "
            f"the word UNSIGNED, so there is no attribute slot to write it in)",
            suggestion=(
                f"Declare the {ch_word} column signed. ClickHouse has no "
                f"unsigned {ch_word}: enforce the range with a named "
                f"table-level constraint instead -- 'CONSTRAINT cc CHECK (c >= "
                f"0)' in the column list, which the server enforces (code 469 "
                f"VIOLATED_CONSTRAINT). An inline 'CHECK (c >= 0)' after the "
                f"type is a syntax error on this server, as 'UNSIGNED' is."
            ),
        )

    def format_data_type_clickhouse_int8(self, data_type: ClickHouseInt8Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int8`` — the signed 8-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`, which is also where the reason is
        written down.
        """
        self._refuse_unsigned_integer(data_type, "Int8", "ClickHouseUInt8Type")
        return "Int8", ()

    def format_data_type_clickhouse_int16(self, data_type: ClickHouseInt16Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int16`` — the signed 16-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`.
        """
        self._refuse_unsigned_integer(data_type, "Int16", "ClickHouseUInt16Type")
        return "Int16", ()

    def format_data_type_clickhouse_int32(self, data_type: ClickHouseInt32Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int32`` — the signed 32-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`.
        """
        self._refuse_unsigned_integer(data_type, "Int32", "ClickHouseUInt32Type")
        return "Int32", ()

    def format_data_type_clickhouse_int64(self, data_type: ClickHouseInt64Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int64`` — the signed 64-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`.
        """
        self._refuse_unsigned_integer(data_type, "Int64", "ClickHouseUInt64Type")
        return "Int64", ()

    def format_data_type_clickhouse_uint8(self, data_type: ClickHouseUInt8Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt8`` — the unsigned 8-bit integer, [0 : 255].

        The unsigned form is a *class* on this backend, so there is nothing to
        refuse here: :class:`ClickHouseUInt8Type` pins ``unsigned=True`` in its own
        ``__init__`` and takes no flag, which means this formatter cannot be reached
        with ``unsigned=False``.
        """
        return "UInt8", ()

    def format_data_type_clickhouse_uint16(self, data_type: ClickHouseUInt16Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt16`` — the unsigned 16-bit integer.

        See :meth:`format_data_type_clickhouse_uint8` for why ``unsigned`` cannot
        arrive here.
        """
        return "UInt16", ()

    def format_data_type_clickhouse_uint32(self, data_type: ClickHouseUInt32Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt32`` — the unsigned 32-bit integer.

        See :meth:`format_data_type_clickhouse_uint8` for why ``unsigned`` cannot
        arrive here.
        """
        return "UInt32", ()

    def format_data_type_clickhouse_uint64(self, data_type: ClickHouseUInt64Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt64`` — the unsigned 64-bit integer.

        See :meth:`format_data_type_clickhouse_uint8` for why ``unsigned`` cannot
        arrive here.
        """
        return "UInt64", ()

    def format_data_type_clickhouse_float32(self, data_type: ClickHouseFloat32Type) -> Tuple[str, tuple]:
        return "Float32", ()

    def format_data_type_clickhouse_float64(self, data_type: ClickHouseFloat64Type) -> Tuple[str, tuple]:
        return "Float64", ()

    def format_data_type_clickhouse_decimal(self, data_type: ClickHouseDecimalType) -> Tuple[str, tuple]:
        return f"Decimal({data_type.precision}, {data_type.scale})", ()

    def format_data_type_clickhouse_decimal32(self, data_type: ClickHouseDecimal32Type) -> Tuple[str, tuple]:
        return f"Decimal32({data_type.scale})", ()

    def format_data_type_clickhouse_decimal64(self, data_type: ClickHouseDecimal64Type) -> Tuple[str, tuple]:
        return f"Decimal64({data_type.scale})", ()

    def format_data_type_clickhouse_decimal128(self, data_type: ClickHouseDecimal128Type) -> Tuple[str, tuple]:
        return f"Decimal128({data_type.scale})", ()

    def format_data_type_clickhouse_string(self, data_type: ClickHouseStringType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_clickhouse_fixed_string(self, data_type: ClickHouseFixedStringType) -> Tuple[str, tuple]:
        return f"FixedString({data_type.length})", ()

    def format_data_type_clickhouse_date(self, data_type: ClickHouseDateType) -> Tuple[str, tuple]:
        return "Date", ()

    def format_data_type_clickhouse_date32(self, data_type: ClickHouseDate32Type) -> Tuple[str, tuple]:
        return "Date32", ()

    def format_data_type_clickhouse_timestamp(self, data_type: ClickHouseDateTimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    def format_data_type_clickhouse_timestamp64(self, data_type: ClickHouseDateTime64Type) -> Tuple[str, tuple]:
        return f"DateTime64({data_type.precision})", ()

    def format_data_type_clickhouse_bool(self, data_type: ClickHouseBoolType) -> Tuple[str, tuple]:
        return "Bool", ()

    def format_data_type_clickhouse_uuid(self, data_type: ClickHouseUUIDType) -> Tuple[str, tuple]:
        return "UUID", ()

    def format_data_type_clickhouse_ipv4(self, data_type: ClickHouseIPv4Type) -> Tuple[str, tuple]:
        return "IPv4", ()

    def format_data_type_clickhouse_ipv6(self, data_type: ClickHouseIPv6Type) -> Tuple[str, tuple]:
        return "IPv6", ()

    def format_data_type_clickhouse_enum8(self, data_type: ClickHouseEnum8Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in data_type.values)
        return f"Enum8({values_str})", ()

    def format_data_type_clickhouse_enum16(self, data_type: ClickHouseEnum16Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in data_type.values)
        return f"Enum16({values_str})", ()

    def format_data_type_clickhouse_array(self, data_type: ClickHouseArrayType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.element_type)
        return f"Array({inner_sql})", inner_params

    def format_data_type_clickhouse_map(self, data_type: ClickHouseMapType) -> Tuple[str, tuple]:
        key_sql, key_params = self.format_data_type(data_type.key_type)
        val_sql, val_params = self.format_data_type(data_type.value_type)
        return f"Map({key_sql}, {val_sql})", key_params + val_params

    def format_data_type_clickhouse_tuple(self, data_type: ClickHouseTupleType) -> Tuple[str, tuple]:
        parts = []
        params = []
        for i, elem_type in enumerate(data_type.element_types):
            elem_sql, elem_params = self.format_data_type(elem_type)
            if data_type.element_names:
                parts.append(f"{data_type.element_names[i]} {elem_sql}")
            else:
                parts.append(elem_sql)
            params.extend(elem_params)
        return f"Tuple({', '.join(parts)})", tuple(params)

    def format_data_type_clickhouse_nullable(self, data_type: ClickHouseNullableType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.inner_type)
        return f"Nullable({inner_sql})", inner_params

    def format_data_type_clickhouse_low_cardinality(self, data_type: ClickHouseLowCardinalityType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(data_type.inner_type)
        return f"LowCardinality({inner_sql})", inner_params

    def format_data_type_clickhouse_json(self, data_type: ClickHouseJSONType) -> Tuple[str, tuple]:
        return "JSON", ()

    def format_data_type_clickhouse_aggregate_function(
        self,
        data_type: ClickHouseAggregateFunctionType,
    ) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in data_type.arg_types)
        return f"AggregateFunction({data_type.function_name}, {args})", ()

    def format_data_type_clickhouse_simple_aggregate_function(
        self, data_type: ClickHouseSimpleAggregateFunctionType
    ) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in data_type.arg_types)
        return f"SimpleAggregateFunction({data_type.function_name}, {args})", ()

    def format_data_type_clickhouse_geometry(self, data_type: ClickHouseGeometryType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"GEOMETRY SRID {data_type.srid}", ()
        return "GEOMETRY", ()

    def format_data_type_clickhouse_point(self, data_type: ClickHousePointType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"POINT SRID {data_type.srid}", ()
        return "POINT", ()

    def format_data_type_clickhouse_linestring(self, data_type: ClickHouseLineStringType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"LINESTRING SRID {data_type.srid}", ()
        return "LINESTRING", ()

    def format_data_type_clickhouse_polygon(self, data_type: ClickHousePolygonType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"POLYGON SRID {data_type.srid}", ()
        return "POLYGON", ()

    def format_data_type_clickhouse_multipoint(self, data_type: ClickHouseMultiPointType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTIPOINT SRID {data_type.srid}", ()
        return "MULTIPOINT", ()

    def format_data_type_clickhouse_multilinestring(
        self,
        data_type: ClickHouseMultiLineStringType,
    ) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTILINESTRING SRID {data_type.srid}", ()
        return "MULTILINESTRING", ()

    def format_data_type_clickhouse_multipolygon(self, data_type: ClickHouseMultiPolygonType) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"MULTIPOLYGON SRID {data_type.srid}", ()
        return "MULTIPOLYGON", ()

    def format_data_type_clickhouse_geometrycollection(
        self,
        data_type: ClickHouseGeometryCollectionType,
    ) -> Tuple[str, tuple]:
        if data_type.srid is not None:
            return f"GEOMETRYCOLLECTION SRID {data_type.srid}", ()
        return "GEOMETRYCOLLECTION", ()

    def format_data_type_clickhouse_vector(self, data_type: ClickHouseVectorType) -> Tuple[str, tuple]:
        """Render ClickHouse's fixed-dimension vector as ``QBit(Float32, dim)``.

        ``QBit`` is ClickHouse's vector type, not ``VECTOR(n)``: ``VECTOR(n)`` is
        MySQL 9.0's spelling and ClickHouse rejects it with ``Unknown data type
        family: VECTOR`` — confirmed against 26.7.3.19 and against
        ``system.data_type_families``, which lists ``QBit`` and no ``VECTOR``.

        Version gate
        ------------
        ``QBit`` landed in 25.10 behind ``allow_experimental_qbit_type``, was
        promoted to Beta in 26.1 and to General Availability in 26.2, after which
        the setting is no longer needed — on 26.7 it already defaults to ``1``.
        The gate is therefore GA, not first appearance: on 25.10–26.1 the type
        exists but a column declaration still needs an experimental opt-in that
        DDL does not carry, so this dialect declines to write one rather than
        emit a statement the server will reject.
        """
        if self.version < self._QBIT_MIN_VERSION:
            required = "{}.{}+".format(*self._QBIT_MIN_VERSION[:2])
            raise UnsupportedFeatureError(
                self.name,
                f"the QBit vector type (needs ClickHouse {required})",
                suggestion=(
                    "This server is older than QBit's General Availability "
                    f"({required}); store the embedding as Array(Float32) and "
                    "search it with L2Distance."
                ),
            )
        return f"QBit(Float32, {data_type.dim})", ()

    # ------------------------------------------------------------------
    # DataTypeSupport — supports_data_type_* (1:1 with format_data_type_*)
    # ------------------------------------------------------------------

    def supports_data_type_clickhouse_int8(self) -> bool:
        return True

    def supports_data_type_clickhouse_int16(self) -> bool:
        return True

    def supports_data_type_clickhouse_int32(self) -> bool:
        return True

    def supports_data_type_clickhouse_int64(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint8(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint16(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint32(self) -> bool:
        return True

    def supports_data_type_clickhouse_uint64(self) -> bool:
        return True

    def supports_data_type_clickhouse_float32(self) -> bool:
        return True

    def supports_data_type_clickhouse_float64(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal32(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal64(self) -> bool:
        return True

    def supports_data_type_clickhouse_decimal128(self) -> bool:
        return True

    def supports_data_type_clickhouse_string(self) -> bool:
        return True

    def supports_data_type_clickhouse_fixed_string(self) -> bool:
        return True

    def supports_data_type_clickhouse_date(self) -> bool:
        return True

    def supports_data_type_clickhouse_date32(self) -> bool:
        return True

    def supports_data_type_clickhouse_timestamp(self) -> bool:
        return True

    def supports_data_type_clickhouse_timestamp64(self) -> bool:
        return True

    def supports_data_type_clickhouse_bool(self) -> bool:
        return True

    def supports_data_type_clickhouse_uuid(self) -> bool:
        return True

    def supports_data_type_clickhouse_ipv4(self) -> bool:
        return True

    def supports_data_type_clickhouse_ipv6(self) -> bool:
        return True

    def supports_data_type_clickhouse_enum8(self) -> bool:
        return True

    def supports_data_type_clickhouse_enum16(self) -> bool:
        return True

    def supports_data_type_clickhouse_array(self) -> bool:
        return True

    def supports_data_type_clickhouse_map(self) -> bool:
        return True

    def supports_data_type_clickhouse_tuple(self) -> bool:
        return True

    def supports_data_type_clickhouse_nullable(self) -> bool:
        return True

    def supports_data_type_clickhouse_low_cardinality(self) -> bool:
        return True

    def supports_data_type_clickhouse_json(self) -> bool:
        return True

    def supports_data_type_clickhouse_aggregate_function(self) -> bool:
        return True

    def supports_data_type_clickhouse_simple_aggregate_function(self) -> bool:
        return True

    def supports_data_type_clickhouse_geometry(self) -> bool:
        return True

    def supports_data_type_clickhouse_point(self) -> bool:
        return True

    def supports_data_type_clickhouse_linestring(self) -> bool:
        return True

    def supports_data_type_clickhouse_polygon(self) -> bool:
        return True

    def supports_data_type_clickhouse_multipoint(self) -> bool:
        return True

    def supports_data_type_clickhouse_multilinestring(self) -> bool:
        return True

    def supports_data_type_clickhouse_multipolygon(self) -> bool:
        return True

    def supports_data_type_clickhouse_geometrycollection(self) -> bool:
        return True

    def supports_data_type_clickhouse_vector(self) -> bool:
        return True

    # Core types that ClickHouse renders natively

    def supports_data_type_integer(self) -> bool:
        return True

    def supports_data_type_bigint(self) -> bool:
        return True

    def supports_data_type_smallint(self) -> bool:
        return True

    def supports_data_type_tinyint(self) -> bool:
        return True

    def supports_data_type_varchar(self) -> bool:
        return True

    def supports_data_type_char(self) -> bool:
        return True

    def supports_data_type_text(self) -> bool:
        return True

    def supports_data_type_boolean(self) -> bool:
        return True

    def supports_data_type_date(self) -> bool:
        return True

    def supports_data_type_datetime(self) -> bool:
        return True

    def supports_data_type_timestamp(self) -> bool:
        return True

    def supports_data_type_time(self) -> bool:
        return True

    def supports_data_type_float(self) -> bool:
        return True

    def supports_data_type_double(self) -> bool:
        return True

    def supports_data_type_real(self) -> bool:
        return True

    def supports_data_type_decimal(self) -> bool:
        return True

    def supports_data_type_json(self) -> bool:
        return True

    def supports_data_type_blob(self) -> bool:
        return True

    def supports_data_type_array(self) -> bool:
        return True

    def supports_data_type_uuid(self) -> bool:
        """ClickHouse has a native ``UUID`` type.

        Checked against the 26.7 scenario server: ``CREATE TABLE t (u UUID)``
        is accepted and ``system.columns`` reports ``UUID``. So the concept is
        rendered here rather than substituted — the alternative would be to send a
        UUID column to ``String``, which is what ``ClickHouseUUIDType`` avoided
        doing.
        """
        return True

    # ------------------------------------------------------------------
    # DataTypeSupport — suggested_data_types()
    # ------------------------------------------------------------------

    def suggested_data_types(self) -> Dict[str, type]:
        """Core concepts ClickHouse genuinely cannot spell, and what it stores.

        ClickHouse's data types are enumerated exhaustively in its manual, so a
        concept is only absent from this dialect for a real reason, not because
        the backend has not got round to it. Every substitute below is a
        ``DataType`` subclass whose own ``name`` this dialect renders, so the
        advice in ``format_data_type``'s error message can be acted on.

        ``custom``
            An unrecognised type name is a name this framework has no class
            for. Some are names ClickHouse itself does not know, and the server
            rejects those with ``Unknown data type family``; others are aliases
            the server accepts but this parser deliberately does not claim
            (``VARCHAR(10)`` resolves to ``String``, ``TINYINT`` to ``Int8``).
            Either way there is no pass-through — the name would either fail at
            the server or store a type the caller may not have meant — which is
            why the dialect has no ``format_data_type_custom``: there is no
            "write whatever the caller said" on this backend. The honest answer
            is the byte-string type ClickHouse does have.

        ``interval``
            ClickHouse has no ``INTERVAL`` type. An elapsed time is a number of
            seconds — an ``Int64`` — or, for a typed interval, the difference of
            two ``DateTime64`` values. ``ClickHouseDateTime64Type`` is named for
            the second form, but ``ClickHouseInt64Type`` is the one that covers
            both, since the difference of two epoch counts is an epoch count.

        ``timestamptz``
            ClickHouse has no timezone-*suffixed* type. A timezone-aware instant
            is a ``DateTime64`` that carries the zone in its declaration
            (``DateTime64(3, 'UTC')``), which is why the substitute is the
            class that knows how to render that form rather than a plain
            ``DateTime``. Note the class as it stands carries no timezone
            parameter, so the rendered column will use the server default —
            see the merge-evaluation report.

        ``timetz``
            ClickHouse has no time-only type at all, with or without a zone; the
            closest storage is a ``DateTime``, which is also what this dialect
            renders for core's ``time`` (see :meth:`format_data_type_time`).

        ``xml``
            ClickHouse's manual enumerates its types and XML is not among them.
            A document would be stored as a byte string. ``TextType`` is named
            rather than ``ClickHouseStringType`` because the two render the same
            ``String`` and the core class is the one that says what the value
            means.

        ``binary`` / ``varbinary``
            ClickHouse's byte-string types are ``String`` (variable) and
            ``FixedString(N)`` (fixed). ``FixedString`` is genuinely a
            fixed-length byte string, so ``binary`` has a real counterpart;
            ``varbinary`` does not, and ``String`` is what it would become.

        ``enum``
            ClickHouse has two enums, and neither is core's ``EnumType``: they
            take explicit integers, cannot be NULL and leave most operations
            undefined. See :class:`ClickHouseEnum8Type` for the full list of
            differences. A generic enum's labels and nothing else cannot be
            rendered as either, so the substitute is the plain byte string.

        ``jsonb``
            ClickHouse has a native ``JSON`` type, but it arrived in 24.10 and
            ``JSONB`` — PostgreSQL's binary representation — has no counterpart;
            the dialect renders ``json`` as ``String``, so ``jsonb`` is the same
            storage. Deliberately *not* ``ClickHouseJSONType``: suggesting a
            native type here would promise a feature whose version floor this
            dialect does not check.
        """
        return {
            "binary": ClickHouseStringType,
            "varbinary": ClickHouseStringType,
            "custom": ClickHouseStringType,
            "enum": ClickHouseStringType,
            "interval": ClickHouseInt64Type,
            "jsonb": ClickHouseStringType,
            "timetz": ClickHouseDateTimeType,
            "timestamptz": ClickHouseDateTime64Type,
            "xml": TextType,
        }

    # --- Core types (pure names) rendered to real ClickHouse SQL ---

    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        """``INTEGER`` and ``INT`` are SQL's two spellings of one 4-byte signed
        integer; ClickHouse has exactly one such type and calls it ``Int32``.

        Both spellings are accepted and both normalise to ``Int32``: the caller
        asked for the concept, and refusing the non-default one would turn a
        ``VarCharType(spelling="character varying")``-style choice into an error
        without saying anything the rendered column does not already say.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`, which is also where the reason is
        written down. It is refused here for exactly the reason it is refused on
        :meth:`format_data_type_clickhouse_int32`: ``IntegerType(unsigned=True)``
        and ``ClickHouseUInt32Type()`` are the same ``UInt32`` column, and this
        backend keeps one class per column.
        """
        self._check_spelling(data_type, IntegerType)
        self._refuse_unsigned_integer(data_type, "Int32", "ClickHouseUInt32Type")
        return "Int32", ()

    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        """``BIGINT`` and ``INT8`` are the standard's and PostgreSQL's spellings of
        the 8-byte signed integer. ClickHouse writes ``Int64`` and has no other
        word for it; both spellings are accepted and render as written above.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`."""
        self._check_spelling(data_type, BigIntType)
        self._refuse_unsigned_integer(data_type, "Int64", "ClickHouseUInt64Type")
        return "Int64", ()

    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        """``SMALLINT`` / ``INT2`` — the 2-byte signed integer, which ClickHouse
        spells ``Int16``. Both spellings accepted.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`."""
        self._check_spelling(data_type, SmallIntType)
        self._refuse_unsigned_integer(data_type, "Int16", "ClickHouseUInt16Type")
        return "Int16", ()

    def format_data_type_tinyint(self, data_type: TinyIntType) -> Tuple[str, tuple]:
        """``TINYINT`` / ``INT1`` — the 1-byte signed integer, which ClickHouse
        spells ``Int8``.

        Neither spelling is ClickHouse's own (unlike ``BOOL``/``BOOLEAN``, which
        ClickHouse does write), but both name the same 1-byte signed integer
        ``Int8`` holds, so both are accepted and render ``Int8``.

        Note that ClickHouse *also* reads ``TINYINT UNSIGNED`` and ``INT1
        UNSIGNED`` — as aliases for ``UInt8``, which is the alias table's purpose.
        That does not make the flag honoured on this concept: the alias resolves
        to ``UInt8``, the column :class:`ClickHouseUInt8Type` already owns, so
        ``unsigned`` is refused here and points at that class instead. See
        :meth:`_refuse_unsigned_integer`.
        """
        self._check_spelling(data_type, TinyIntType)
        self._refuse_unsigned_integer(data_type, "Int8", "ClickHouseUInt8Type")
        return "Int8", ()

    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        """ClickHouse has no length-bounded character type: ``String`` is
        variable-length and unpadded, so the declared length is dropped. Both
        ``VARCHAR`` and ``CHARACTER VARYING`` are accepted for the same reason as
        the integer spellings — the concept was asked for and this is its only
        storage."""
        self._check_spelling(data_type, VarCharType)
        return "String", ()

    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        """``CHAR`` / ``CHARACTER`` — a fixed-length character string.

        Rendered ``String``, which is a **widening**, and the caller should know
        it: ClickHouse has no fixed-width character type, so a ``CHAR(10)`` column
        becomes an unbounded one. ``ClickHouseFixedStringType`` is the fixed-length
        type on this backend, but it is a fixed number of *bytes*, zero-padded —
        a different concept, so it is not what a generic ``CharType`` silently
        becomes. Both spellings are accepted for the reason given on
        :meth:`format_data_type_varchar`.
        """
        self._check_spelling(data_type, CharType)
        return "String", ()

    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        """``TEXT`` / ``CLOB`` — unbounded text, which is ``String``.

        ``CLOB`` is not a ClickHouse word, but it is the concept's own second
        spelling and ``String`` is the concept's only storage here, so it is
        accepted rather than refused.
        """
        self._check_spelling(data_type, TextType)
        return "String", ()

    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        """``BOOLEAN`` / ``BOOL`` — and both are ClickHouse's own words.

        Verified against the 26.7 scenario server: ``CREATE TABLE t (b BOOLEAN)``
        and ``(b Bool)`` are both accepted and both reported back as ``Bool``, so
        this is the one concept whose core spelling list happens to be exactly
        ClickHouse's vocabulary.
        """
        self._check_spelling(data_type, BooleanType)
        return "Bool", ()

    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        """``DATE`` — ClickHouse's own ``Date``, 1970..2149 in two bytes.

        Deliberately *not* ``Date32``: the wider range is a different storage and
        a different type to the server, and silently choosing it would change the
        range a column accepts. ``ClickHouseDate32Type`` is available for that.
        """
        return "Date", ()

    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        """``DATETIME`` — MySQL's wall-clock date and time.

        ClickHouse has no such type; its ``DateTime`` is a count of seconds since
        the epoch. The nearest storage is ``DateTime``, and the difference is
        visible: a ``DATETIME`` value has no epoch to convert against, so on this
        backend it is stored as an instant. ``format_data_type_timestamp`` renders
        the same word for core's ``TIMESTAMP``, which is the same storage and the
        honest reading of it.
        """
        return "DateTime", ()

    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        """``TIMESTAMP`` — an instant, which is what ClickHouse's ``DateTime`` is.

        Sub-second precision is dropped: ClickHouse spells that
        ``DateTime64(p)``, and choosing the word for the caller would silently
        widen the value. ``ClickHouseDateTime64Type`` is the type that carries the
        precision.
        """
        return "DateTime", ()

    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        """``TIME`` — time of day, with no date attached.

        ClickHouse has no time-only type; the closest storage is ``DateTime``,
        which is what is rendered. A column declared ``TIME`` on this backend
        therefore holds an instant, not a time of day. ``timetz`` is not rendered
        at all — see :meth:`suggested_data_types`.
        """
        return "DateTime", ()

    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        """``FLOAT[(p)]`` — approximate numeric.

        Rendered ``Float32``, the default approximate type. A declared
        ``precision`` is **not** honoured: ClickHouse's ``Float32`` has a fixed
        32-bit mantissa and there is no ``FLOAT(p)`` spelling to widen it to, so
        honouring the request would mean substituting a different type for the one
        asked for. ``format_data_type_double`` is where a caller who wants the
        wider float should end up.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_numeric`, which is where the reason, the
        ``system.data_type_families`` inventory and the parser measurements are
        written down.
        """
        self._refuse_unsigned_numeric(data_type, "Float32")
        return "Float32", ()

    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        """``DOUBLE`` / ``DOUBLE PRECISION`` — the 8-byte float, ``Float64``.

        Both spellings accepted; the concept's default spelling is ``double``, so
        it must render, and the long form names the same 53-bit mantissa.

        ``unsigned`` is refused rather than ignored, before the spelling check;
        see :meth:`_refuse_unsigned_numeric`.
        """
        self._refuse_unsigned_numeric(data_type, "Float64")
        self._check_spelling(data_type, DoubleType)
        return "Float64", ()

    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        """``REAL`` — single precision. ClickHouse's word for it is ``Float32``,
        which is also what ``FLOAT`` renders, because ClickHouse has no separate
        ``REAL`` family.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_numeric`.
        """
        self._refuse_unsigned_numeric(data_type, "Float32")
        return "Float32", ()

    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        """``DECIMAL`` / ``NUMERIC`` / ``DEC`` — exact fixed-point.

        ClickHouse's spelling vocabulary for this concept is *exactly* the core
        list: verified against the 26.7 scenario server, ``NUMERIC(10,2)`` and
        ``DEC(10,2)`` are both accepted and both reported back as
        ``Decimal(10, 2)``. So all three are accepted and render the same.

        A precision of 38 is ClickHouse's maximum and is reached by
        ``Decimal128``; ``Decimal(P, S)`` with a smaller P is a different storage,
        which is why the precision is rendered rather than normalised.

        ``unsigned`` is refused rather than ignored, before the spelling check;
        see :meth:`_refuse_unsigned_numeric`.  ClickHouse's ``Decimal`` family
        has no unsigned variant and no attribute slot — ``Decimal(10, 2)
        UNSIGNED`` is a syntax error at the word — so the flag has nowhere to go
        and the caller is told so by name rather than handed a signed column.
        """
        self._refuse_unsigned_numeric(data_type, "Decimal(P, S)")
        self._check_spelling(data_type, DecimalType)
        p = data_type.precision
        s = data_type.scale
        if p is not None and s is not None:
            return f"Decimal({p}, {s})", ()
        if p is not None:
            return f"Decimal({p})", ()
        return "Decimal(10, 0)", ()

    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        """``JSON`` — rendered ``String``, not ClickHouse's native ``JSON``.

        The native type exists (``ClickHouseJSONType`` renders it) but it arrived
        in 24.10 and this dialect does not check the server version for it, so
        the portable column is a byte string and a caller who wants the native
        type asks for ``ClickHouseJSONType`` by name. Reporting this honestly
        matters: a native ``JSON`` column knows its paths and ``JSONExtract``
        reads a field without parsing the value, and a ``String`` column does not.
        """
        return "String", ()

    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        """``BLOB`` / ``BYTEA`` — a byte string, which is ClickHouse's ``String``.

        Both spellings accepted: ``BYTEA`` is PostgreSQL's word and ``BLOB`` is
        the concept's default, and ``String`` is the concept's only unbounded byte
        storage on this backend.

        Not ``FixedString``: there is no length to honour, and ``FixedString``
        zero-pads, so using it here would change the value.
        """
        self._check_spelling(data_type, BlobType)
        return "String", ()

    def format_data_type_uuid(self, data_type: UUIDType) -> Tuple[str, tuple]:
        """``UUID`` — ClickHouse has a type with that exact name and meaning.

        128 bits, stored as two 64-bit halves. ``ClickHouseUUIDType`` renders the
        same SQL through its own namespaced name; both are the UUID concept, one
        reached through the core type and one through the backend's.
        """
        return "UUID", ()

    def format_data_type_array(self, data_type: ArrayType) -> Tuple[str, tuple]:
        """``T[]`` — ClickHouse's ``Array(T)``, always one dimension.

        ClickHouse has no multi-dimensional array syntax, so ``dimensions > 1``
        is rendered as a single level rather than rejected: a nested
        ``Array(Array(T))`` is the same value, and this is the documented
        ClickHouse spelling for it.
        """
        inner_sql, inner_params = self.format_data_type(data_type.element_type)
        return f"Array({inner_sql})", inner_params

    # ------------------------------------------------------------------
    # DataTypeSupport — parsing
    # ------------------------------------------------------------------

    _CLICKHOUSE_INTEGER_TYPES = re.compile(
        r"^(?:Int8|Int16|Int32|Int64|UInt8|UInt16|UInt32|UInt64)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_FLOAT_TYPES = re.compile(
        r"^(?:Float32|Float64)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_DECIMAL_TYPES = re.compile(
        r"^(?:Decimal(?:32|64|128)?|Numeric|Dec)(?:\(.*\))?\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_STRING_TYPES = re.compile(
        r"^(?:String|FixedString(?:\(.*\))?)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_DATE_TYPES = re.compile(
        r"^(?:Date|Date32|DateTime|DateTime64(?:\(.*\))?)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_OTHER_TYPES = re.compile(
        r"^(?:Bool|Boolean|UUID|IPv4|IPv6|JSON)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_ENUM_TYPES = re.compile(
        r"^(?:Enum8|Enum16)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_CONTAINER_TYPES = re.compile(
        r"^(?:Array|Map|Tuple|Nullable|LowCardinality)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_AGGREGATE_TYPES = re.compile(
        r"^(?:AggregateFunction|SimpleAggregateFunction)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_SPATIAL_TYPES = re.compile(
        r"^(?:GEOMETRY|POINT|LINESTRING|POLYGON|"
        r"MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\b",
        re.IGNORECASE,
    )
    _CLICKHOUSE_VECTOR_TYPES = re.compile(
        r"^(?:QBit)\b",
        re.IGNORECASE,
    )
    #: MySQL-style integer aliases ClickHouse accepts and resolves to ``UInt``.
    #:
    #: One concept, one class: each alias maps to the ``ClickHouseUInt*Type``
    #: that already owns that column -- the same argument as
    #: ``_refuse_unsigned_integer``'s "why the alias is not the answer" -- so an
    #: aliased spelling reads back as the class the native spelling yields and a
    #: differ comparing the two sees no change.
    #:
    #: Measured on the 26.7.3.19 scenario server.  Every name below is
    #: ``case_insensitive = 1`` in ``system.data_type_families`` with the
    #: ``alias_to`` shown, and ``SELECT toTypeName(CAST(1 AS <name>))`` returns it:
    #:
    #:     TINYINT UNSIGNED / INT1 UNSIGNED                    -> UInt8
    #:     SMALLINT UNSIGNED / YEAR                            -> UInt16
    #:     MEDIUMINT UNSIGNED / INT UNSIGNED / INTEGER UNSIGNED -> UInt32
    #:     BIGINT UNSIGNED / UNSIGNED                          -> UInt64
    #:
    #: ``YEAR`` is on the list because ClickHouse itself resolves it to
    #: ``UInt16``; it is not a year storage type here.  The MySQL-style ``YEAR``
    #: concept -- one byte, 1901..2155 -- lives in the MySQL backend as
    #: ``MySQLYearType``, and mapping the word to a year class would claim a
    #: storage the server does not use.
    #:
    #: Deliberately *not* on the list: the single-word signed aliases
    #: (``TINYINT``, ``INT1``, ``SMALLINT``, ``MEDIUMINT``, ``INT``, ``INTEGER``,
    #: ``BIGINT``) and their ``* SIGNED`` forms.  The server accepts those too --
    #: measured on 26.7.3.19, ``toTypeName(CAST(1 AS TINYINT))`` is ``Int8`` --
    #: but they are spellings of the signed columns whose native names this
    #: parser already claims, and the server's alias table is much wider than
    #: this dialect's vocabulary (``VARCHAR(10)`` -> ``String`` and ``FLOAT`` ->
    #: ``Float32`` are equally real and equally unclaimed).  They keep the
    #: answers they had: a single word falls through to ``CustomType``, a
    #: two-word ``* SIGNED`` name keeps the closed-grammar ``InvalidTypeNameError``.
    _CLICKHOUSE_UNSIGNED_INTEGER_ALIASES: Dict[str, type] = {
        "TINYINT UNSIGNED": ClickHouseUInt8Type,
        "INT1 UNSIGNED": ClickHouseUInt8Type,
        "SMALLINT UNSIGNED": ClickHouseUInt16Type,
        "YEAR": ClickHouseUInt16Type,
        "MEDIUMINT UNSIGNED": ClickHouseUInt32Type,
        "INT UNSIGNED": ClickHouseUInt32Type,
        "INTEGER UNSIGNED": ClickHouseUInt32Type,
        "BIGINT UNSIGNED": ClickHouseUInt64Type,
        "UNSIGNED": ClickHouseUInt64Type,
    }

    # ``UNSIGNED`` as a whole word, checked only against a string whose head one of
    # the three numeric branches below would otherwise claim.  The MySQL-style
    # aliases above are recognised *before* this guard; none of their heads is a
    # word those three branches claim, so the two checks cannot collide.  What
    # this catches is the opposite mistake: ``Int8 UNSIGNED``, ``Float32
    # UNSIGNED``, ``Float64 UNSIGNED`` and ``Decimal(10,2) UNSIGNED``, which a
    # branch would otherwise match on the head and return a *signed* type for.
    # See ``_refuse_unsigned_type_string``.
    _UNSIGNED_ATTRIBUTE = re.compile(r"\bUNSIGNED\b", re.IGNORECASE)

    def _refuse_unsigned_type_string(self, raw: str) -> None:
        """Refuse ``Int8`` / ``Float32`` / ``Float64`` / ``Decimal`` + ``UNSIGNED``.

        :meth:`_refuse_unsigned_numeric` closes the door on the way *in* — a
        declaration.  This closes it on the way *out*: a string.  Without it the
        three numeric branches below match on the word *in front of* the attribute
        and return a signed type — ``parse_type("Float32 UNSIGNED")`` was
        ``ClickHouseFloat32Type()`` and ``parse_type("Decimal(10,2) UNSIGNED")``
        was ``ClickHouseDecimalType(10, 2)`` — so a string saying ``UNSIGNED``
        produced a value object that ``==`` calls equal to the signed column.  The
        differ would then report no change for the one change the string
        describes.

        It is checked *here*, at the head of ``parse_type``, and only for a string
        whose head a numeric branch would claim.  The MySQL-style integer aliases
        ClickHouse genuinely accepts (``TINYINT UNSIGNED`` and friends, which the
        server resolves to ``UInt8``…``UInt64``) are not attributes and are not
        caught here: ``_CLICKHOUSE_UNSIGNED_INTEGER_ALIASES`` recognises them
        before the numeric branches and returns the ``UInt`` class they name.

        No server can have written the strings this refuses: ``Int8 UNSIGNED`` is
        ``UNKNOWN_TYPE`` code 50 on 26.7 and ``Float32 UNSIGNED`` /
        ``Float64 UNSIGNED`` / ``Decimal(10,2) UNSIGNED`` are ``SYNTAX_ERROR``
        code 62 at the word — see :meth:`_refuse_unsigned_numeric`, which is where
        the inventory and the parser output are recorded.  So the branch guards
        caller-supplied DDL, which ``parse_type`` is a documented reader of, and
        says so rather than implying a catalog row is at stake.
        """
        raise UnsupportedFeatureError(
            self.name,
            f"an UNSIGNED attribute on a ClickHouse type name ({raw!r}) "
            f"(ClickHouse expresses signedness in the type NAME and only for "
            f"integers: system.data_type_families on 26.7 resolves every "
            f"'* UNSIGNED' name to a UInt family -- TINYINT/INT1 UNSIGNED -> "
            f"UInt8, SMALLINT UNSIGNED -> UInt16, MEDIUMINT/INT/INTEGER UNSIGNED "
            f"-> UInt32, BIGINT UNSIGNED -> UInt64 -- and has no unsigned float "
            f"or decimal family at all, while Float32, Float64 and Decimal(P, S) "
            f"carry no attribute in their own grammar. 'Int8 UNSIGNED' is "
            f"UNKNOWN_TYPE (code 50) and 'Float32 UNSIGNED', 'Float64 UNSIGNED' "
            f"and 'Decimal(10,2) UNSIGNED' are SYNTAX_ERROR (code 62) at the "
            f"word, so the attribute is not merely absent: there is nowhere to "
            f"put it.)",
            suggestion=(
                "Read the unsigned integer column back as the UInt family that "
                "actually stores it -- 'UInt8', 'UInt16', 'UInt32', 'UInt64', or "
                "the ClickHouseUInt*Type classes. For a float or a decimal there "
                "is no unsigned column to read: declare it signed and enforce "
                "the range with a named table-level 'CONSTRAINT cc CHECK (c >= "
                "0)', which the server enforces (code 469 VIOLATED_CONSTRAINT)."
            ),
        )

    def parse_type(self, raw: str) -> "DataType":
        """Parse a ClickHouse type string back into a ``DataType``.

        One concept in, one class out: every recognised spelling of a concept
        yields the *same* class, so no spelling becomes a synonym class and a
        parsed type compares equal to the declared one that produced it.

        ClickHouse's own spelling vocabulary
        ------------------------------------
        The spellings ClickHouse itself accepts for the concepts this dialect
        models are recognised here, so that ``parse_type`` covers the server's
        own output and the words its documentation lists:

        ``Bool`` / ``BOOLEAN``
            Both are accepted by the server and both reported back as ``Bool``
            (checked against 26.7). Same class either way.

        ``Decimal(P, S)`` / ``NUMERIC(P, S)`` / ``DEC(P, S)``
            All three accepted, all three reported back as ``Decimal(P, S)``.
            That is exactly ``DecimalType.SPELLINGS``.

        ``TINYINT UNSIGNED`` / ``INT1 UNSIGNED`` / ``SMALLINT UNSIGNED`` /
        ``MEDIUMINT UNSIGNED`` / ``INT UNSIGNED`` / ``INTEGER UNSIGNED`` /
        ``BIGINT UNSIGNED`` / ``UNSIGNED`` / ``YEAR``
            The MySQL-style unsigned integer aliases.  The server accepts every
            one of them and resolves each to a ``UInt`` family (measured on
            26.7.3.19; the mapping is recorded in
            ``_CLICKHOUSE_UNSIGNED_INTEGER_ALIASES``), so each yields the
            ``ClickHouseUInt*Type`` that already owns that column — ``YEAR``
            included, which ClickHouse resolves to ``UInt16`` rather than to a
            year type.  ``TINYINT UNSIGNED`` is therefore a real spelling of an
            unsigned column while ``Int8 UNSIGNED`` is not a spelling at all,
            and the two get different answers.

        The rest of the server's alias table is deliberately not claimed.  On
        26.7.3.19 ``system.data_type_families`` lists 73 aliases; ``FLOAT`` and
        ``REAL`` resolve to ``Float32``, ``DOUBLE`` to ``Float64``, ``VARCHAR``,
        ``TEXT`` and ``BLOB`` to ``String``, and the single-word integer aliases
        (``TINYINT``, ``INT``, ``BIGINT``…) to the signed widths.  The server
        accepts every one of those words — ``CREATE TABLE t (a VARCHAR(10))``
        and ``(a TINYINT)`` are measured to succeed and store ``String`` and
        ``Int8`` — but none is a word this parser claims: the vocabulary is the
        native names this dialect renders.  In the type grammar, case decides
        only the native names, and only against their exact spelling: measured
        on 26.7.3.19, ``(a Int8)`` and ``(a String)`` succeed while ``(a INT8)``,
        ``(a int8)`` and ``(a string)`` are rejected with code 50 ``Unknown data
        type family``; the alias words are ``case_insensitive = 1`` and accept
        any case.

        That difference does not reach introspection.  The catalog normalises
        aliases at ``CREATE`` time — ``system.columns`` stores the resolved
        type, not the spelling — so an aliased column comes back in its native
        form (``TINYINT`` -> ``Int8``, ``VARCHAR(10)`` -> ``String``,
        ``TINYINT UNSIGNED`` -> ``UInt8``, ``YEAR`` -> ``UInt16``) and the
        introspection caller only ever hands this parser canonical names.  An
        unclaimed spelling therefore matters for hand-written DDL only, where it
        falls through to :class:`~...types.custom.CustomType`, which this
        dialect cannot render — a reported failure rather than a silently
        written type the caller may not have meant.  What a caller holding such
        a name should use is answered by :meth:`suggested_data_types`, which is
        also what the ``TypeError`` from an unrenderable ``CustomType`` points
        at.

        Known lossiness
        ---------------
        ``DateTime(tz)`` and ``DateTime64(p, tz)`` carry a time zone that
        :class:`ClickHouseDateTimeType` and
        :class:`ClickHouseDateTime64Type` cannot hold, so the zone is dropped and
        the parsed type renders without it. The server reports those forms, so an
        introspected zone-aware column comes back as the server-default zone.
        Carrying the zone is a change to those two classes' identity, and this
        refactor does not change rendering — reported rather than fixed.

        ``QBit(element_type, dimension[, stride])`` loses two of its three
        arguments for the same reason. The ``stride`` is dropped because it is a
        storage detail that does not change what the vector *is*, and
        ``element_type`` is dropped because
        :class:`ClickHouseVectorType` models the dimension only; the formatter
        renders ``Float32``. So a ``QBit(BFloat16, 1536)`` column introspects as
        ``QBit(Float32, 1536)``. The dimension round-trips exactly, which is the
        part that cannot change without rewriting the column. Making
        ``element_type`` part of the class's identity is a wider change than
        correcting a wrong spelling — reported rather than fixed.

        ``UNSIGNED`` as an attribute
            Still refused rather than dropped, and this is the one word in the
            grammar that *looks* like it might belong to a string: the integer,
            float and decimal branches all match on the word in front of it, so
            ``Float32 UNSIGNED`` used to parse to a signed
            :class:`~...types.native.ClickHouseFloat32Type` — a value object
            ``==`` calls equal to the signed column. The MySQL-style aliases
            that carry the same word are the other case: ``TINYINT UNSIGNED``
            and friends name a column, so they are recognised as aliases above,
            while bare ``UNSIGNED`` after a native name is an attribute nothing
            can carry. See :meth:`_refuse_unsigned_type_string`.
        """
        stripped = raw.strip()
        upper = stripped.upper()

        # The MySQL-style unsigned aliases: a closed list of words the server
        # resolves to ``UInt*``.  Checked first because none of them is a word
        # the numeric branches below (or the UNSIGNED-attribute guard after it)
        # claims, and a hit must not reach the ``CustomType`` fallback.
        alias_class = self._CLICKHOUSE_UNSIGNED_INTEGER_ALIASES.get(
            " ".join(upper.split()))
        if alias_class is not None:
            return alias_class(dialect=self)

        if (self._UNSIGNED_ATTRIBUTE.search(stripped)
                and (self._CLICKHOUSE_INTEGER_TYPES.match(upper)
                     or self._CLICKHOUSE_FLOAT_TYPES.match(upper)
                     or self._CLICKHOUSE_DECIMAL_TYPES.match(upper))):
            self._refuse_unsigned_type_string(stripped)

        # Integer family
        if self._CLICKHOUSE_INTEGER_TYPES.match(upper):
            if upper.startswith("INT8"):
                return ClickHouseInt8Type(dialect=self)
            if upper.startswith("INT16"):
                return ClickHouseInt16Type(dialect=self)
            if upper.startswith("INT32"):
                return ClickHouseInt32Type(dialect=self)
            if upper.startswith("INT64"):
                return ClickHouseInt64Type(dialect=self)
            if upper.startswith("UINT8"):
                return ClickHouseUInt8Type(dialect=self)
            if upper.startswith("UINT16"):
                return ClickHouseUInt16Type(dialect=self)
            if upper.startswith("UINT32"):
                return ClickHouseUInt32Type(dialect=self)
            if upper.startswith("UINT64"):
                return ClickHouseUInt64Type(dialect=self)

        # Float family
        if self._CLICKHOUSE_FLOAT_TYPES.match(upper):
            if upper.startswith("FLOAT32"):
                return ClickHouseFloat32Type(dialect=self)
            if upper.startswith("FLOAT64"):
                return ClickHouseFloat64Type(dialect=self)

        # Decimal family
        if self._CLICKHOUSE_DECIMAL_TYPES.match(upper):
            # The digits inside the parentheses are the arguments, never part of
            # the type name: for ``Decimal32(S)`` the ``32`` is the width, so
            # reading the first number out of the whole string would take the
            # width for the scale and produce ``Decimal32(32)`` — or, for
            # ``Decimal64(8)`` / ``Decimal128(18)``, a scale outside the range the
            # constructor accepts, which is a hard failure rather than a wrong
            # value. Take the arguments only.
            inner = self._extract_inner_types(stripped)
            nums = [int(n) for n in re.findall(r"\d+", " ".join(inner))]
            if upper.startswith("DECIMAL32"):
                return ClickHouseDecimal32Type(dialect=self, scale=nums[0] if nums else 0)
            if upper.startswith("DECIMAL64"):
                return ClickHouseDecimal64Type(dialect=self, scale=nums[0] if nums else 0)
            if upper.startswith("DECIMAL128"):
                return ClickHouseDecimal128Type(dialect=self, scale=nums[0] if nums else 0)
            # Decimal(P, S). ClickHouse writes the scale even when it is zero and
            # reports ``Decimal(5)`` as ``Decimal(5, 0)``, so a one-argument
            # declaration is parsed the way the server reports it back.
            precision = nums[0] if nums else 10
            scale = nums[1] if len(nums) > 1 else 0
            return ClickHouseDecimalType(dialect=self, precision=precision, scale=scale)

        # String family
        if self._CLICKHOUSE_STRING_TYPES.match(upper):
            if upper.startswith("FIXEDSTRING"):
                nums = re.findall(r"\d+", stripped)
                length = int(nums[0]) if nums else 1
                return ClickHouseFixedStringType(dialect=self, length=length)
            return ClickHouseStringType(dialect=self)

        # Date / Time family
        if self._CLICKHOUSE_DATE_TYPES.match(upper):
            if upper.startswith("DATETIME64"):
                nums = re.findall(r"\((\d+)\)", stripped)
                precision = int(nums[0]) if nums else 3
                return ClickHouseDateTime64Type(dialect=self, precision=precision)
            if upper.startswith("DATETIME"):
                return ClickHouseDateTimeType(dialect=self)
            if upper.startswith("DATE32"):
                return ClickHouseDate32Type(dialect=self)
            if upper.startswith("DATE"):
                return ClickHouseDateType(dialect=self)

        # Other simple types
        if self._CLICKHOUSE_OTHER_TYPES.match(upper):
            if upper.startswith("BOOL"):
                return ClickHouseBoolType(dialect=self)
            if upper.startswith("UUID"):
                return ClickHouseUUIDType(dialect=self)
            if upper.startswith("IPV4"):
                return ClickHouseIPv4Type(dialect=self)
            if upper.startswith("IPV6"):
                return ClickHouseIPv6Type(dialect=self)
            if upper.startswith("JSON"):
                return ClickHouseJSONType(dialect=self)

        # Enum types
        if self._CLICKHOUSE_ENUM_TYPES.match(upper):
            pairs = re.findall(r"'([^']*)'\s*=\s*(-?\d+)", stripped)
            # ClickHouse orders the labels of an enum by the integer assigned to
            # each, not by the order they were declared in, and rewrites the
            # declaration to match: a 26.7 server reports
            # ``Enum8('x' = 1, 'y' = -2)`` back as ``Enum8('y' = -2, 'x' = 1)``.
            # Sorting here is what makes an introspected enum equal to the
            # declared one that produced it, instead of a schema diff reporting
            # a change that is not there.
            values = sorted(
                ((name, int(num)) for name, num in pairs),
                key=lambda pair: pair[1],
            )
            if upper.startswith("ENUM8"):
                return ClickHouseEnum8Type(dialect=self, values=values)
            return ClickHouseEnum16Type(dialect=self, values=values)

        # Container types
        if self._CLICKHOUSE_CONTAINER_TYPES.match(upper):
            # Extract inner type(s) from parentheses
            inner = self._extract_inner_types(stripped)
            if upper.startswith("ARRAY") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseArrayType(dialect=self, element_type=inner_type)
            if upper.startswith("MAP") and len(inner) >= 2:
                key_type = self.parse_type(inner[0])
                val_type = self.parse_type(inner[1])
                return ClickHouseMapType(dialect=self, key_type=key_type, value_type=val_type)
            if upper.startswith("TUPLE") and inner:
                # Each element may carry a field name: ClickHouse writes
                # ``Tuple(name Type, ...)``, and on 26.7.3.19 the names are
                # part of the type's identity -- stored, reported, compared,
                # used for ``tuple.name`` and INSERT matching (see the class
                # docstring for the evidence). Feeding ``"name Type"`` to
                # ``parse_type`` whole fell through to CustomType, whose
                # type-name validation refused the space -- so the word this
                # dialect renders was the one its own parse raised on. Split
                # the leading identifier off when a second word follows; the
                # names are carried into ``element_names`` so the round trip
                # keeps them, which is why the class records them in
                # PARAMETERS.
                types = []
                names = []
                named = False
                for part in inner:
                    words = part.split(None, 1)
                    if (len(words) == 2
                            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", words[0])):
                        names.append(words[0])
                        types.append(self.parse_type(words[1]))
                        named = True
                    else:
                        names.append(None)
                        types.append(self.parse_type(part))
                if named:
                    return ClickHouseTupleType(
                        dialect=self, element_types=types,
                        element_names=names)
                return ClickHouseTupleType(dialect=self, element_types=types)
            if upper.startswith("NULLABLE") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseNullableType(dialect=self, inner_type=inner_type)
            if upper.startswith("LOWCARDINALITY") and inner:
                inner_type = self.parse_type(inner[0])
                return ClickHouseLowCardinalityType(dialect=self, inner_type=inner_type)

        # AggregateFunction
        if self._CLICKHOUSE_AGGREGATE_TYPES.match(upper):
            inner = self._extract_inner_types(stripped)
            if inner:
                func_name = inner[0]
                arg_types = [self.parse_type(t) for t in inner[1:]]
                if upper.startswith("SIMPLEAGGREGATEFUNCTION"):
                    return ClickHouseSimpleAggregateFunctionType(
                        dialect=self, function_name=func_name, arg_types=arg_types)
                return ClickHouseAggregateFunctionType(dialect=self, function_name=func_name, arg_types=arg_types)

        # Spatial
        if self._CLICKHOUSE_SPATIAL_TYPES.match(upper):
            srid = None
            srid_match = re.search(r"SRID\s+(\d+)", upper)
            if srid_match:
                srid = int(srid_match.group(1))
            spatial_map = {
                "GEOMETRY": ClickHouseGeometryType,
                "POINT": ClickHousePointType,
                "LINESTRING": ClickHouseLineStringType,
                "POLYGON": ClickHousePolygonType,
                "MULTIPOINT": ClickHouseMultiPointType,
                "MULTILINESTRING": ClickHouseMultiLineStringType,
                "MULTIPOLYGON": ClickHouseMultiPolygonType,
                "GEOMETRYCOLLECTION": ClickHouseGeometryCollectionType,
            }
            # Dispatch on the leading **word**, not on a prefix scanned in
            # declaration order. ``GEOMETRYCOLLECTION`` begins with
            # ``GEOMETRY``, and the map put ``GEOMETRY`` first, so the
            # ``startswith`` loop read a collection column as the generic
            # geometry type -- the same defect MariaDB's and MySQL's
            # branches of this family each found and fixed, found here by
            # the render-parse-re-render sweep. Every one of the eight words
            # is a single identifier, so the leading word is the whole name.
            head = re.match(r"[A-Z]+", upper)
            word = head.group(0) if head else upper
            return spatial_map.get(word, ClickHouseGeometryType)(
                dialect=self, srid=srid)
            return ClickHouseGeometryType(dialect=self, srid=srid)

        # Vector: QBit(element_type, dimension[, stride]).
        #
        # The dimension is the first argument that is a *bare* integer. Scanning
        # for any digit run instead would read the "32" out of "Float32" and
        # report a QBit(Float32, 8) column as 32-dimensional — and the element
        # type is not modelled by ClickHouseVectorType, so it is deliberately not
        # matched here either. A strided QBit(Float32, 16, 8) still yields 16.
        if self._CLICKHOUSE_VECTOR_TYPES.match(upper):
            inner = ""
            if "(" in stripped and ")" in stripped:
                inner = stripped[stripped.index("(") + 1: stripped.rindex(")")]
            dim = next(
                (int(arg.strip()) for arg in inner.split(",") if arg.strip().isdigit()),
                0,
            )
            return ClickHouseVectorType(dialect=self, dim=dim)

        # Fallback: a type name this dialect does not know. It is a
        # ``CustomType`` because that is honest — the framework has no class for
        # it — but rendering one will raise, and that is the point rather than an
        # oversight: an unclaimed name may be one ClickHouse rejects outright, or
        # one it accepts as an alias (``VARCHAR(10)`` means ``String``), so
        # writing ``data_type.raw`` back out would either fail at the server or
        # silently store a type the caller may not have meant. There is no
        # ``format_data_type_custom`` here, and
        # ``suggested_data_types()["custom"]`` names ``ClickHouseStringType`` so
        # the ``TypeError`` says what to use instead.
        from rhosocial.activerecord.backend.expression.types import CustomType
        return CustomType(dialect=self, raw=stripped)

    @staticmethod
    def _extract_inner_types(raw: str) -> list:
        """Extract comma-separated type arguments from the outermost parentheses.

        Handles nested parentheses like ``Array(Nullable(Int32))``.
        """
        start = raw.find("(")
        if start == -1:
            return []
        depth = 0
        parts = []
        current = []
        for ch in raw[start + 1:]:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current).strip())
        return parts
