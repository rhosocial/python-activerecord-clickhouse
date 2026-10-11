# src/rhosocial/activerecord/backend/impl/clickhouse/expression/types.py
"""ClickHouse-specific DataType subclasses.

Naming convention
-----------------
ClickHouse-specific types use the ``ClickHouse`` prefix to distinguish them from
the core types (which have no prefix).  This avoids ambiguity when both
core and backend types are used together.

Usage scope
-----------
These types are used **only** for ClickHouse backend DDL column definitions,
introspection result parsing, and schema comparison.  They should **not**
be used by application code directly — always use the core types for
DDL definition expressions (``ColumnDefinition.data_type``).

Inheritance
-----------
Every ClickHouse type that *is* a core concept derives from the core class it
is, rather than sitting on ``DataType`` and restating it:

============================  ======================
ClickHouse type               Core concept
============================  ======================
``Int8`` / ``UInt8``          :class:`TinyIntType`
``Int16`` / ``UInt16``        :class:`SmallIntType`
``Int32`` / ``UInt32``        :class:`IntegerType`
``Int64`` / ``UInt64``        :class:`BigIntType`
``Float32``                   :class:`FloatType`
``Float64``                   :class:`DoubleType`
``Decimal*``                  :class:`DecimalType`
``String``                    :class:`TextType`
``FixedString(N)``            :class:`BinaryType`
``Date`` / ``Date32``         :class:`DateType`
``DateTime`` / ``DateTime64`` :class:`TimestampType`
``Bool``                      :class:`BooleanType`
``UUID``                      :class:`UUIDType`
``JSON``                      :class:`JsonType`
============================  ======================

The ``name`` stays ``clickhouse_``-prefixed in every case, because the DDL really
does say ``Int32`` and a schema diff has to compare the word the server wrote.
Inheritance says what the type *is*; ``name`` says how it is *spelled*.

What is left on ``DataType`` is what ClickHouse has and core does not — the
wrappers, the containers, the enum, the network addresses, the spatial family
and the vector type. Each of those carries a docstring saying why it is not a
core concept.
"""

from __future__ import annotations

from typing import List, Optional, Tuple as TupleType

from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BinaryType,
    BooleanType,
    DataType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    SmallIntType,
    TextType,
    TimestampType,
    TinyIntType,
    UUIDType,
)
from rhosocial.activerecord.backend.expression.types.array import ArrayType


# ---------------------------------------------------------------------------
# Integer types (signed and unsigned)
#
# ClickHouse is the one backend where width and signedness are two independent
# axes over the same eight storage sizes: ``Int8``..``Int64`` and
# ``UInt8``..``UInt64``. Core already models that shape — width is the class,
# signedness is the ``unsigned`` field — so each ClickHouse integer is the core
# width class whose storage it uses, and nothing else.
# ---------------------------------------------------------------------------

class ClickHouseInt8Type(TinyIntType):
    """ClickHouse ``Int8`` — signed 8-bit integer, range [-128, 127].

    The 1-byte signed integer concept. ``spelling`` stays a core word
    (``tinyint``): ClickHouse has no spelling of its own for it, ``Int8`` is the
    name of the *column*, not of the concept.
    """

    name = "clickhouse_int8"


class ClickHouseInt16Type(SmallIntType):
    """ClickHouse ``Int16`` — signed 16-bit integer, range [-32768, 32767].

    The 2-byte signed integer concept; see :class:`ClickHouseInt8Type`.
    """

    name = "clickhouse_int16"


class ClickHouseInt32Type(IntegerType):
    """ClickHouse ``Int32`` — signed 32-bit integer.

    The 4-byte signed integer concept, and the default integer ClickHouse uses
    for a number with no width stated.
    """

    name = "clickhouse_int32"


class ClickHouseInt64Type(BigIntType):
    """ClickHouse ``Int64`` — signed 64-bit integer.

    The 8-byte signed integer concept. ClickHouse also uses ``Int64`` as the
    storage for an interval expressed as a count of seconds, which is why
    ``suggested_data_types()`` names this class as the stand-in for core's
    ``IntervalType``.
    """

    name = "clickhouse_int64"


class ClickHouseUInt8Type(TinyIntType):
    """ClickHouse ``UInt8`` — unsigned 8-bit integer, range [0, 255].

    Same width concept as ``Int8`` but the opposite value range, and ClickHouse
    spells that in the name rather than as a modifier, so it is a separate class
    with ``unsigned`` pinned on rather than a flag a caller can flip.

    ``UInt8`` is also the physical type behind ``Bool``; that is
    :class:`ClickHouseBoolType`, kept separate because the two do not compare or
    convert the same way.
    """

    name = "clickhouse_uint8"

    def __init__(self, dialect=None):
        super().__init__(dialect, unsigned=True)


