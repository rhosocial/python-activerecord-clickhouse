# src/rhosocial/activerecord/backend/impl/clickhouse/explain/types.py
"""
ClickHouse-specific EXPLAIN result types.

ClickHouse's default tabular EXPLAIN output has 12 fixed columns:
  id, select_type, table, partitions, type, possible_keys,
  key, key_len, ref, rows, filtered, Extra
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from rhosocial.activerecord.backend.explain.types import BaseExplainResult

try:
    from typing import Literal
except ImportError:  # Python 3.8
    from typing_extensions import Literal  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Index-usage label (mirrors SQLite's IndexUsage for API consistency)
# ---------------------------------------------------------------------------
IndexUsage = Literal["full_scan", "index_with_lookup", "covering_index", "unknown"]


class ClickHouseExplainRow(BaseModel):
    """One row from ClickHouse's default tabular EXPLAIN output.

    Column semantics:
    - id           : SELECT identifier (query block number)
    - select_type  : Query type (SIMPLE, PRIMARY, SUBQUERY, DERIVED, ...)
    - table        : Table name or alias
    - partitions   : Matching partitions (NULL if not partitioned)
    - type         : Join/access type (ALL, index, range, ref, eq_ref, const, ...)
    - possible_keys: Indexes that *could* be used
    - key          : Index actually chosen by the optimizer
    - key_len      : Bytes used from the chosen index
    - ref          : Column(s) or constants compared against the index key
    - rows         : Estimated number of rows to examine
    - filtered     : Estimated percentage of rows to survive WHERE conditions
    - extra        : Additional information (e.g. "Using index", "Using filesort")
    """

    id: Optional[int] = None
    select_type: Optional[str] = None
    table: Optional[str] = None
    partitions: Optional[str] = None
    type: Optional[str] = None
    possible_keys: Optional[str] = None
    key: Optional[str] = None
    key_len: Optional[str] = None
    ref: Optional[str] = None
    rows: Optional[int] = None
    filtered: Optional[float] = None
    extra: Optional[str] = Field(None, alias="Extra")

    model_config = {"populate_by_name": True}


class ClickHouseExplainResult(BaseExplainResult):
    """ClickHouse EXPLAIN result (default tabular format).

    Contains index-usage analysis helpers that mirror the SQLite equivalents
    for a consistent cross-backend API.
    """

    rows: List[ClickHouseExplainRow] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Index-usage analysis
    # ------------------------------------------------------------------

    def analyze_index_usage(self) -> IndexUsage:
        """Analyse index usage from the tabular EXPLAIN output.

        Heuristic (applied to the first data row with a ``type`` value):

        * ``type == "ALL"`` → full_scan
        * ``key IS NULL`` (and type is not "ALL") → full_scan
          (e.g. possible_keys present but optimizer chose none)
        * ``extra`` contains ``"Using index"`` and key is set → covering_index
        * ``key IS NOT NULL`` and type not "ALL" → index_with_lookup

        Returns one of: ``"full_scan"``, ``"index_with_lookup"``,
        ``"covering_index"``, or ``"unknown"``.
        """
        if not self.rows:
            return "unknown"

        # Inspect the first row that carries a meaningful access type
        for row in self.rows:
            if row.type is None:
                continue

            access_type = row.type.upper()

            # Explicit full table scan
            if access_type == "ALL":
                return "full_scan"

            # No index chosen
            if not row.key:
                return "full_scan"

            # Index chosen – check for covering index
            extra = (row.extra or "").upper()
            if "USING INDEX" in extra:
                return "covering_index"

            return "index_with_lookup"

        return "unknown"

    @property
    def is_full_scan(self) -> bool:
        """``True`` when no index is used (full table scan)."""
        return self.analyze_index_usage() == "full_scan"

    @property
    def is_index_used(self) -> bool:
        """``True`` when any index is used."""
        return self.analyze_index_usage() in ("index_with_lookup", "covering_index")

    @property
    def is_covering_index(self) -> bool:
        """``True`` when a covering index eliminates table access."""
        return self.analyze_index_usage() == "covering_index"
