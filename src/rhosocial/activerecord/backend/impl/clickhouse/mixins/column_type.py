# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/column_type.py
"""Which column class ClickHouse suggests for each common Python type.

This is the ClickHouse half of the column-type protocol: an answer for every
one of the eighteen common Python types the framework defines, and nothing
else. Everything here is a **column** decision -- what operations a value
carries -- and none of it is a storage decision: whether ``Array(T)`` or
``JSON`` spells the column is the DDL layer's separate answer (see
:class:`ClickHouseTypeSupportMixin`), and this table never reads it.

Evidence
--------
Every cell below is backed by a probe against a live **ClickHouse 26.7.3.19**
server (HTTP ``127.0.0.1:18682``, ``clickhouse-connect`` 1.9.0), recorded in the
core plan directory and, for the measured matrix, in this repository's
``.claude/plan/2026-10-08/secondary-gaps-investigation.md`` appendix C:

* ``suggested-pairing-array.md`` -- the native-array column of the matrix;
* ``suggested-pairing-json.md`` -- the ``dict`` battery (J00-J15);
* ``suggested-pairing-string-enum.md`` -- ``str`` / ``bytes`` / ``enum``;
* ``suggested-pairing-numeric.md`` -- the numeric families.

What ClickHouse is *not* given here
-----------------------------------
Two questions are deliberately left open rather than answered, because answering
them would be a ruling nobody has made:

* **The ``UInt`` question (议题 C).** ClickHouse has a full unsigned family
  (``UInt8``..``UInt256``) and "a column that can only hold a non-negative
  number" is a real semantic difference. Whether that deserves a column class of
  its own is undecided, so ``int`` answers :class:`IntegerColumn` like every
  other backend. This table is not a ruling on 议题 C and must not be read as
  one; it only says the question is still open.
* **``Tuple`` / ``Map`` column classes (议题 A).** ClickHouse's ``Tuple`` is a
  heterogeneous positional group and ``Map`` is native, and core has no column
  class for either. ``tuple`` is answered :class:`ArrayColumn` because that is
  what the protocol's agreed ClickHouse row says and because the permissive
  fallback this entry used to reach no longer exists; if 议题 A decides
  that ``Tuple`` gets a class, this entry moves with it.

Two rendering facts recorded here and **not** acted on, because rendering
belongs to Phase 2b:

* ``LENGTH`` on a ClickHouse ``String`` returns **bytes** (``length(s) = 9`` for
  five characters / nine UTF-8 bytes; ``lengthUTF8`` is the character count) --
  one of only two backends where that is true. A length operation must not
  assume a character count.
* Equality on a ``JSON`` column has to render as ``toString(doc) = ?``; the
  comparison exists and is not narrowed, but the bare ``=`` is not what the
  server accepts.

The JSON version gate
---------------------
The native ``JSON`` data type first appears on ClickHouse 26.0 -- the version
this backend already declares for JSON elsewhere
(:meth:`ClickHouseJSONFunctionMixin.supports_json_type` and
``_JSON_FUNCTION_VERSIONS`` both answer ``26.0``). Below it the JSON surface is
carried by the ``JSONExtract*`` / ``JSONHas`` / ``isValidJSON`` function family
over ``String`` storage, which is why the ``dict`` entry is answerable on every
version the backend supports and never needs the protocol's ``None``. This is
**not** a measured boundary: the probe battery ran on 26.7.3.19 only, and no
older server was available to find the exact first version. What is measured is
that on 26.7 the native type needs no experimental setting and plain DDL
declares it.

The capability mechanism this used to be routed through was removed from core:
nothing in production called it, and it had drifted from real behaviour. The
fact it carried survives here as a note, because a future phase that offers
``json_value`` has to know that the chainable document accessor needs the
native type.
"""

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, Optional, Type

from rhosocial.activerecord.backend.dialect.mixins import ColumnTypeMixin
from rhosocial.activerecord.backend.expression.column_types import (
    ArrayColumn,
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)