class ClickHouseUInt16Type(SmallIntType):
    """ClickHouse ``UInt16`` — unsigned 16-bit integer, range [0, 65535].

    See :class:`ClickHouseUInt8Type` for why this is a class and not a flag.
    """

    name = "clickhouse_uint16"

    def __init__(self, dialect=None):
        super().__init__(dialect, unsigned=True)


class ClickHouseUInt32Type(IntegerType):
    """ClickHouse ``UInt32`` — unsigned 32-bit integer, range [0, 4294967295].

    See :class:`ClickHouseUInt8Type` for why this is a class and not a flag.
    """

    name = "clickhouse_uint32"

    def __init__(self, dialect=None):
        super().__init__(dialect, unsigned=True)


class ClickHouseUInt64Type(BigIntType):
    """ClickHouse ``UInt64`` — unsigned 64-bit integer.

    See :class:`ClickHouseUInt8Type` for why this is a class and not a flag.
    """

    name = "clickhouse_uint64"

    def __init__(self, dialect=None):
        super().__init__(dialect, unsigned=True)


# ---------------------------------------------------------------------------
# Float types
# ---------------------------------------------------------------------------

class ClickHouseFloat32Type(FloatType):
    """ClickHouse ``Float32`` — 32-bit floating point.

    The variable-precision approximate-numeric concept, but ClickHouse has no
    adjustable precision to give it: ``Float32`` is 32 bits and that is the whole
    type, where ``FLOAT(p)`` in the generic spelling would choose a mantissa
    width.

    So the class declares **no** parameters. ``PARAMETERS`` and ``__init__`` are
    both stated for the same reason — ``precision`` is not a constructor argument
    at all, because accepting one would let a caller set a width the server will
    silently ignore, and because :meth:`BaseExpression.get_params` reads the
    constructor signature, so the two must agree about what the parameters are.
    """

    # ClickHouse's ``Float32`` takes no precision argument -- ``__init__`` rejects
    #     one -- so declaring ``precision`` here would advertise an identity the
    #     class cannot have. Declared empty deliberately.

    PARAMETERS = ()

    name = "clickhouse_float32"

    def __init__(self, dialect=None):
        super().__init__(dialect)


        super().__init__(dialect)

class ClickHouseFloat64Type(DoubleType):
    """ClickHouse ``Float64`` — 64-bit floating point.

    Core's ``DoubleType`` is ``DOUBLE PRECISION``; ClickHouse's word for the same
    8-byte float is ``Float64``. The concept is the same — an approximate number
    with a 53-bit mantissa — so the class derives from it, and declares no
    parameters for symmetry with :class:`ClickHouseFloat32Type`: ``spelling`` is
    a SQL-standard word (``double`` / ``double precision``) that ClickHouse never
    writes, so it is neither part of this type's identity nor something a caller
    should be able to set. Both ``PARAMETERS`` and ``__init__`` are stated so
    the two agree — :meth:`BaseExpression.get_params` reads the constructor
    signature, and an inherited ``spelling`` would make it report a parameter
    equality says does not exist.
    """

    # As ``ClickHouseFloat32Type``: no precision argument, so no precision in
    #     identity.

    PARAMETERS = ()

    name = "clickhouse_float64"

    def __init__(self, dialect=None):
        super().__init__(dialect)


# ---------------------------------------------------------------------------
# Decimal types
#
# ClickHouse has four ways to spell an exact fixed-point number, and the choice
# is not cosmetic: ``Decimal(P, S)`` takes an explicit precision, while
# ``Decimal32`` / ``Decimal64`` / ``Decimal128`` fix it at 9 / 18 / 38 digits and
# take only the scale. A schema diff has to see that difference, which is why
# these are four classes over one core concept rather than one class with a
# precision.
# ---------------------------------------------------------------------------

class ClickHouseDecimalType(DecimalType):
    """ClickHouse ``Decimal(P, S)`` — exact fixed-point with explicit precision.

    ClickHouse caps the precision at 38 digits, tighter than the SQL standard's
    38 (and much tighter than PostgreSQL's 1000), so the bound is enforced here
    rather than left to the server.
    """

    PARAMETERS = ("precision", "scale",)

    name = "clickhouse_decimal"

    precision: int
    scale: int

    def __init__(self, dialect=None, *, precision: int, scale: int = 0):
        super().__init__(dialect)
        if not (1 <= precision <= 38):
            raise ValueError(
                f"Decimal precision must be between 1 and 38, got {precision}"
            )
        if not (0 <= scale <= 38):
            raise ValueError(
                f"Decimal scale must be between 0 and 38, got {scale}"
            )
        self.precision = precision
        self.scale = scale


