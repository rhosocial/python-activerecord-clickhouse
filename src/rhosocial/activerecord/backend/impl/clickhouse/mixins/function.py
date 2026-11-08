# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/function.py
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.bases import BaseExpression


class ClickHouseFunctionMixin:
    """ClickHouse function version support."""

    def _engine_function(
        self, name: str, *operands, alias: Optional[str] = None
    ) -> "BaseExpression":
        """``name(operands...)`` with the name spelled the way ClickHouse spells it.

        The shared :meth:`~...dialect.mixins.function.format_function_call`
        upper-cases every function name it renders, and on this engine that is
        right for exactly the SQL-standard spellings -- ``SUM``, ``COUNT``,
        ``MIN``, ``MAX``, which the aggregate factory registers
        ``Case::Insensitive`` so any casing resolves. It is wrong for every
        camelCase name: ``groupUniqArray``, ``toTypeName`` and ``currentUser``
        are registered ``Case::Sensitive`` (the default), and the combinator
        suffixes (``OrNull``, ``If``, ``State`` ...) are matched against the
        tail of the name *as written*. So ``GROUPUNIQARRAY`` and
        ``CURRENTUSER`` land in neither the exact map nor the lowercased one,
        and the server answers ``Function with name `X` does not exist`` --
        which is how ``MINORNULL`` failed all five data-profile CI jobs.

        A name the renderer cannot case correctly is therefore handed to SQL as
        text, and the node is a
        :class:`~...expression.operators.RawSQL` rather than a
        :class:`~...expression.core.FunctionCall` precisely so no companion
        code path re-applies the case rule to it. The *operands* still render
        through their own nodes -- a column is quoted and catalog-qualified by
        the dialect's identifier renderer, and a literal binds where
        ``Literal`` says it binds -- so only the optional operator text is
        raw; the whole call never is.

        Args:
            name: The function name, in the engine's own spelling.
            *operands: Expression nodes for the arguments.
            alias: Optional result alias.

        Returns:
            A ``RawSQL`` node rendering ``name(operand_sql, ...)``, carrying
            the parameters the operands collected, in argument order.
        """
        parts: List[str] = []
        collected: List = []
        for operand in operands:
            part_sql, part_params = operand.to_sql()
            parts.append(part_sql)
            collected.extend(part_params)
        sql = f"{name}({', '.join(parts)})"
        if alias:
            sql = f"{sql} AS {self.format_identifier(alias)}"
        from rhosocial.activerecord.backend.expression.operators import RawSQL

        return RawSQL(self, sql, tuple(collected))

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
        """Check if a ClickHouse-specific function is supported based on version.

        Both bounds are answered through :meth:`version_at_least`, which never
        raises: a capability check is a question, not a formatter, so an
        unadapted dialect reports "not confirmed" rather than failing.
        """
        version_range = self._CLICKHOUSE_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True

        min_version, max_version = version_range

        if min_version is not None and not self.version_at_least(min_version):
            return False

        if max_version is not None:
            # "at most max_version" is the complement of "at least the first
            # version after it"; version components are integers, so no
            # version falls strictly between the two tuples.
            first_after = (max_version[0], max_version[1], max_version[2] + 1)
            if self.version_at_least(first_after):
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
