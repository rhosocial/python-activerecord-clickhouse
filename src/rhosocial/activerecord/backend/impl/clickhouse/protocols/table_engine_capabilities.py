# clickhouse/protocols/table_engine_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class ClickHouseTableEngineSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_table_engine_clauses(self, storage_options: Optional[Dict[str, Any]]) -> str:
        ...  # pragma: no cover

class ClickHouseQueryClauseSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_final_modifier(self) -> str:
        ...  # pragma: no cover
    def format_array_join_clause(self, array_exprs: List[str], is_left: bool=False) -> str:
        ...  # pragma: no cover