class ClickHouseDecimal32Type(DecimalType):
    """ClickHouse ``Decimal32(S)`` — exact fixed-point in 32 bits, 9 digits.

    The precision is fixed by the width, so it is the class that carries it and
    only the scale is a parameter — which is why ``precision`` deliberately does
    not appear in ``PARAMETERS``: two ``Decimal32`` columns with the same scale
    are the same type whatever the class docstring says about digit counts.
    """

    name = "clickhouse_decimal32"

    scale: int

    def __init__(self, dialect=None, *, scale: int = 0):
        super().__init__(dialect)
        if not (0 <= scale <= 38):
            raise ValueError(
                f"Decimal32 scale must be between 0 and 38, got {scale}"
            )
        self.scale = scale

    PARAMETERS = ("scale",)

class ClickHouseDecimal64Type(DecimalType):
    """ClickHouse ``Decimal64(S)`` — exact fixed-point in 64 bits, 18 digits.

    See :class:`ClickHouseDecimal32Type` on why only the scale is a parameter.
    """

    name = "clickhouse_decimal64"

    scale: int

    def __init__(self, dialect=None, *, scale: int = 0):
        super().__init__(dialect)
        if not (0 <= scale <= 38):
            raise ValueError(
                f"Decimal64 scale must be between 0 and 38, got {scale}"
            )
        self.scale = scale

    PARAMETERS = ("scale",)

class ClickHouseDecimal128Type(DecimalType):
    """ClickHouse ``Decimal128(S)`` — exact fixed-point in 128 bits, 38 digits.

    See :class:`ClickHouseDecimal32Type` on why only the scale is a parameter.
    """

    name = "clickhouse_decimal128"

    scale: int

    def __init__(self, dialect=None, *, scale: int = 0):
        super().__init__(dialect)
        if not (0 <= scale <= 38):
            raise ValueError(
                f"Decimal128 scale must be between 0 and 38, got {scale}"
            )
        self.scale = scale

    PARAMETERS = ("scale",)

# ---------------------------------------------------------------------------
# String / Binary types
#
# ClickHouse has exactly two string types and they divide on padding, not on
# character set. ``String`` is variable-length and stores the bytes as given;
# ``FixedString(N)`` is exactly N **bytes**, right-padded with ``\\0`` to length
# N and rejecting anything longer. That padding is what makes the second one a
# byte string: a fixed-length *character* type cannot behave that way, and
# ClickHouse's own documentation shows ``FixedString(3)`` holding ``'a'``
# matching ``= 'a'`` while ``LIKE 'a'`` matches nothing, because the stored value
# is ``'a\\0\\0'``.
# ---------------------------------------------------------------------------

class ClickHouseStringType(TextType):
    """ClickHouse ``String`` — variable-length byte string, no padding.

    The unbounded-text concept: ClickHouse's manual recommends it for UTF-8 text
    and appends nothing, so what is stored is what was written. It is *not* a
    ``CHAR(n)`` — ClickHouse has no fixed-width character type at all, which is
    why ``CharType`` and ``VarCharType`` both render ``String`` here and the
    declared length is dropped.
    """

    name = "clickhouse_string"


class ClickHouseFixedStringType(BinaryType):
    """ClickHouse ``FixedString(N)`` — exactly N bytes, zero-padded on the right.

    The fixed-length **byte** string concept, not the fixed-length character
    one. Two properties make that the honest reading and not a matter of taste:

    * ``N`` counts bytes, not characters, so a UTF-8 column is limited by bytes
      and a character can be split by the padding;
    * a shorter value is padded with ``\\0`` to exactly N, which is why
      ``FixedString(3)`` holding ``'a'`` equals ``'a'`` but does not match
      ``LIKE 'a'`` — a fixed-length character type cannot do that.

    ``length`` is required here although :class:`BinaryType` makes it optional,
    because ``FixedString`` with no length is not a type ClickHouse will accept.
    """

    # ``FixedString(N)`` is exactly N zero-padded bytes, so N is not a hint but
    #     the storage: a FixedString(4) and a FixedString(8) are different columns.

    PARAMETERS = ("length",)

    name = "clickhouse_fixed_string"

    length: int

    def __init__(self, dialect=None, *, length: int):
        super().__init__(dialect)
        if length < 1:
            raise ValueError("FixedString length must be >= 1")
        self.length = length


# ---------------------------------------------------------------------------
# Date / Time types
#
# ClickHouse's ``DateTime`` is a count of seconds since the Unix epoch — the
# thing SQL calls ``TIMESTAMP``, not MySQL's wall-clock ``DATETIME``. That is why
# both ``ClickHouseDateTimeType`` and ``ClickHouseDateTime64Type`` derive from
# :class:`TimestampType` even though one of them is spelled ``DateTime``.
# ---------------------------------------------------------------------------

class ClickHouseDateType(DateType):
    """ClickHouse ``Date`` — calendar date in 2 bytes, 1970-01-01..2149-06-06.

    The date concept at its narrowest. :class:`ClickHouseDate32Type` is the same
    concept in 4 bytes over a wider range, which is a storage difference a schema
    diff must notice, so it is a second class over the same core concept.
    """

    name = "clickhouse_date"


