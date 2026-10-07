# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/cte.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression import bases


class ClickHouseCTEMixin:
    """ClickHouse CTE (Common Table Expression) support."""

    def supports_basic_cte(self) -> bool:
        """Basic CTEs (WITH clause) are supported in ClickHouse."""
        return True

    def supports_recursive_cte(self) -> bool:
        """Recursive CTEs are supported in ClickHouse."""
        return True

    def supports_materialized_cte(self) -> bool:
        """ClickHouse accepts the ``AS MATERIALIZED`` CTE hint.

        The negative spelling, ``AS NOT MATERIALIZED``, is a syntax error on
        ClickHouse 26.7 (``Code: 62``, measured); :meth:`format_cte_expression`
        refuses it by name rather than rendering it.
        """
        return True

    def format_cte_expression(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Format a CTE definition, refusing the spelling ClickHouse lacks.

        The states core renders are kept: neither hint renders nothing and
        ``materialized`` renders ``AS MATERIALIZED`` (accepted by the server).
        ``not_materialized`` has no ClickHouse spelling and is refused by name.

        Raises:
            UnsupportedFeatureError: ``not_materialized``.
        """
        if expr.not_materialized:
            raise UnsupportedFeatureError(
                self.name,
                "CTE NOT MATERIALIZED",
                "ClickHouse spells only AS MATERIALIZED; NOT MATERIALIZED is a "
                "syntax error (measured: Code 62).",
            )
        return super().format_cte_expression(expr)
