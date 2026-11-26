# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/explain.py
from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import ExplainStatement


class ClickHouseExplainMixin:
    """ClickHouse EXPLAIN statement support.

    ClickHouse renders ``EXPLAIN [ANALYZE] [FORMAT=<format>] <statement>``.
    It has no ``VERBOSE`` / ``COSTS`` / ``BUFFERS`` / ``TIMING`` / ``SETTINGS``
    / ``WAL`` options, so those switches answer ``False``; only ``TEXT``,
    ``JSON`` and ``TREE`` are offered through the shared ``ExplainFormat``
    vocabulary.
    """

    def supports_explain_analyze(self) -> bool:
        """Whether EXPLAIN ANALYZE is supported.

        Accepted syntax-wise from ClickHouse 26.7; older maintained lines
        (25.8 LTS, 26.3 LTS) reject the ANALYZE keyword. Answered through
        ``version_at_least`` so an unadapted dialect says "no" instead of
        raising just to report a capability.
        """
        return self.version_at_least((26, 7, 0))

    def supports_explain_verbose(self) -> bool:
        """ClickHouse EXPLAIN has no VERBOSE option."""
        return False

    def supports_explain_costs(self) -> bool:
        """ClickHouse EXPLAIN has no COSTS option."""
        return False

    def supports_explain_buffers(self) -> bool:
        """ClickHouse EXPLAIN has no BUFFERS option."""
        return False

    def supports_explain_timing(self) -> bool:
        """ClickHouse EXPLAIN has no TIMING option."""
        return False

    def supports_explain_settings(self) -> bool:
        """ClickHouse EXPLAIN has no SETTINGS option."""
        return False

    def supports_explain_wal(self) -> bool:
        """ClickHouse EXPLAIN has no WAL option."""
        return False

    def supports_explain_format_text(self) -> bool:
        """Whether ``EXPLAIN ... FORMAT=TEXT`` is supported."""
        return True

    def supports_explain_format_json(self) -> bool:
        """Whether ``EXPLAIN ... FORMAT=JSON`` is supported."""
        return True

    def supports_explain_format_xml(self) -> bool:
        """Whether ``EXPLAIN ... FORMAT=XML`` is supported."""
        return False

    def supports_explain_format_yaml(self) -> bool:
        """Whether ``EXPLAIN ... FORMAT=YAML`` is supported."""
        return False

    def supports_explain_format_tree(self) -> bool:
        """Whether ``EXPLAIN ... FORMAT=TREE`` is supported."""
        return True

    def supports_explain_format_traditional(self) -> bool:
        """Whether ``EXPLAIN ... FORMAT=TRADITIONAL`` is supported."""
        return False

    def format_explain_statement(self, expr: "ExplainStatement") -> tuple:
        """Build the ClickHouse EXPLAIN SQL string and return (sql, params).

        ClickHouse syntax variants:
        - ``EXPLAIN <stmt>``
        - ``EXPLAIN <stmt> FORMAT=TEXT|JSON|TREE``
        - ``EXPLAIN ANALYZE <stmt>``
        - ``EXPLAIN PIPELINE <stmt>``

        Raises:
            UnsupportedFeatureError: A requested option is not available on
                ClickHouse, or the requested format is outside the TEXT /
                JSON / TREE set.
        """
        from rhosocial.activerecord.backend.expression.statements import (
            ExplainFormat,
            ExplainType,
        )

        statement_sql, statement_params = expr.statement.to_sql()
        options = expr.options
        parts = ["EXPLAIN"]

        if options is not None:
            if options.analyze:
                if not self.supports_explain_analyze():
                    raise UnsupportedFeatureError(self.name, "EXPLAIN ANALYZE")
                parts.append("ANALYZE")

            if options.format is not None:
                probe = {
                    ExplainFormat.TEXT: self.supports_explain_format_text,
                    ExplainFormat.JSON: self.supports_explain_format_json,
                    ExplainFormat.XML: self.supports_explain_format_xml,
                    ExplainFormat.YAML: self.supports_explain_format_yaml,
                    ExplainFormat.TREE: self.supports_explain_format_tree,
                    ExplainFormat.TRADITIONAL: self.supports_explain_format_traditional,
                }[options.format]
                if not probe():
                    raise UnsupportedFeatureError(
                        self.name, f"EXPLAIN FORMAT {options.format.value}"
                    )
                parts.append(f"FORMAT={options.format.value}")
            elif options.type is not None and options.type == ExplainType.QUERY_PLAN:
                pass

            if options.verbose:
                raise UnsupportedFeatureError(self.name, "EXPLAIN VERBOSE")
            if not options.costs:
                raise UnsupportedFeatureError(self.name, "EXPLAIN COSTS OFF")
            if options.buffers:
                raise UnsupportedFeatureError(self.name, "EXPLAIN BUFFERS")
            if options.timing:
                raise UnsupportedFeatureError(self.name, "EXPLAIN TIMING")
            if options.settings:
                raise UnsupportedFeatureError(self.name, "EXPLAIN SETTINGS")
            if options.wal:
                raise UnsupportedFeatureError(self.name, "EXPLAIN WAL")

        return f"{' '.join(parts)} {statement_sql}", statement_params