class ClickHouseDate32Type(DateType):
    """ClickHouse ``Date32`` — calendar date in 4 bytes, 1900-01-01..2299-12-31.

    Same concept as :class:`ClickHouseDateType`, four times the range, and a
    different type to ClickHouse — a column cannot change from one to the other
    in place without rewriting what it holds.
    """

    name = "clickhouse_date32"


class ClickHouseDateTimeType(TimestampType):
    """ClickHouse ``DateTime`` — seconds since the Unix epoch, no sub-second part.

    Core's ``TimestampType`` is ``TIMESTAMP[(p)]``: a point on the timeline,
    stored as an epoch count and rendered in a session or column time zone. That
    is exactly what ClickHouse's ``DateTime`` is, so it is the same concept — and
    specifically *not* core's ``DateTimeType``, which is MySQL's wall-clock
    ``DATETIME`` with no epoch to convert against.

    The precision is fixed at 0 (whole seconds) and there is nothing to set, so
    this declares **no** parameters: ``precision`` is not a constructor argument,
    because accepting one would promise a sub-second precision the server will
    not keep, and :meth:`BaseExpression.get_params` reads the constructor
    signature, so it and ``PARAMETERS`` have to agree.
    :class:`ClickHouseDateTime64Type` is the adjustable-precision variant.

    The dispatch key is ``clickhouse_timestamp``, **not**
    ``clickhouse_datetime``, even though the server's word is ``DateTime``. The
    key names the concept; the renderer writes ClickHouse's spelling of it —
    exactly as this backend writes ``String`` for a text column. An earlier key
    of ``clickhouse_datetime`` said "datetime" while the class derived from
    ``TimestampType``: a reader comparing the key against core's type list would
    conclude the base was wrong, and act on it.
    """

    # As the Float classes: ``__init__`` takes no precision, so inheriting
    # ``precision`` from the timestamp concept would advertise an identity
    # this class cannot have. Whole seconds only.
    PARAMETERS = ()

    name = "clickhouse_timestamp"

    def __init__(self, dialect=None):
        super().__init__(dialect)


class ClickHouseDateTime64Type(TimestampType):
    """ClickHouse ``DateTime64(P)`` — epoch seconds with 0..9 fractional digits.

    The same concept as :class:`ClickHouseDateTimeType` at a chosen precision,
    stored as a scaled integer. ``precision`` is a real parameter here, so
    ``PARAMETERS`` is stated rather than inherited only to make it obvious that
    it is the precision — and not some other inherited field — that makes two
    ``DateTime64`` columns different types.

    The dispatch key is ``clickhouse_timestamp64``, not
    ``clickhouse_datetime64``, even though the server's word is ``DateTime64``.
    The key names the *concept*; the renderer writes ClickHouse's spelling. The
    old key said "datetime" while the class derived from ``TimestampType``, which
    is the one claim a reader would act on and get wrong. See
    :class:`ClickHouseDateTimeType` for why the concept is a timestamp here.
    """

    name = "clickhouse_timestamp64"

    precision: int

    def __init__(self, dialect=None, *, precision: int = 3):
        super().__init__(dialect)
        if precision < 0 or precision > 9:
            raise ValueError("DateTime64 precision must be between 0 and 9")
        self.precision = precision

    PARAMETERS = ("precision",)

# ---------------------------------------------------------------------------
# Boolean type
# ---------------------------------------------------------------------------

class ClickHouseBoolType(BooleanType):
    """ClickHouse ``Bool`` — truth value, stored as a ``UInt8`` restricted to 0/1.

    Core's ``BooleanType`` is ``BOOLEAN`` / ``BOOL``, and ClickHouse accepts both
    words for exactly this type — so the core spelling list is not a widening
    here, it is ClickHouse's own vocabulary.

    ``UInt8`` is the physical type underneath, but ``Bool`` is not an integer:
    ClickHouse rejects any other value on insert, which is the property
    :class:`ClickHouseUInt8Type` does not have.
    """

    name = "clickhouse_bool"


# ---------------------------------------------------------------------------
# UUID
# ---------------------------------------------------------------------------

class ClickHouseUUIDType(UUIDType):
    """ClickHouse ``UUID`` — 128-bit identifier, stored as two 64-bit halves.

    ClickHouse is the reference implementation for this concept on this side of
    the project: the value is a plain 128-bit number with no object identity
    beyond the bits, and the type is named exactly as core names it. Deriving
    from :class:`UUIDType` is what lets code written against the core concept
    work on this backend unchanged, and what makes "is this a UUID column?" one
    question instead of one per backend.
    """

    name = "clickhouse_uuid"


# ---------------------------------------------------------------------------
# IP types
#
# Not core concepts: SQL:2016 has no network address type, and core's type
# documentation promises none. ClickHouse stores an address as its own type with
# its own operators, so each gets a class here rather than being faked with a
# character type.
# ---------------------------------------------------------------------------

