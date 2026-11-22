# src/rhosocial/activerecord/backend/impl/clickhouse/introspection/type_parser.py
"""ClickHouse type-spelling parser (read direction, introspection-only).

Reading a server-reported type string back into a ``DataType`` is not an
expression-construction concern and is not a dialect protocol member. This
backend-local helper is used only when introspection reads a column's declared
type; the dialect no longer exposes a parsing hook.
"""
import re
from typing import Dict

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.types import CustomType, DataType
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
    ClickHouseEnum8Type,
    ClickHouseEnum16Type,
    ClickHouseFixedStringType,
    ClickHouseFloat32Type,
    ClickHouseFloat64Type,
    ClickHouseGeometryCollectionType,
    ClickHouseGeometryType,
    ClickHouseIPv4Type,
    ClickHouseIPv6Type,
    ClickHouseInt8Type,
    ClickHouseInt16Type,
    ClickHouseInt32Type,
    ClickHouseInt64Type,
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
    ClickHouseUInt8Type,
    ClickHouseUInt16Type,
    ClickHouseUInt32Type,
    ClickHouseUInt64Type,
    ClickHouseUUIDType,
    ClickHouseVectorType,
)


class ClickHouseTypeParser:
    """Parse a raw ClickHouse type spelling into a ``DataType``, bound to a dialect."""

    def __init__(self, dialect):
        self.dialect = dialect

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

        :meth:`ClickHouseTypeSupportMixin._refuse_unsigned_numeric` closes the door on the way *in* — a
        declaration.  This closes it on the way *out*: a string.  Without it the
        three numeric branches below match on the word *in front of* the attribute
        and return a signed type — ``parse("Float32 UNSIGNED")`` was
        ``ClickHouseFloat32Type()`` and ``parse("Decimal(10,2) UNSIGNED")``
        was ``ClickHouseDecimalType(10, 2)`` — so a string saying ``UNSIGNED``
        produced a value object that ``==`` calls equal to the signed column.  The
        differ would then report no change for the one change the string
        describes.

        It is checked *here*, at the head of ``parse``, and only for a string
        whose head a numeric branch would claim.  The MySQL-style integer aliases
        ClickHouse genuinely accepts (``TINYINT UNSIGNED`` and friends, which the
        server resolves to ``UInt8``…``UInt64``) are not attributes and are not
        caught here: ``_CLICKHOUSE_UNSIGNED_INTEGER_ALIASES`` recognises them
        before the numeric branches and returns the ``UInt`` class they name.

        No server can have written the strings this refuses: ``Int8 UNSIGNED`` is
        ``UNKNOWN_TYPE`` code 50 on 26.7 and ``Float32 UNSIGNED`` /
        ``Float64 UNSIGNED`` / ``Decimal(10,2) UNSIGNED`` are ``SYNTAX_ERROR``
        code 62 at the word — see :meth:`ClickHouseTypeSupportMixin._refuse_unsigned_numeric`, which is where
        the inventory and the parser output are recorded.  So the branch guards
        caller-supplied DDL, which ``parse`` is a documented reader of, and
        says so rather than implying a catalog row is at stake.
        """
        raise UnsupportedFeatureError(
            self.dialect.name,
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

    def parse(self, raw: str) -> "DataType":
        """Parse a ClickHouse type string back into a ``DataType``.

        One concept in, one class out: every recognised spelling of a concept
        yields the *same* class, so no spelling becomes a synonym class and a
        parsed type compares equal to the declared one that produced it.

        ClickHouse's own spelling vocabulary
        ------------------------------------
        The spellings ClickHouse itself accepts for the concepts this dialect
        models are recognised here, so that ``parse`` covers the server's
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
        a name should use is answered by :meth:`suggest_substitute_types`, which is
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
            return alias_class(dialect=self.dialect)

        if (self._UNSIGNED_ATTRIBUTE.search(stripped)
                and (self._CLICKHOUSE_INTEGER_TYPES.match(upper)
                     or self._CLICKHOUSE_FLOAT_TYPES.match(upper)
                     or self._CLICKHOUSE_DECIMAL_TYPES.match(upper))):
            self._refuse_unsigned_type_string(stripped)

        # Integer family
        if self._CLICKHOUSE_INTEGER_TYPES.match(upper):
            if upper.startswith("INT8"):
                return ClickHouseInt8Type(dialect=self.dialect)
            if upper.startswith("INT16"):
                return ClickHouseInt16Type(dialect=self.dialect)
            if upper.startswith("INT32"):
                return ClickHouseInt32Type(dialect=self.dialect)
            if upper.startswith("INT64"):
                return ClickHouseInt64Type(dialect=self.dialect)
            if upper.startswith("UINT8"):
                return ClickHouseUInt8Type(dialect=self.dialect)
            if upper.startswith("UINT16"):
                return ClickHouseUInt16Type(dialect=self.dialect)
            if upper.startswith("UINT32"):
                return ClickHouseUInt32Type(dialect=self.dialect)
            if upper.startswith("UINT64"):
                return ClickHouseUInt64Type(dialect=self.dialect)

        # Float family
        if self._CLICKHOUSE_FLOAT_TYPES.match(upper):
            if upper.startswith("FLOAT32"):
                return ClickHouseFloat32Type(dialect=self.dialect)
            if upper.startswith("FLOAT64"):
                return ClickHouseFloat64Type(dialect=self.dialect)

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
                return ClickHouseDecimal32Type(dialect=self.dialect, scale=nums[0] if nums else 0)
            if upper.startswith("DECIMAL64"):
                return ClickHouseDecimal64Type(dialect=self.dialect, scale=nums[0] if nums else 0)
            if upper.startswith("DECIMAL128"):
                return ClickHouseDecimal128Type(dialect=self.dialect, scale=nums[0] if nums else 0)
            # Decimal(P, S). ClickHouse writes the scale even when it is zero and
            # reports ``Decimal(5)`` as ``Decimal(5, 0)``, so a one-argument
            # declaration is parsed the way the server reports it back.
            precision = nums[0] if nums else 10
            scale = nums[1] if len(nums) > 1 else 0
            return ClickHouseDecimalType(dialect=self.dialect, precision=precision, scale=scale)

        # String family
        if self._CLICKHOUSE_STRING_TYPES.match(upper):
            if upper.startswith("FIXEDSTRING"):
                nums = re.findall(r"\d+", stripped)
                length = int(nums[0]) if nums else 1
                return ClickHouseFixedStringType(dialect=self.dialect, length=length)
            return ClickHouseStringType(dialect=self.dialect)

        # Date / Time family
        if self._CLICKHOUSE_DATE_TYPES.match(upper):
            if upper.startswith("DATETIME64"):
                nums = re.findall(r"\((\d+)\)", stripped)
                precision = int(nums[0]) if nums else 3
                return ClickHouseDateTime64Type(dialect=self.dialect, precision=precision)
            if upper.startswith("DATETIME"):
                return ClickHouseDateTimeType(dialect=self.dialect)
            if upper.startswith("DATE32"):
                return ClickHouseDate32Type(dialect=self.dialect)
            if upper.startswith("DATE"):
                return ClickHouseDateType(dialect=self.dialect)

        # Other simple types
        if self._CLICKHOUSE_OTHER_TYPES.match(upper):
            if upper.startswith("BOOL"):
                return ClickHouseBoolType(dialect=self.dialect)
            if upper.startswith("UUID"):
                return ClickHouseUUIDType(dialect=self.dialect)
            if upper.startswith("IPV4"):
                return ClickHouseIPv4Type(dialect=self.dialect)
            if upper.startswith("IPV6"):
                return ClickHouseIPv6Type(dialect=self.dialect)
            if upper.startswith("JSON"):
                return ClickHouseJSONType(dialect=self.dialect)

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
                return ClickHouseEnum8Type(dialect=self.dialect, values=values)
            return ClickHouseEnum16Type(dialect=self.dialect, values=values)

        # Container types
        if self._CLICKHOUSE_CONTAINER_TYPES.match(upper):
            # Extract inner type(s) from parentheses
            inner = self._extract_inner_types(stripped)
            if upper.startswith("ARRAY") and inner:
                inner_type = self.parse(inner[0])
                return ClickHouseArrayType(dialect=self.dialect, element_type=inner_type)
            if upper.startswith("MAP") and len(inner) >= 2:
                key_type = self.parse(inner[0])
                val_type = self.parse(inner[1])
                return ClickHouseMapType(dialect=self.dialect, key_type=key_type, value_type=val_type)
            if upper.startswith("TUPLE") and inner:
                # Each element may carry a field name: ClickHouse writes
                # ``Tuple(name Type, ...)``, and on 26.7.3.19 the names are
                # part of the type's identity -- stored, reported, compared,
                # used for ``tuple.name`` and INSERT matching (see the class
                # docstring for the evidence). Feeding ``"name Type"`` to
                # ``parse`` whole fell through to CustomType, whose
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
                        types.append(self.parse(words[1]))
                        named = True
                    else:
                        names.append(None)
                        types.append(self.parse(part))
                if named:
                    return ClickHouseTupleType(
                        dialect=self.dialect, element_types=types,
                        element_names=names)
                return ClickHouseTupleType(dialect=self.dialect, element_types=types)
            if upper.startswith("NULLABLE") and inner:
                inner_type = self.parse(inner[0])
                return ClickHouseNullableType(dialect=self.dialect, inner_type=inner_type)
            if upper.startswith("LOWCARDINALITY") and inner:
                inner_type = self.parse(inner[0])
                return ClickHouseLowCardinalityType(dialect=self.dialect, inner_type=inner_type)

        # AggregateFunction
        if self._CLICKHOUSE_AGGREGATE_TYPES.match(upper):
            inner = self._extract_inner_types(stripped)
            if inner:
                func_name = inner[0]
                arg_types = [self.parse(t) for t in inner[1:]]
                if upper.startswith("SIMPLEAGGREGATEFUNCTION"):
                    return ClickHouseSimpleAggregateFunctionType(
                        dialect=self.dialect, function_name=func_name, arg_types=arg_types)
                return ClickHouseAggregateFunctionType(dialect=self.dialect, function_name=func_name, arg_types=arg_types)

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
                dialect=self.dialect, srid=srid)
            return ClickHouseGeometryType(dialect=self.dialect, srid=srid)

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
            return ClickHouseVectorType(dialect=self.dialect, dim=dim)

        # Fallback: a type name this dialect does not know. It is a
        # ``CustomType`` because that is honest — the framework has no class for
        # it — but rendering one will raise, and that is the point rather than an
        # oversight: an unclaimed name may be one ClickHouse rejects outright, or
        # one it accepts as an alias (``VARCHAR(10)`` means ``String``), so
        # writing ``data_type.raw`` back out would either fail at the server or
        # silently store a type the caller may not have meant. There is no
        # ``format_data_type_custom`` here, and
        # ``suggest_substitute_types()["custom"]`` names ``ClickHouseStringType`` so
        # the ``TypeError`` says what to use instead.
        from rhosocial.activerecord.backend.expression.types import CustomType
        return CustomType(dialect=self.dialect, raw=stripped)

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
