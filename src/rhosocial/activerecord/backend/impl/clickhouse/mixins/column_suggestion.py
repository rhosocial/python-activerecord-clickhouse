# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/column_suggestion.py
"""Which column class ClickHouse suggests for each common Python type.

The full eighteen-entry table of
:data:`~rhosocial.activerecord.backend.expression.column_suggestions.COLUMN_TYPE_ENTRIES`,
plus the one version-gated narrowing ClickHouse has. Everything here is a
**column** decision -- what operations a value carries -- and none of it is a
storage decision: whether ``Array(T)`` or ``JSON`` spells the column is the DDL
layer's separate answer (see :class:`ClickHouseTypeSupportMixin`), and this
table never reads it.

Evidence
--------
Every cell below is backed by a probe against a live **ClickHouse 26.7.3.19**
server (HTTP ``127.0.0.1:18682``, ``clickhouse-connect`` 1.9.0), recorded in the
core plan directory and, for the measured matrix, in this repository's
``.claude/plan/2026-10-08/secondary-gaps-investigation.md`` appendix C:

* ``suggested-pairing-array.md`` §A -- the native-array column of the matrix;
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
  fallback this entry used to fall back on no longer exists; if 议题 A decides
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
"""

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, FrozenSet, Type

from rhosocial.activerecord.backend.dialect.mixins import ColumnSuggestionMixin
from rhosocial.activerecord.backend.expression.column_suggestions import (
    NEUTRAL_COLUMN_TYPE_SUGGESTIONS,
)
from rhosocial.activerecord.backend.expression.column_types import (
    ArrayColumn,
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)