class ClickHouseIPv4Type(DataType):
    """ClickHouse ``IPv4`` — an IPv4 address, stored as 4 bytes.

    ClickHouse's own type, with its own operators: arithmetic on two addresses
    yields a network mask rather than a number, which is why it cannot be a
    ``UInt32`` with a name.

    On ``DataType`` because SQL:2016 has no network address type. Core's own
    backend documentation lists the other backends' ``PostgresInetType`` /
    ``MySqlInetType`` as backend types rather than promising a core concept, and
    promoting one is on the datatype-hierarchy plan's shelved list — a separate
    decision, not something to settle by inheritance here.
    """

    name = "clickhouse_ipv4"


class ClickHouseIPv6Type(DataType):
    """ClickHouse ``IPv6`` — an IPv6 address, stored as 16 bytes.

    A separate class from :class:`ClickHouseIPv4Type` because the stored length
    differs, which is what a schema diff has to notice.

    On ``DataType`` because SQL:2016 has no network address type; see
    :class:`ClickHouseIPv4Type`.
    """

    name = "clickhouse_ipv6"


# ---------------------------------------------------------------------------
# Enum types (ClickHouse native Enum8 / Enum16)
# ---------------------------------------------------------------------------

class ClickHouseEnum8Type(DataType):
    """ClickHouse ``Enum8`` — a closed set of string labels over a signed byte.

    **Not** core's :class:`~...types.enum_.EnumType`, and the differences are
    behavioural, not cosmetic:

    * the value space is an explicit mapping of label to **possibly negative
      signed integer**, and those integers are chosen by the caller;
    * the server orders the labels **by the integer assigned to each**, not by
      the order they were declared in, and rewrites the declaration to match —
      ``Enum8('x' = 1, 'y' = -2)`` is reported back as ``Enum8('y' = -2, 'x' = 1)``;
    * the column is **not nullable**. ``Enum8`` values cannot hold NULL; the
      closest equivalent is ``Nullable(Enum8(...))``, a different type;
    * most numeric and string operations are simply **undefined** on it — ClickHouse
      raises rather than coercing, so an enum does not inherit the arithmetic of
      the integer it happens to be stored as.

    Core's ``EnumType`` carries ``values: Tuple[str, ...]`` — labels only, no
    integers, no order rule and no nullability. Deriving from it would make
    ``isinstance`` claim four things about a ClickHouse enum that are all false,
    so the class sits on ``DataType`` (D6).
    """

    # The label-to-integer mapping is the whole type, and ClickHouse assigns
    #     possibly-negative integers and orders by them.

    PARAMETERS = ("values",)

    name = "clickhouse_enum8"

    values: List[TupleType[str, int]]

    def __init__(self, dialect=None, *, values: List[TupleType[str, int]]):
        super().__init__(dialect)
        if not values:
            raise ValueError("Enum8 must have at least one value")
        seen = set()
        for name, num in values:
            if num < -128 or num > 127:
                raise ValueError(f"Enum8 value {num} out of range [-128, 127]")
            pair = (name, num)
            if pair in seen:
                raise ValueError(f"Duplicate Enum8 pair: {pair}")
            seen.add(pair)
        self.values = tuple(values)

        PARAMETERS = ("values",)

class ClickHouseEnum16Type(DataType):
    """ClickHouse ``Enum16`` — a closed set of string labels over a signed short.

    Identical in kind to :class:`ClickHouseEnum8Type` and identical in every one
    of its reasons for not being core's ``EnumType``: explicit possibly-negative
    integers, ordering by the assigned integer rather than the declaration order,
    non-nullable, and undefined for most numeric and string operations.

    Separate from ``Enum8`` because the label set has to fit in a signed short
    rather than a signed byte, and that is a different type to the server.
    """

    name = "clickhouse_enum16"

    PARAMETERS = ("values",)

    def __init__(self, dialect=None, *, values: List[TupleType[str, int]]):
        super().__init__(dialect)
        if not values:
            raise ValueError("Enum16 must have at least one value")
        seen = set()
        for name, num in values:
            if num < -32768 or num > 32767:
                raise ValueError(f"Enum16 value {num} out of range [-32768, 32767]")
            pair = (name, num)
            if pair in seen:
                raise ValueError(f"Duplicate Enum16 pair: {pair}")
            seen.add(pair)
        self.values = tuple(values)

        PARAMETERS = ("values",)

# ---------------------------------------------------------------------------
# Container types (Array, Map, Tuple)
# ---------------------------------------------------------------------------

class ClickHouseArrayType(ArrayType):
    """ClickHouse ``Array(T)`` — a variable-length list of ``T``.

    Already the right shape: core's :class:`~...types.array.ArrayType` is
    ``T[]`` with an element type and a dimensionality, and ClickHouse's
    ``Array(T)`` is the nesting spelling of it. Nesting stays available here
    (``Array(Array(Int32))``) precisely because ClickHouse has no multi-dimensional
    array syntax; see the core docstring on nesting versus dimensionality.
    """

    name = "clickhouse_array"


