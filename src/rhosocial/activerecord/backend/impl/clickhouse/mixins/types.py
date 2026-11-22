# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/types.py
"""ClickHouse DataType formatting mixin.

Reading a server-reported type spelling back into a ``DataType`` is an
introspection-only concern; it lives in ``introspection/type_parser.py`` as
``ClickHouseTypeParser`` and is deliberately not a dialect protocol member.
"""

from __future__ import annotations

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.data_type import DataTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DataTypeSupport
from rhosocial.activerecord.backend.suggestion.definitions import (
    SubstituteAdviceSuggestion,
    SubstituteTypeSuggestion,
)
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
    """ClickHouse DataType formatting.

    Implements ``DataTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings. Reading a server-reported type spelling back
    into a ``DataType`` is an introspection-only concern handled by
    ``ClickHouseTypeParser`` in ``introspection/type_parser.py``.

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

        The shape check runs first, and this is the only gate there is: the
        expression collects ``unsigned`` without judging it, because only the
        formatter knows which backend must honour it, so a non-boolean arrives
        here rather than being rejected at construction.  A truth test cannot
        see it — ``unsigned=0``, ``unsigned=""`` and ``unsigned=None`` are all
        falsy, so they would pass the test below and render a signed ``Int8``
        (or a core ``TINYINT``) while reporting success.  ``bool`` is also the
        only shape that means what the field says: the flag *is* the identity,
        so ``"yes"`` and ``1`` are not spellings of ``True`` but wrong values.
        """
        unsigned = data_type.unsigned
        if not isinstance(unsigned, bool):
            raise TypeError(
                f"unsigned must be a bool, got {type(unsigned).__name__}; it "
                f"becomes a type modifier in the rendered DDL."
            )
        if not unsigned:
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

        The shape check is first for the reason given in
        :meth:`_refuse_unsigned_integer`, and it covers the same four numeric
        concepts through their own dispatch keys: a non-boolean reaches this
        gate unjudged, and a falsy one — ``0``, ``""``, ``None``, an empty
        container — is invisible to the truth test below, so it would render a
        signed ``Float32`` / ``Float64`` / ``Decimal(P, S)`` and report success.
        """
        unsigned = data_type.unsigned
        if not isinstance(unsigned, bool):
            raise TypeError(
                f"unsigned must be a bool, got {type(unsigned).__name__}; it "
                f"becomes a type modifier in the rendered DDL."
            )
        if not unsigned:
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

    def format_data_type_clickhouse_int8(self, expr: ClickHouseInt8Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int8`` — the signed 8-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`, which is also where the reason is
        written down.
        """
        self._refuse_unsigned_integer(expr, "Int8", "ClickHouseUInt8Type")
        return "Int8", ()

    def format_data_type_clickhouse_int16(self, expr: ClickHouseInt16Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int16`` — the signed 16-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`.
        """
        self._refuse_unsigned_integer(expr, "Int16", "ClickHouseUInt16Type")
        return "Int16", ()

    def format_data_type_clickhouse_int32(self, expr: ClickHouseInt32Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int32`` — the signed 32-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`.
        """
        self._refuse_unsigned_integer(expr, "Int32", "ClickHouseUInt32Type")
        return "Int32", ()

    def format_data_type_clickhouse_int64(self, expr: ClickHouseInt64Type) -> Tuple[str, tuple]:
        """ClickHouse ``Int64`` — the signed 64-bit integer.

        ``unsigned=True`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`.
        """
        self._refuse_unsigned_integer(expr, "Int64", "ClickHouseUInt64Type")
        return "Int64", ()

    def format_data_type_clickhouse_uint8(self, expr: ClickHouseUInt8Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt8`` — the unsigned 8-bit integer, [0 : 255].

        The unsigned form is a *class* on this backend, so there is nothing to
        refuse here: :class:`ClickHouseUInt8Type` pins ``unsigned=True`` in its own
        ``__init__`` and takes no flag, which means this formatter cannot be reached
        with ``unsigned=False``.
        """
        return "UInt8", ()

    def format_data_type_clickhouse_uint16(self, expr: ClickHouseUInt16Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt16`` — the unsigned 16-bit integer.

        See :meth:`format_data_type_clickhouse_uint8` for why ``unsigned`` cannot
        arrive here.
        """
        return "UInt16", ()

    def format_data_type_clickhouse_uint32(self, expr: ClickHouseUInt32Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt32`` — the unsigned 32-bit integer.

        See :meth:`format_data_type_clickhouse_uint8` for why ``unsigned`` cannot
        arrive here.
        """
        return "UInt32", ()

    def format_data_type_clickhouse_uint64(self, expr: ClickHouseUInt64Type) -> Tuple[str, tuple]:
        """ClickHouse ``UInt64`` — the unsigned 64-bit integer.

        See :meth:`format_data_type_clickhouse_uint8` for why ``unsigned`` cannot
        arrive here.
        """
        return "UInt64", ()

    def format_data_type_clickhouse_float32(self, expr: ClickHouseFloat32Type) -> Tuple[str, tuple]:
        return "Float32", ()

    def format_data_type_clickhouse_float64(self, expr: ClickHouseFloat64Type) -> Tuple[str, tuple]:
        return "Float64", ()

    def format_data_type_clickhouse_decimal(self, expr: ClickHouseDecimalType) -> Tuple[str, tuple]:
        return f"Decimal({expr.precision}, {expr.scale})", ()

    def format_data_type_clickhouse_decimal32(self, expr: ClickHouseDecimal32Type) -> Tuple[str, tuple]:
        return f"Decimal32({expr.scale})", ()

    def format_data_type_clickhouse_decimal64(self, expr: ClickHouseDecimal64Type) -> Tuple[str, tuple]:
        return f"Decimal64({expr.scale})", ()

    def format_data_type_clickhouse_decimal128(self, expr: ClickHouseDecimal128Type) -> Tuple[str, tuple]:
        return f"Decimal128({expr.scale})", ()

    def format_data_type_clickhouse_string(self, expr: ClickHouseStringType) -> Tuple[str, tuple]:
        return "String", ()

    def format_data_type_clickhouse_fixed_string(self, expr: ClickHouseFixedStringType) -> Tuple[str, tuple]:
        return f"FixedString({expr.length})", ()

    def format_data_type_clickhouse_date(self, expr: ClickHouseDateType) -> Tuple[str, tuple]:
        return "Date", ()

    def format_data_type_clickhouse_date32(self, expr: ClickHouseDate32Type) -> Tuple[str, tuple]:
        return "Date32", ()

    def format_data_type_clickhouse_timestamp(self, expr: ClickHouseDateTimeType) -> Tuple[str, tuple]:
        return "DateTime", ()

    def format_data_type_clickhouse_timestamp64(self, expr: ClickHouseDateTime64Type) -> Tuple[str, tuple]:
        return f"DateTime64({expr.precision})", ()

    def format_data_type_clickhouse_bool(self, expr: ClickHouseBoolType) -> Tuple[str, tuple]:
        return "Bool", ()

    def format_data_type_clickhouse_uuid(self, expr: ClickHouseUUIDType) -> Tuple[str, tuple]:
        return "UUID", ()

    def format_data_type_clickhouse_ipv4(self, expr: ClickHouseIPv4Type) -> Tuple[str, tuple]:
        return "IPv4", ()

    def format_data_type_clickhouse_ipv6(self, expr: ClickHouseIPv6Type) -> Tuple[str, tuple]:
        return "IPv6", ()

    def format_data_type_clickhouse_enum8(self, expr: ClickHouseEnum8Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in expr.values)
        return f"Enum8({values_str})", ()

    def format_data_type_clickhouse_enum16(self, expr: ClickHouseEnum16Type) -> Tuple[str, tuple]:
        values_str = ", ".join(f"'{name}' = {num}" for name, num in expr.values)
        return f"Enum16({values_str})", ()

    def format_data_type_clickhouse_array(self, expr: ClickHouseArrayType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(expr.element_type)
        return f"Array({inner_sql})", inner_params

    def format_data_type_clickhouse_map(self, expr: ClickHouseMapType) -> Tuple[str, tuple]:
        key_sql, key_params = self.format_data_type(expr.key_type)
        val_sql, val_params = self.format_data_type(expr.value_type)
        return f"Map({key_sql}, {val_sql})", key_params + val_params

    def format_data_type_clickhouse_tuple(self, expr: ClickHouseTupleType) -> Tuple[str, tuple]:
        parts = []
        params = []
        for i, elem_type in enumerate(expr.element_types):
            elem_sql, elem_params = self.format_data_type(elem_type)
            if expr.element_names:
                parts.append(f"{expr.element_names[i]} {elem_sql}")
            else:
                parts.append(elem_sql)
            params.extend(elem_params)
        return f"Tuple({', '.join(parts)})", tuple(params)

    def format_data_type_clickhouse_nullable(self, expr: ClickHouseNullableType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(expr.inner_type)
        return f"Nullable({inner_sql})", inner_params

    def format_data_type_clickhouse_low_cardinality(self, expr: ClickHouseLowCardinalityType) -> Tuple[str, tuple]:
        inner_sql, inner_params = self.format_data_type(expr.inner_type)
        return f"LowCardinality({inner_sql})", inner_params

    def format_data_type_clickhouse_json(self, expr: ClickHouseJSONType) -> Tuple[str, tuple]:
        return "JSON", ()

    def format_data_type_clickhouse_aggregate_function(
        self,
        expr: ClickHouseAggregateFunctionType,
    ) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in expr.arg_types)
        return f"AggregateFunction({expr.function_name}, {args})", ()

    def format_data_type_clickhouse_simple_aggregate_function(
        self, expr: ClickHouseSimpleAggregateFunctionType
    ) -> Tuple[str, tuple]:
        args = ", ".join(self.format_data_type(t)[0] for t in expr.arg_types)
        return f"SimpleAggregateFunction({expr.function_name}, {args})", ()

    def format_data_type_clickhouse_geometry(self, expr: ClickHouseGeometryType) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"GEOMETRY SRID {expr.srid}", ()
        return "GEOMETRY", ()

    def format_data_type_clickhouse_point(self, expr: ClickHousePointType) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"POINT SRID {expr.srid}", ()
        return "POINT", ()

    def format_data_type_clickhouse_linestring(self, expr: ClickHouseLineStringType) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"LINESTRING SRID {expr.srid}", ()
        return "LINESTRING", ()

    def format_data_type_clickhouse_polygon(self, expr: ClickHousePolygonType) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"POLYGON SRID {expr.srid}", ()
        return "POLYGON", ()

    def format_data_type_clickhouse_multipoint(self, expr: ClickHouseMultiPointType) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"MULTIPOINT SRID {expr.srid}", ()
        return "MULTIPOINT", ()

    def format_data_type_clickhouse_multilinestring(
        self,
        expr: ClickHouseMultiLineStringType,
    ) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"MULTILINESTRING SRID {expr.srid}", ()
        return "MULTILINESTRING", ()

    def format_data_type_clickhouse_multipolygon(self, expr: ClickHouseMultiPolygonType) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"MULTIPOLYGON SRID {expr.srid}", ()
        return "MULTIPOLYGON", ()

    def format_data_type_clickhouse_geometrycollection(
        self,
        expr: ClickHouseGeometryCollectionType,
    ) -> Tuple[str, tuple]:
        if expr.srid is not None:
            return f"GEOMETRYCOLLECTION SRID {expr.srid}", ()
        return "GEOMETRYCOLLECTION", ()

    def format_data_type_clickhouse_vector(self, expr: ClickHouseVectorType) -> Tuple[str, tuple]:
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
        return f"QBit(Float32, {expr.dim})", ()

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
    # DataTypeSuggestionSupport — suggest_substitute_types()
    # ------------------------------------------------------------------

    def suggest_substitute_types(self) -> SubstituteTypeSuggestion:
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
        return SubstituteTypeSuggestion(mapping={
            "binary": ClickHouseStringType,
            "varbinary": ClickHouseStringType,
            "custom": ClickHouseStringType,
            "enum": ClickHouseStringType,
            "interval": ClickHouseInt64Type,
            "jsonb": ClickHouseStringType,
            "timetz": ClickHouseDateTimeType,
            "timestamptz": ClickHouseDateTime64Type,
            "xml": TextType,
        })

    def suggest_substitute_advice(self, name: str) -> SubstituteAdviceSuggestion:
        """No extra caveat: every substitute above is already explained in its docstring."""
        return SubstituteAdviceSuggestion(advice="")

    # --- Core types (pure names) rendered to real ClickHouse SQL ---

    def format_data_type_integer(self, expr: IntegerType) -> Tuple[str, tuple]:
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
        self._check_spelling(expr, IntegerType)
        self._refuse_unsigned_integer(expr, "Int32", "ClickHouseUInt32Type")
        return "Int32", ()

    def format_data_type_bigint(self, expr: BigIntType) -> Tuple[str, tuple]:
        """``BIGINT`` and ``INT8`` are the standard's and PostgreSQL's spellings of
        the 8-byte signed integer. ClickHouse writes ``Int64`` and has no other
        word for it; both spellings are accepted and render as written above.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`."""
        self._check_spelling(expr, BigIntType)
        self._refuse_unsigned_integer(expr, "Int64", "ClickHouseUInt64Type")
        return "Int64", ()

    def format_data_type_smallint(self, expr: SmallIntType) -> Tuple[str, tuple]:
        """``SMALLINT`` / ``INT2`` — the 2-byte signed integer, which ClickHouse
        spells ``Int16``. Both spellings accepted.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`."""
        self._check_spelling(expr, SmallIntType)
        self._refuse_unsigned_integer(expr, "Int16", "ClickHouseUInt16Type")
        return "Int16", ()

    def format_data_type_tinyint(self, expr: TinyIntType) -> Tuple[str, tuple]:
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
        self._check_spelling(expr, TinyIntType)
        self._refuse_unsigned_integer(expr, "Int8", "ClickHouseUInt8Type")
        return "Int8", ()

    def format_data_type_varchar(self, expr: VarCharType) -> Tuple[str, tuple]:
        """ClickHouse has no length-bounded character type: ``String`` is
        variable-length and unpadded, so the declared length is dropped. Both
        ``VARCHAR`` and ``CHARACTER VARYING`` are accepted for the same reason as
        the integer spellings — the concept was asked for and this is its only
        storage."""
        self._check_spelling(expr, VarCharType)
        return "String", ()

    def format_data_type_char(self, expr: CharType) -> Tuple[str, tuple]:
        """``CHAR`` / ``CHARACTER`` — a fixed-length character string.

        Rendered ``String``, which is a **widening**, and the caller should know
        it: ClickHouse has no fixed-width character type, so a ``CHAR(10)`` column
        becomes an unbounded one. ``ClickHouseFixedStringType`` is the fixed-length
        type on this backend, but it is a fixed number of *bytes*, zero-padded —
        a different concept, so it is not what a generic ``CharType`` silently
        becomes. Both spellings are accepted for the reason given on
        :meth:`format_data_type_varchar`.
        """
        self._check_spelling(expr, CharType)
        return "String", ()

    def format_data_type_text(self, expr: TextType) -> Tuple[str, tuple]:
        """``TEXT`` / ``CLOB`` — unbounded text, which is ``String``.

        ``CLOB`` is not a ClickHouse word, but it is the concept's own second
        spelling and ``String`` is the concept's only storage here, so it is
        accepted rather than refused.
        """
        self._check_spelling(expr, TextType)
        return "String", ()

    def format_data_type_boolean(self, expr: BooleanType) -> Tuple[str, tuple]:
        """``BOOLEAN`` / ``BOOL`` — and both are ClickHouse's own words.

        Verified against the 26.7 scenario server: ``CREATE TABLE t (b BOOLEAN)``
        and ``(b Bool)`` are both accepted and both reported back as ``Bool``, so
        this is the one concept whose core spelling list happens to be exactly
        ClickHouse's vocabulary.
        """
        self._check_spelling(expr, BooleanType)
        return "Bool", ()

    def format_data_type_date(self, expr: DateType) -> Tuple[str, tuple]:
        """``DATE`` — ClickHouse's own ``Date``, 1970..2149 in two bytes.

        Deliberately *not* ``Date32``: the wider range is a different storage and
        a different type to the server, and silently choosing it would change the
        range a column accepts. ``ClickHouseDate32Type`` is available for that.
        """
        return "Date", ()

    def format_data_type_datetime(self, expr: DateTimeType) -> Tuple[str, tuple]:
        """``DATETIME`` — MySQL's wall-clock date and time.

        ClickHouse has no such type; its ``DateTime`` is a count of seconds since
        the epoch. The nearest storage is ``DateTime``, and the difference is
        visible: a ``DATETIME`` value has no epoch to convert against, so on this
        backend it is stored as an instant. ``format_data_type_timestamp`` renders
        the same word for core's ``TIMESTAMP``, which is the same storage and the
        honest reading of it.
        """
        return "DateTime", ()

    def format_data_type_timestamp(self, expr: TimestampType) -> Tuple[str, tuple]:
        """``TIMESTAMP`` — an instant, which is what ClickHouse's ``DateTime`` is.

        A declared sub-second precision is honoured as ``DateTime64(p)``
        (``p`` = 0..9); without one the plain ``DateTime`` (whole seconds) is
        rendered. Dropping a requested precision would make the column narrower
        than the type the caller asked for, and a value written through it would
        come back truncated — so the precision is rendered, not discarded.
        ``ClickHouseDateTime64Type`` is the type that carries that parameter.
        """
        precision = getattr(expr, "precision", None)
        if precision is None:
            return "DateTime", ()
        if (
            isinstance(precision, bool)
            or not isinstance(precision, int)
            or not 0 <= precision <= 9
        ):
            raise ValueError(
                f"TIMESTAMP precision must be an integer in 0..9, got {precision!r}"
            )
        return self.format_data_type_clickhouse_timestamp64(
            ClickHouseDateTime64Type(precision=precision)
        )

    def format_data_type_time(self, expr: TimeType) -> Tuple[str, tuple]:
        """``TIME`` — time of day, with no date attached.

        ClickHouse has no time-only type; the closest storage is ``DateTime``,
        which is what is rendered. A column declared ``TIME`` on this backend
        therefore holds an instant, not a time of day. ``timetz`` is not rendered
        at all — see :meth:`suggest_substitute_types`.
        """
        return "DateTime", ()

    def format_data_type_float(self, expr: FloatType) -> Tuple[str, tuple]:
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
        self._refuse_unsigned_numeric(expr, "Float32")
        return "Float32", ()

    def format_data_type_double(self, expr: DoubleType) -> Tuple[str, tuple]:
        """``DOUBLE`` / ``DOUBLE PRECISION`` — the 8-byte float, ``Float64``.

        Both spellings accepted; the concept's default spelling is ``double``, so
        it must render, and the long form names the same 53-bit mantissa.

        ``unsigned`` is refused rather than ignored, before the spelling check;
        see :meth:`_refuse_unsigned_numeric`.
        """
        self._refuse_unsigned_numeric(expr, "Float64")
        self._check_spelling(expr, DoubleType)
        return "Float64", ()

    def format_data_type_real(self, expr: RealType) -> Tuple[str, tuple]:
        """``REAL`` — single precision. ClickHouse's word for it is ``Float32``,
        which is also what ``FLOAT`` renders, because ClickHouse has no separate
        ``REAL`` family.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_numeric`.
        """
        self._refuse_unsigned_numeric(expr, "Float32")
        return "Float32", ()

    def format_data_type_decimal(self, expr: DecimalType) -> Tuple[str, tuple]:
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
        self._refuse_unsigned_numeric(expr, "Decimal(P, S)")
        self._check_spelling(expr, DecimalType)
        p = expr.precision
        s = expr.scale
        if p is not None and s is not None:
            return f"Decimal({p}, {s})", ()
        if p is not None:
            return f"Decimal({p})", ()
        return "Decimal(10, 0)", ()

    def format_data_type_json(self, expr: JsonType) -> Tuple[str, tuple]:
        """``JSON`` — rendered ``String``, not ClickHouse's native ``JSON``.

        The native type exists (``ClickHouseJSONType`` renders it) but it arrived
        in 24.10 and this dialect does not check the server version for it, so
        the portable column is a byte string and a caller who wants the native
        type asks for ``ClickHouseJSONType`` by name. Reporting this honestly
        matters: a native ``JSON`` column knows its paths and ``JSONExtract``
        reads a field without parsing the value, and a ``String`` column does not.
        """
        return "String", ()

    def format_data_type_blob(self, expr: BlobType) -> Tuple[str, tuple]:
        """``BLOB`` / ``BYTEA`` — a byte string, which is ClickHouse's ``String``.

        Both spellings accepted: ``BYTEA`` is PostgreSQL's word and ``BLOB`` is
        the concept's default, and ``String`` is the concept's only unbounded byte
        storage on this backend.

        Not ``FixedString``: there is no length to honour, and ``FixedString``
        zero-pads, so using it here would change the value.
        """
        self._check_spelling(expr, BlobType)
        return "String", ()

    def format_data_type_uuid(self, expr: UUIDType) -> Tuple[str, tuple]:
        """``UUID`` — ClickHouse has a type with that exact name and meaning.

        128 bits, stored as two 64-bit halves. ``ClickHouseUUIDType`` renders the
        same SQL through its own namespaced name; both are the UUID concept, one
        reached through the core type and one through the backend's.
        """
        return "UUID", ()

    def format_data_type_array(self, expr: ArrayType) -> Tuple[str, tuple]:
        """``T[]`` — ClickHouse's ``Array(T)``, always one dimension.

        ClickHouse has no multi-dimensional array syntax, so ``dimensions > 1``
        is rendered as a single level rather than rejected: a nested
        ``Array(Array(T))`` is the same value, and this is the documented
        ClickHouse spelling for it.
        """
        inner_sql, inner_params = self.format_data_type(expr.element_type)
        return f"Array({inner_sql})", inner_params