#: ClickHouse's full table: ``{common Python type: ColumnBase subclass}``.
#:
#: Every entry of the protocol's common-type list is answered, and every answer
#: is a column class: no entry is ``None``, and that is a finding rather than an
#: omission. ClickHouse has every capability the protocol's other backends lack
#: a default for: a native array, a native JSON type, and the ``ILIKE`` operator
#: that only PostgreSQL shares. The two ends that *do* answer ``None``
#: elsewhere -- Firebird's ``dict`` and ``list`` (no JSON functions, no arrays at
#: all) and MySQL 5.6's (no JSON functions) -- have nothing here to refuse.
#: ``dict`` stays answerable below the JSON type's first version because the
#: ``JSONExtract`` family, not the type, is what carries it.
#:
#: There is no core table to derive from any more: the neutral common-type table
#: was removed with the rebuild, so these are this backend's own answers, stated
#: in full. The numeric family is answered with the one class core now carries
#: -- see the comment on the ``float`` entry.
CLICKHOUSE_COLUMN_TYPES: Dict[Any, Optional[Type[ColumnBase]]] = {
    # --- numbers ---------------------------------------------------------
    # The measured facts behind this cell are that §1 calls `float` the whole
    # Float family here (Float32 / Float64 / BFloat16) and `Decimal` the
    # Decimal32/64/128/256 family, that Float64 yields inf on overflow and
    # carries nan natively, and that `AVG` of a Decimal answers Float64 rather
    # than a Decimal (suggested-pairing-numeric.md). Those are real differences
    # in what the server does, but core now carries one class for every numeric
    # width and precision -- the operations are the same whatever the value was
    # declared as, and the difference between a `Decimal(18, 4)` and a
    # `Float64` belongs to the DDL layer's DataType. So both entries answer
    # NumericColumn, and the width stays a rendering concern.
    float: NumericColumn,
    decimal.Decimal: NumericColumn,
    # --- booleans ------------------------------------------------------
    # `Bool` storage, and ClickHouse's Bool is UInt8 underneath
    # (suggested-mappings.md §1). The column class is unaffected: the
    # boolean-domain surface (`is_true` / `is_false` / `&` / `|` / `~`) is
    # BooleanColumn's, and core renders the literals as TRUE / FALSE.
    bool: BooleanColumn,
    # --- integers ------------------------------------------------------
    # The UInt question (议题 C) is open and this cell does not decide it:
    # see the module docstring. `int` is a whole number here as anywhere.
    int: IntegerColumn,
    # --- text and bytes ------------------------------------------------
    # String, with no server-side collation concept (§5 of the string
    # probe: ClickHouse compares bytes / code points, `Zebra` = `zebra` is
    # false). `ilike` is **not** narrowed -- ClickHouse is one of only two
    # backends that has it, and it was measured hitting both 'aXc' and
    # 'ABC'. LENGTH returning bytes is a Phase 2b rendering fact, noted in
    # the module docstring.
    str: StringColumn,
    # Bytes live in `String`, which is already byte-oriented; the driver
    # hands them back as a hex string for non-UTF-8 payloads, a value-layer
    # fact rather than a column-class one. Comparison, byte length,
    # substring, concat and hex were all measured present.
    bytes: BinaryColumn,
    bytearray: BinaryColumn,
    # --- date / time ---------------------------------------------------
    # DateTimeColumn for all three temporal entries, which is the shared
    # baseline. Two are provisional and say so: core has no DateColumn yet
    # (appendix C, `date`), and this backend's own TimeType renders DateTime
    # even though ClickHouse has had Time/Time64 for a while (appendix D-①,
    # 待办 #7). Neither gap is a reason to refuse an entry; both are reasons
    # the answer may move.
    datetime.date: DateTimeColumn,
    datetime.time: DateTimeColumn,
    datetime.datetime: DateTimeColumn,
    # A timedelta is a number of seconds here, answered by the numeric
    # surface. ClickHouse does have a native `Interval` family and the
    # driver binds a timedelta natively, but core has no IntervalColumn, and
    # the native type's arithmetic surface is **not** measured: the
    # aggregate fact table found `sum` / `avg` over `Interval*` rejected with
    # ILLEGAL_TYPE_OF_ARGUMENT on 26.7.3.19 even though the docs promise a
    # same-type result. So the honest answer is the numeric one, and the
    # Interval question rides with core's missing class.
    datetime.timedelta: NumericColumn,
    # Native `UUID` type, compared as a value like any other: portable SQL
    # has no UUID operator for a UUID column to be missing.
    uuid.UUID: UUIDColumn,
    # --- documents ------------------------------------------------------
    # Native `JSON` on 26.0+, and the `JSONExtract*` family over String
    # below it -- which is why this entry is never refused. Measured on
    # 26.7: plain DDL declares the type with no experimental setting, scalar
    # path `JSONExtractString`, document path `JSONExtractRaw`, has-key
    # `JSONHas`, array length `JSONLength(toString(doc), 'arr')`, validity
    # `isValidJSON(toString(doc))`, equality `toString(doc) = ?`. Note the
    # `toString` in two of those: passing the JSON column straight to
    # `JSONLength` silently returns 0. The version gate that used to hang off
    # this entry is now recorded in the module docstring.
    dict: JSONColumn,
    # --- arrays ----------------------------------------------------------
    # ClickHouse's `Array(T)`, and the one backend family where ArrayColumn
    # is the *native* answer rather than a narrowed substitute: the 26.7
    # column of the array matrix is check-marked for every row -- DDL,
    # a Python list bound directly (and read back as a list, no framework
    # serialisation needed), `length(x)`, 1-based `x[1]`, `has(x, v)`,
    # `arrayConcat(x, [v])`, `arrayExists(e -> e = v, x)`, whole-column
    # equality `x = [...]`, and `ARRAY JOIN` for unnest. Nothing is
    # narrowed on ArrayColumn.
    list: ArrayColumn,
    # A tuple is heterogeneous and ClickHouse has `Tuple(...)` for exactly
    # that, so this cell is the one most likely to move: it is 议题 A's
    # subject, and the answer here is the agreed table's, not a ruling that
    # `Array(T)` is the right carrier for a heterogeneous value.
    tuple: ArrayColumn,
    set: ArrayColumn,
    # A set is an Array with the duplicates already removed by Python; the
    # Array does not re-deduplicate on the server, so "set-ness" is a
    # value-layer property and the storage family is `Array(T)`.
    frozenset: ArrayColumn,
    # Native `Enum8` / `Enum16` storage holding string values, so the value
    # semantics are text: comparison, `IN` and `ORDER BY` render. Two
    # measured facts a caller must not assume away: `ORDER BY` on a native
    # enum is **declaration order**, not lexicographic, and an illegal member
    # is refused by the server (code 691) rather than by a CHECK constraint.
    enum.Enum: StringColumn,
}


class ClickHouseColumnTypeMixin(ColumnTypeMixin):
    """ClickHouse's answer to "which column class does this annotation mean".

    Composed into ``ClickHouseDialect`` **ahead of** ``ColumnTypeMixin``, which
    is where the backend's own answer wins: it overrides
    :meth:`suggested_column_types` and calls ``super()`` for nothing, because
    the one other member of the protocol -- ``suggested_extra_column_types`` --
    has no backend-specific answer here. Core offers no inherited table to fall
    back on, so the ordering only matters for the method this class defines.
    """

    def suggested_column_types(self) -> Dict[Any, Optional[Type[ColumnBase]]]:
        """A fresh copy of :data:`CLICKHOUSE_COLUMN_TYPES`, all eighteen entries.

        Returning a copy is part of the protocol: a caller mutating the answer
        must not corrupt the table the next lookup reads.
        """
        return dict(CLICKHOUSE_COLUMN_TYPES)


__all__ = ["CLICKHOUSE_COLUMN_TYPES", "ClickHouseColumnTypeMixin"]