class ClickHouseMapType(DataType):
    """ClickHouse ``Map(K, V)`` — a dictionary keyed by ``K``.

    The nearest SQL standard concept is ``ROW``, but a ``ROW`` is an ordered list
    of *named* fields and a ``Map`` is an unordered set of key/value pairs whose
    keys are values of their own type — the two accept different literals, index
    differently and have different operators. Core's only container is
    :class:`~...types.array.ArrayType`, which cannot express either the key type
    or the lookup, so this is a ClickHouse type of its own.

    Stored as a nested ``Array(Tuple(K, V))``, which is why ClickHouse's manual
    warns about its per-key overhead.
    """

    name = "clickhouse_map"

    key_type: DataType
    value_type: DataType

    def __init__(self, dialect=None, *, key_type: DataType, value_type: DataType):
        super().__init__(dialect)
        self.key_type = key_type
        self.value_type = value_type

    PARAMETERS = ("key_type", "value_type",)

class ClickHouseTupleType(DataType):
    """ClickHouse ``Tuple(T1, T2, ...)`` — a fixed group of values.

    Elements are addressed by position (``tuple.1``) and, when the declaration
    names them, by name (``tuple.a``) as well. The names **are** part of the
    type's identity on this server: verified live on ClickHouse 26.7.3.19, they
    are stored and reported by ``system.columns.type`` / ``SHOW CREATE`` /
    ``DESCRIBE`` / ``toTypeName``, compared (and hashed) by ``IDataType::equals``,
    used for ``tuple.name`` access, and matched when values convert during
    INSERT/CAST. The full evidence table lives in
    ``.claude/plan/2026-10-08/secondary-gaps-investigation.md`` §A. That is why
    ``element_names`` sits in ``PARAMETERS``: ``Tuple(a Int32)`` and
    ``Tuple(b Int32)`` are different columns, and a model declaring the latter
    against a table holding the former is a change the differ must report —
    the ``ALTER TABLE … MODIFY COLUMN x Tuple(b Int32)`` it emits renames the
    column, where suppressing the difference would leave ``x.b`` failing at
    runtime with ``UNKNOWN_IDENTIFIER``. It is not an array either: core's
    :class:`~...types.array.ArrayType` has no way to say the elements are
    heterogeneous.

    On ``DataType`` because SQL:2016 has no positional composite type; ``STRUCT``
    and ``ROW`` are shelved in the datatype-hierarchy plan, and a ClickHouse
    ``Tuple`` is neither.
    """

    name = "clickhouse_tuple"

    element_types: List[DataType]
    element_names: Optional[List[str]] = None

    def __init__(self, dialect=None, *, element_types: List[DataType],
                 element_names: Optional[List[str]] = None):
        super().__init__(dialect)
        if not element_types:
            raise ValueError("Tuple must have at least one element")
        if element_names and len(element_names) != len(element_types):
            raise ValueError("element_names length must match element_types")
        # Tuples from construction, so the declaration below is a plain read
        # rather than a comparison that quietly normalises a list it forgot to
        # normalise when the value was stored.
        self.element_types = tuple(element_types)
        self.element_names = tuple(element_names) if element_names else None

    PARAMETERS = ("element_types", "element_names",)


# ---------------------------------------------------------------------------
# Type wrappers (Nullable, LowCardinality)
#
# The briefing's shelved list names these four wrappers explicitly as out of
# scope for this refactor, so they keep their classes and their rendering; what
# follows is only the D7 justification for each of them sitting on ``DataType``.
# ---------------------------------------------------------------------------

class ClickHouseNullableType(DataType):
    """ClickHouse ``Nullable(T)`` — ``T``, or ``NULL``.

    SQL models nullability as a **column attribute** (core's
    ``ColumnDefinition.nullable``) that any type may carry; ClickHouse has no such
    thing and writes it into the type name instead. That difference is not
    cosmetic — a ``Nullable(String)`` column cannot hold the empty string
    distinctly from ``''``, and a non-nullable one cannot hold ``NULL`` at all —
    so the wrapper has to be a type in order to be rendered and compared.

    On ``DataType``: there is no core concept to derive from, because the concept
    it wraps is a *modifier*, and modifiers are not in the identity of a type.
    Shelved as a wrapper in the datatype-hierarchy plan.
    """

    name = "clickhouse_nullable"

    inner_type: DataType

    def __init__(self, dialect=None, *, inner_type: DataType):
        super().__init__(dialect)
        self.inner_type = inner_type

    PARAMETERS = ("inner_type",)