class ClickHouseColumnSuggestionMixin(ColumnSuggestionMixin):
    """ClickHouse's answer to the column-type suggestion protocol.

    Composed into ``ClickHouseDialect`` **ahead of** ``ColumnSuggestionMixin``,
    which is where C3 linearisation puts the narrower answer: it overrides
    :attr:`COLUMN_TYPE_SUGGESTIONS` and :meth:`supports_column_operation`, and
    both call ``super()`` for everything they do not speak to.
    """

    #: First ClickHouse line carrying the native ``JSON`` data type, and
    #: therefore the first on which a ``JSONColumn``'s *document* is a document
    #: rather than text.
    #:
    #: This is the version this backend already declares for JSON elsewhere --
    #: :meth:`ClickHouseJSONFunctionMixin.supports_json_type` and
    #: ``_JSON_FUNCTION_VERSIONS`` both answer ``26.0`` -- so the capability
    #: narrowing and the DDL-side gate cannot drift apart. It is **not** a
    #: measured boundary: the probe battery ran on 26.7.3.19 only, and no older
    #: server was available to find the exact first version. What is measured is
    #: that on 26.7 the native type needs no experimental setting and plain DDL
    #: declares it; below it ClickHouse has no JSON type at all and the JSON
    #: surface is carried by the ``JSONExtract*`` / ``JSONHas`` /
    #: ``isValidJSON`` function family over ``String`` storage.
    _JSON_TYPE_MIN_VERSION = (26, 0, 0)

    #: The operations on ``JSONColumn`` that need that native type.
    #:
    #: ``json_value`` is the chainable one: core defines it as yielding **JSON**
    #: that can be navigated again, against ``json_path``'s terminal scalar.
    #: On a native ``JSON`` column ClickHouse's ``JSONExtractRaw`` answers with
    #: the JSON type, so the contract holds. Below 26.0 the same function over
    #: ``String`` storage answers with text, which is a different answer to the
    #: same question -- offering it would hand back a value the framework types
    #: as a document while the server produced a string, so it is narrowed
    #: rather than offered as a text-shaped impostor.
    _JSON_TYPE_OPERATIONS: FrozenSet[str] = frozenset({"json_value"})

    #: The full table. Every entry of the protocol list is answered; there is no
    #: ``UNSUPPORTED`` here, and that is a finding rather than an omission.
    #:
    #: ClickHouse has every capability the protocol's other backends lack a
    #: default for: a native array, a native JSON type, and the ``ILIKE``
    #: operator that only PostgreSQL shares. The two ends that *do* refuse a
    #: default -- Firebird's ``dict`` and ``list`` (no JSON functions, no arrays
    #: at all) and MySQL 5.6's (no JSON functions) -- have nothing here to
    #: refuse. ``dict`` stays answerable below the JSON type's first version
    #: because the ``JSONExtract`` family, not the type, is what carries it.
    #:
    #: Deviations from :data:`NEUTRAL_COLUMN_TYPE_SUGGESTIONS` are exactly two
    #: cells, both about telling apart numbers core keeps together:
    #: ``float`` and ``Decimal`` are :class:`FloatColumn` and
    #: :class:`DecimalColumn` rather than the single :class:`NumericColumn` core
    #: answers for both. Everything else below restates core's baseline, and the
    #: group comments say what the ClickHouse measurement behind it was.
    COLUMN_TYPE_SUGGESTIONS: Dict[Any, Type[ColumnBase]] = {
        **NEUTRAL_COLUMN_TYPE_SUGGESTIONS,
        # --- numbers core keeps together -----------------------------------
        # §1 calls `float` the whole Float family here (Float32 / Float64 /
        # BFloat16) and `Decimal` the Decimal32/64/128/256 family; the
        # operation set of the two is what FloatColumn and DecimalColumn
        # respectively say, and the widths are the DDL layer's business.
        # Measured on 26.7 (suggested-pairing-numeric.md): Float64 yields inf
        # on overflow and carries nan natively, and `AVG` of a Decimal answers
        # Float64 rather than a Decimal -- so the two are genuinely different
        # surfaces here, not one generic number.
        float: FloatColumn,
        decimal.Decimal: DecimalColumn,
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
        # below it -- which is why this entry is never UNSUPPORTED. Measured on
        # 26.7: plain DDL declares the type with no experimental setting, scalar
        # path `JSONExtractString`, document path `JSONExtractRaw`, has-key
        # `JSONHas`, array length `JSONLength(toString(doc), 'arr')`, validity
        # `isValidJSON(toString(doc))`, equality `toString(doc) = ?`. Note the
        # `toString` in two of those: passing the JSON column straight to
        # `JSONLength` silently returns 0. Capability gating for this entry is
        # in `supports_column_operation` below, not here.
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

    def supports_column_operation(self, column_name: str, op: str) -> bool:
        """Whether ``op`` is available on ``column_name`` here, at this version.

        ClickHouse narrows exactly one operation, and only by version. The rest
        of the answer is core's default True, which for this backend is the
        measured truth rather than an omission: appendix D-③ of the investigation
        records that the "core provides, this backend cannot do" list is nearly
        empty -- the array function family and ``ILIKE`` are both native. A
        backend that over-declares hides an incompatibility; one that narrows
        without evidence refuses queries that work. So nothing is narrowed here
        that a probe did not show.

        The one narrowing is :attr:`_JSON_TYPE_OPERATIONS`, gated on
        :attr:`_JSON_TYPE_MIN_VERSION`. Reading ``self.version`` raises
        ``DialectNotAdaptedException`` on a dialect that has not been adapted
        yet, which is the same trade every other version-gated switch here makes
        (``supports_json_type``, ``supports_explain_analyze``): the whole table
        still answers without a version, and only the gated query needs one.

        Args:
            column_name: the column class name, as ``type(column).__name__``.
            op: the operation name, as the attribute that provides it -- so
                ``"ilike"``, ``"json_path"``, ``"array_length"``.

        Returns:
            False only for the version-gated JSON operations; core's default
            otherwise.
        """
        if column_name == JSONColumn.__name__ and op in self._JSON_TYPE_OPERATIONS:
            return self.version >= self._JSON_TYPE_MIN_VERSION
        return super().supports_column_operation(column_name, op)
