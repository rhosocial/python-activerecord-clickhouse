# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/literal.py
"""ClickHouse's tier-2 value literals.

``SQLDialectBase.format_literal`` is the single entry point for writing a
value as SQL text, and it resolves in three tiers: the portable scalars it
knows, the types a backend spells for itself, and the literal-construction
protocol. This module is ClickHouse's second tier. ClickHouse has two such
types and no more:

* ``bytes`` becomes ``unhex('0102')``. ClickHouse has no blob literal; the
  string functions are byte-oriented, and ``unhex`` is the documented way
  to build one. Measured on the scenario server named by
  ``tests/config/clickhouse_scenarios.yaml`` (``clickhouse_http``:
  **ClickHouse 26.7.3.19 official build**, HTTP on ``127.0.0.1:18682``,
  database ``test_db``)::

      CREATE TABLE probe_tier2_bin (id Int32, s String DEFAULT unhex('0102'))
          ENGINE = MergeTree ORDER BY id     -- accepted
      INSERT INTO probe_tier2_bin (id) VALUES (1)
      SELECT hex(s) FROM probe_tier2_bin    -- '0102': the exact bytes

* ``UUID`` becomes the bare quoted text. The ``UUID`` type parses the
  canonical form from a string, so a ``UUID DEFAULT
  '01234567-89ab-cdef-0123-456789abcdef'`` was measured accepted and a row
  read back the same text through ``toString(u)``.

**``timedelta`` is deliberately left to the base's refusal.** The grammar's
``INTERVAL`` is date-arithmetic syntax -- ``INTERVAL n UNIT``, with the unit
part of the spelling -- while a ``timedelta`` carries no unit, so a renderer
would have to invent one. The measurements that close the question, on the
same instance::

    CREATE TABLE probe_iv (id Int32, s String DEFAULT INTERVAL '1' DAY) ...
    INSERT ... -> SELECT s = '1'   -- accepted, but the unit is silently
                                    -- dropped: the stored value is the
                                    -- number, not the span
    SELECT INTERVAL '1' DAY + INTERVAL '2' HOUR
        -> toTypeName = Tuple(IntervalDay, IntervalHour)
                                 -- a mixed-unit span is not one interval

``IntervalDay`` columns exist and accept ``DEFAULT INTERVAL '3' DAY`` (read
back as ``3``), which makes the omission a real choice rather than an
absence: the one spelling that works ties the literal to the column's own
interval unit, and the host value carries no unit to tie it to. Leaving
``timedelta`` out of this override is what makes the base's explicit
failure the answer.

Everything else falls through to the base implementation, which is where
the portable forms -- NULL, booleans, numbers, quoted ISO dates -- and the
literal-construction protocol live. Those portable forms were measured
accepted verbatim as DEFAULTs on the same instance (``Date DEFAULT
'2026-01-01'``, ``DateTime DEFAULT '2026-01-01 12:00:00'``, ``Bool DEFAULT
TRUE`` / ``FALSE``), so the base spellings are ClickHouse's own and no
override is added for them.
"""

import uuid
from typing import Any


class ClickHouseLiteralValueMixin:
    """ClickHouse's tier-2 branches of :meth:`format_literal`.

    Composed **ahead of** ``SQLDialectBase`` in the dialect's base list --
    unlike every other ClickHouse mixin, which only adds methods the base
    lacks and may sit anywhere. This one overrides ``format_literal``, and a
    mixin placed after the class it overrides never wins.
    """

    def format_literal(self, value: Any) -> str:
        """Render *value* as inline SQL text, ClickHouse's spelling where it
        has one.

        Args:
            value: The host value to write into the statement.

        Returns:
            The escaped literal text, without a bind parameter.

        Raises:
            TypeError: The base implementation refuses a type ClickHouse has
                no literal form for (``timedelta`` among them, on purpose --
                see the module docstring), and this is the same refusal.
        """
        if isinstance(value, (bytes, bytearray)):
            # Lowercase hex, the form ``bytes.hex()`` spells; ``unhex``
            # accepts either case.
            return f"unhex('{bytes(value).hex()}')"
        if isinstance(value, uuid.UUID):
            return self.format_literal(str(value))
        return super().format_literal(value)