class ClickHouseLowCardinalityType(DataType):
    """ClickHouse ``LowCardinality(T)`` — ``T`` stored as a dictionary index.

    A **storage encoding**: the values are written into a dictionary and the
    column holds positions into it, which pays off only when the number of
    distinct values is small. The value it holds is exactly the ``T`` it wraps,
    so two columns differ in encoding rather than in content.

    On ``DataType`` because no core concept describes it, and because there is
    nothing for it to *be* a different type from — ``LowCardinality(String)`` and
    ``String`` hold the same values and answer the same queries. It cannot derive
    from :class:`ClickHouseStringType` (nor from any other inner type, since the
    inner type is a parameter): doing so would make ``isinstance(encoding,
    StringType)`` true for a type that only ever *wraps* a string.
    """

    name = "clickhouse_low_cardinality"

    inner_type: DataType

    def __init__(self, dialect=None, *, inner_type: DataType):
        super().__init__(dialect)
        self.inner_type = inner_type

    PARAMETERS = ("inner_type",)

# ---------------------------------------------------------------------------
# JSON type
# ---------------------------------------------------------------------------

class ClickHouseJSONType(JsonType):
    """ClickHouse ``JSON`` — a native semi-structured column type.

    Distinct from :class:`ClickHouseStringType`, which stores the same document
    as opaque bytes: a ``JSON`` column knows its paths and types, so
    ``JSONExtract`` reads a field without parsing the whole value, and a path that
    does not exist is a query error rather than an empty result. Core's
    :class:`~...types.json_.JsonType` is the concept for exactly that, so this
    derives from it.
    """

    name = "clickhouse_json"


# ---------------------------------------------------------------------------
# Aggregation function types
# ---------------------------------------------------------------------------

class ClickHouseAggregateFunctionType(DataType):
    """ClickHouse ``AggregateFunction(name, T...)`` — an intermediate state.

    Not a column's storage type: it is the partially-accumulated state an
    aggregate query builds in memory and writes into
    ``AggregatingMergeTree``'s columns, to be merged later. Its identity is the
    *function* plus the argument types, which is why ``function_name`` and
    ``arg_types`` are the parameters.

    On ``DataType`` because SQL:2016 has no type for "a value that only means
    something to a particular aggregate function", and because a state that is
    only meaningful to a function cannot be a subtype of any of the types it will
    eventually produce — a ``sum`` state is not a ``SUM(bigint)``.
    """

    # An aggregate function's state is identified by which function it is over
    #     which argument types; anything else would make two different aggregates
    #     interchangeable.

    PARAMETERS = ("function_name", "arg_types",)

    name = "clickhouse_aggregate_function"

    function_name: str
    arg_types: List[DataType]

    def __init__(self, dialect=None, *, function_name: str, arg_types: List[DataType]):
        super().__init__(dialect)
        self.function_name = function_name
        self.arg_types = tuple(arg_types)

        # A tuple from construction, not from comparison: the
        # argument types are identity, and state that is only
        # normalised when it is hashed is mutable in every other
        # respect.
        PARAMETERS = ("function_name", "arg_types",)

class ClickHouseSimpleAggregateFunctionType(DataType):
    """ClickHouse ``SimpleAggregateFunction(name, T...)`` — a mergeable state.

    A restricted :class:`ClickHouseAggregateFunctionType`: only aggregates whose
    state merges by itself (``sum``, ``min``, ``max``, ``any``…) may use it, and
    then it can be stored in an ordinary ``MergeTree`` column instead of needing
    ``AggregatingMergeTree``. That is a different type to ClickHouse, so it is a
    different class.

    On ``DataType`` for the same reason as ``AggregateFunction``: SQL:2016 has no
    type for a value that only means something to a particular aggregate
    function, so there is no core concept for it to be.
    """

    PARAMETERS = ("function_name", "arg_types",)

    name = "clickhouse_simple_aggregate_function"

    function_name: str
    arg_types: List[DataType]

    def __init__(self, dialect=None, *, function_name: str, arg_types: List[DataType]):
        super().__init__(dialect)
        self.function_name = function_name
        self.arg_types = tuple(arg_types)

        # A tuple from construction, not from comparison: the
        # argument types are identity, and state that is only
        # normalised when it is hashed is mutable in every other
        # respect.
        PARAMETERS = ("function_name", "arg_types",)

# ---------------------------------------------------------------------------
# Spatial / Geometry types
#
# SQL:2016 has no geometric types at all, so there is nothing in core to derive
# from. The seven concrete classes do share ClickHouse's own base — which is also
# the real, separately-nameable ``GEOMETRY`` type — and each carries the same
# ``srid`` because ClickHouse gives them all the same optional coordinate
# reference identifier.
# ---------------------------------------------------------------------------

