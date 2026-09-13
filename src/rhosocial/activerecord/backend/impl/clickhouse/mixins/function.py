# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/function.py
from typing import Dict


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
