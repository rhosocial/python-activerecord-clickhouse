# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/function.py
from typing import Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.bases import BaseExpression


class ClickHouseFunctionMixin:
    """ClickHouse function version support."""

    # ClickHouse function version support: function_name -> (min_version, max_version)
    _CLICKHOUSE_FUNCTION_VERSIONS = {
        "round_": (None, None),
        "pow": (None, None),
        "power": (None, None),
        "sqrt": (None, None),
        "mod": (None, None),
        "ceil": (None, None),
        "floor": (None, None),
        "trunc": (None, None),
        "max_": (None, None),
        "min_": (None, None),
        "avg": (None, None),
    }

    def supports_functions(self) -> Dict[str, bool]:
        """Return supported SQL functions as function_name -> bool mapping."""
        from rhosocial.activerecord.backend.expression.functions import (
            __all__ as core_functions,
        )

        expression_constructors = {
            "xmlagg",
            "xmlattributes",
            "xmlcomment",
            "xmlconcat",
            "xmlelement",
            "xmlexists",
            "xmlforest",
            "xmlparse",
            "xmlpi",
            "xmlquery",
            "xmlroot",
            "xmlserialize",
            "xmltable",
        }
        result = {}
        for func_name in core_functions:
            if func_name not in expression_constructors:
                result[func_name] = self._is_clickhouse_function_supported(func_name)
        return result

    def _is_clickhouse_function_supported(self, func_name: str) -> bool:
        """Check if a ClickHouse-specific function is supported based on version."""
        version_range = self._CLICKHOUSE_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True

        min_version, max_version = version_range

        if min_version is not None and self.version < min_version:
            return False

        if max_version is not None and self.version > max_version:
            return False

        return True

    def format_char_length_function(self, expr: "BaseExpression") -> Tuple[str, tuple]:
        """Render ``lengthUTF8(operand)`` -- the character count.

        ClickHouse's ``LENGTH`` answers in **bytes**, so the core's default
        spelling answers a different question than the node asks. Measured
        on the scenario server ``tests/config/clickhouse_scenarios.yaml``
        names ``clickhouse_http`` (ClickHouse 26.7.3.19, HTTP on
        ``127.0.0.1:18682``)::

            SELECT length('héllo')      -- 6: five characters, six UTF-8 bytes
            SELECT lengthUTF8('héllo')  -- 5: the character count
            SELECT CHAR_LENGTH('héllo') -- 5: accepted as an alias on this
                                        --   version; lengthUTF8 is the
                                        --   spelling whose availability
                                        --   spans every version this
                                        --   backend declares

        ``expr.unit`` is deliberately not read, the same choice the core's
        default makes: it records which length semantics the caller asked
        for, and this entry point writes the one spelling that carries the
        character answer.
        """
        operand_sql, operand_params = expr.operand.to_sql()
        sql = f"lengthUTF8({operand_sql})"
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, tuple(operand_params)