class ClickHouseGeometryType(DataType):
    """ClickHouse ``GEOMETRY`` — a geometry of any of the seven concrete kinds.

    On ``DataType`` because SQL:2016 has no geometric types at all, so there is
    nothing in core to derive from. Promoting a geometric family to core is a
    design decision of its own — nine such types across five backends is the
    largest candidate on the datatype-hierarchy plan's shelved list, and it is
    shelved precisely so that it is not settled here by inheritance.

    ClickHouse names this type as well as using it as the base of the concrete
    ones, so the inheritance below is not a grouping node invented by this
    project: ``Point``, ``LineString``, ``Polygon``, ``MultiPoint``,
    ``MultiLineString``, ``MultiPolygon`` and ``GeometryCollection`` are all
    ``GEOMETRY`` values with a known kind, and a column declared ``GEOMETRY``
    accepts any of them.

    ``srid`` is the optional coordinate reference identifier ClickHouse writes as
    ``SRID <n>``. It is part of the type's identity here because it is part of
    the written declaration — two geometries with different SRIDs are not
    interchangeable without a transform.
    """

    name = "clickhouse_geometry"

    srid: Optional[int] = None

    def __init__(self, dialect=None, *, srid: Optional[int] = None):
        super().__init__(dialect)
        self.srid = srid

    PARAMETERS = ("srid",)

class ClickHousePointType(ClickHouseGeometryType):
    """ClickHouse ``POINT`` — a single ``(x, y)`` position.

    The smallest geometry: two coordinates and no extent. Separate from
    ``GEOMETRY`` because the column will only ever hold points.
    """

    name = "clickhouse_point"


class ClickHouseLineStringType(ClickHouseGeometryType):
    """ClickHouse ``LINESTRING`` — an ordered sequence of two or more positions.

    Open: it has a direction and no interior, unlike ``POLYGON``.
    """

    name = "clickhouse_linestring"


class ClickHousePolygonType(ClickHouseGeometryType):
    """ClickHouse ``POLYGON`` — a closed area bounded by a ring of positions.

    Has an interior, which is what separates it from ``LINESTRING``.
    """

    name = "clickhouse_polygon"


class ClickHouseMultiPointType(ClickHouseGeometryType):
    """ClickHouse ``MULTIPOINT`` — several points held as one value.

    Not an array of points: a ``MultiPoint`` is a single geometry, which is why
    it is a type rather than ``Array(Point)``.
    """

    name = "clickhouse_multipoint"


class ClickHouseMultiLineStringType(ClickHouseGeometryType):
    """ClickHouse ``MULTILINESTRING`` — several line strings held as one value.

    Distinct from ``Array(LINESTRING)``, which would lose the guarantee that the
    collection is one geometry.
    """

    name = "clickhouse_multilinestring"


class ClickHouseMultiPolygonType(ClickHouseGeometryType):
    """ClickHouse ``MULTIPOLYGON`` — several polygons held as one value.

    Distinct from ``Array(POLYGON)``; see ``MULTILINESTRING``.
    """

    name = "clickhouse_multipolygon"


class ClickHouseGeometryCollectionType(ClickHouseGeometryType):
    """ClickHouse ``GEOMETRYCOLLECTION`` — geometries of mixed kinds as one value.

    The only kind that may hold any of the other six, which is why it cannot be
    derived from any single one of them.
    """

    name = "clickhouse_geometrycollection"


# ---------------------------------------------------------------------------
# QBit — ClickHouse's vector type
# ---------------------------------------------------------------------------

class ClickHouseVectorType(DataType):
    """ClickHouse ``QBit(Float32, n)`` — a fixed-dimension vector of floats.

    ``n`` is part of the identity: a vector column cannot change its dimension
    in place without rewriting the data.

    On ``DataType`` because SQL:2016 has no vector type, and because it is not an
    array — the components are addressed positionally and the dimension is fixed,
    where :class:`ClickHouseArrayType` allows both to vary.

    The name is historical and deliberately kept: ``VECTOR(n)`` is **MySQL 9.0's**
    spelling, imported into this backend along with MySQL's ``STRING_TO_VECTOR`` /
    ``VECTOR_TO_STRING`` / ``DISTANCE_*`` family, and ClickHouse has never had
    it — ``CREATE TABLE t (a VECTOR(4))`` is rejected with ``Unknown data type
    family: VECTOR``. ClickHouse's own vector type is ``QBit``, so that is what
    this class renders. ``name`` stays ``clickhouse_vector`` because the concept
    really is ClickHouse-specific rather than a core one, and the dispatch key
    must carry the ``clickhouse_`` prefix; it is the *rendering* that was wrong,
    not the name.

    ``QBit``'s own spelling is ``QBit(element_type, dimension[, stride])``, with
    ``element_type`` one of ``Int8``, ``BFloat16``, ``Float32`` or ``Float64``.
    This class carries only the dimension, so the formatter fixes the element
    type at ``Float32`` — the representation this backend's own documentation
    already recommends for embeddings (``Array(Float32)`` + ``L2Distance``).
    """

    name = "clickhouse_vector"

    dim: int

    def __init__(self, dialect=None, *, dim: int):
        super().__init__(dialect)
        self.dim = dim

    PARAMETERS = ("dim",)
