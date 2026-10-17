# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/typed_value.py
"""ClickHouse's spellings for the value types whose literal form is its own.

ClickHouse agrees with the base on NULL, booleans, numbers, strings and
dates, so nothing is overridden for those. Measured on the scenario server
named by ``tests/config/clickhouse_scenarios.yaml`` (``clickhouse_http``:
**ClickHouse 26.7.3.19 official build**, HTTP on ``127.0.0.1:18682``,
database ``test_db``)::

    CREATE TABLE probe_tier1_dates (id Int32, d Date DEFAULT '2026-01-01')
        ENGINE = MergeTree ORDER BY id          -- accepted
    ALTER TABLE probe_tier1_dates ADD COLUMN ts DateTime DEFAULT '2026-01-01 12:00:00'
                                              -- accepted
    CREATE TABLE probe_tier1_bool (id Int32, b Bool DEFAULT TRUE)
        ENGINE = MergeTree ORDER BY id          -- accepted
    ALTER TABLE probe_tier1_bool ADD COLUMN nb Bool DEFAULT FALSE
                                              -- accepted

so the base tier-1 spellings (quoted ISO dates, ``TRUE``/``FALSE``) are
this engine's own and need no override. Two value types differ:

* **binary** -- ``unhex('0102')``. ClickHouse has no blob literal; the
  string functions are byte-oriented, and ``unhex`` is the documented way
  to build one. A ``String DEFAULT unhex('0102')`` was measured accepted,
  and a row inserted without the column read back ``hex(s) = '0102'``.
* **UUID** -- the bare quoted text. The ``UUID`` type parses the canonical
  form from a string, so a ``UUID DEFAULT '01234567-89ab-cdef-0123-456789abcdef'``
  was measured accepted and a row read back the same text through
  ``toString(u)``.

**INTERVAL stays unimplemented on purpose.** The grammar's ``INTERVAL`` is
date-arithmetic syntax -- ``INTERVAL n UNIT``, with the unit part of the
spelling -- while the node carries a bare ``timedelta``, so a renderer would
have to invent the unit the caller never named. The measurements that close
the question, all on the same 26.7.3.19 instance::

    CREATE TABLE probe_iv (id Int32, s String DEFAULT INTERVAL '1' DAY) ...
    INSERT ... -> SELECT s = '1'      -- accepted, but the unit is silently
                                        dropped: the stored value is the
                                        number, not the span
    SELECT INTERVAL '1' DAY + INTERVAL '2' HOUR
        -> toTypeName = Tuple(IntervalDay, IntervalHour)
                                     -- a mixed-unit span is not one
                                        interval: the sum is a tuple, so a
                                        single literal for an arbitrary
                                        timedelta does not exist

``IntervalDay`` columns exist and accept ``DEFAULT INTERVAL '3' DAY``
(read back as ``3``), which makes the omission a real choice rather than
an absence: the one spelling that works ties the literal to the column's
own interval unit, and the value node carries no unit to tie it to. That
is why this mixin defines no ``format_interval_value`` -- leaving the
method absent is what makes the base's explicit failure the answer.
"""

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.values import TypedValue


class ClickHouseTypedValueMixin:
    """ClickHouse's tier-2 value literals.

    Stands alone rather than inheriting :class:`TypedValueMixin`, like every
    other ClickHouse mixin: the dialect composes the specific mixin ahead of
    the generic one, and these two methods win by that position. Inheriting
    would put the base ahead of the other generic mixins and make the
    ordering the dialect has to reason about depend on this class instead.
    """

    def format_binary_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """``unhex('0102')`` -- the byte string built from its hex text.

        ClickHouse has no blob literal form; ``unhex`` is the documented
        constructor and the one the measured DEFAULT accepted (see the module
        docstring). Lowercase hex, the form ``bytes.hex()`` spells.
        """
        if not type(expr).inline_params:
            return self._bind_value(expr)
        return f"unhex('{bytes(expr.value).hex()}')", ()

    def format_uuid_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """A UUID as quoted text -- the ``UUID`` type parses the canonical form.

        No cast suffix and no ``toUUID`` call: both were unnecessary where the
        measurement ran, and the bare quoted text is what the column's
        ``DEFAULT`` accepted (see the module docstring).
        """
        if not type(expr).inline_params:
            return self._bind_value(expr)
        return self.format_literal(str(expr.value)), ()
