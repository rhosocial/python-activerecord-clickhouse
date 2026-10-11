# src/rhosocial/activerecord/backend/impl/clickhouse/expression/optimizer_hint.py
"""ClickHouse optimizer hint expressions.

Models per-statement optimizer hints in the ``/*+ ... */`` comment syntax,
including ``SET_VAR`` hints that name a setting and a value.

**The comment parses on 26.7.3.19 and the contents are discarded**, so there is
no version floor and no setting to name a version for. Five measurements:

* ``SELECT /*+ SET_VAR(max_threads=1) */ 1`` succeeds — the comment is
  recognised, so "ClickHouse cannot parse ``/*+ ... */``" would be wrong.
* ``SELECT /*+ SET_VAR(totally_bogus_zzz=1) */ 1`` also succeeds, so the hint's
  setting name is not validated at parse time.
* ``SELECT /*+ SET_VAR(max_block_size=7) */ getSetting('max_block_size')``
  returns ``65409``, the session default: the hint has **no effect**. (The same
  query with an explicit ``SETTINGS max_block_size=7`` does change it.)
* ``SELECT count() FROM system.settings`` is 1715 on this server, and
  ``WHERE name ILIKE '%optimizer%'`` matches **none** of them.
* ``SELECT 1 SETTINGS optimizer_switch='hypergraph_optimizer=on'`` —
  ``Code: 115. DB::Exception: Setting optimizer_switch is neither a builtin
  setting nor started with the prefix 'SQL_' registered for user-defined
  settings. (UNKNOWN_SETTING)``. There is no ``optimizer_switch`` here to carry
  a ``hypergraph_optimizer`` flag.

So the expression class below is a fail-fast switch, not a renderer:
``supports_optimizer_hint()`` and ``supports_hypergraph_optimizer()`` are both
``False`` and ``format_optimizer_hint`` raises ``UnsupportedFeatureError``. The
ClickHouse way to set something per statement is the ``SETTINGS`` clause on the
statement itself (``https://clickhouse.com/docs/reference/statements/select``,
"Settings in SELECT Query"), which this backend renders for the settings it
actually models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect.base import SQLDialectBase


class OptimizerHintType(Enum):
    """Types of ClickHouse optimizer hints."""

    SET_VAR = "SET_VAR"


@dataclass
class SetVarHint:
    """A SET_VAR optimizer hint."""

    variable: str
    value: str


class ClickHouseOptimizerHintExpression(BaseExpression):
    """A MySQL-style ``/*+ ... */`` optimizer hint — accepted but inert in ClickHouse.

    Kept as a fail-fast switch: ``to_sql()`` raises ``UnsupportedFeatureError``
    through the dialect. The server parses the comment and then ignores it (see
    the module docstring for the measurements, including the ``SET_VAR`` case
    that leaves ``max_block_size`` at its default), so a hint this backend
    rendered would be a comment that does nothing — which is worse than a
    refusal, because it looks like it worked.

    Usage (of the switch, not of a renderer):
        hint = ClickHouseOptimizerHintExpression(dialect, [
            SetVarHint("optimizer_switch", "hypergraph_optimizer=on")
        ])
        hint.to_sql()  # raises UnsupportedFeatureError
    """

    def __init__(self, dialect: "SQLDialectBase", hints: List[SetVarHint]):
        super().__init__(dialect)
        self.hints = hints

    @property
    def format_method(self) -> str:
        return "format_optimizer_hint"
