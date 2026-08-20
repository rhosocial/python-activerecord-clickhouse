# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/locking.py
from typing import Tuple


class ClickHouseLockingMixin:
    """ClickHouse row-level locking mixin."""

    def supports_for_share(self) -> bool:
        return self.version >= (8, 0, 0)

    def supports_for_update_nowait(self) -> bool:
        return self.version >= (8, 0, 0)

    def supports_for_update_skip_locked(self) -> bool:
        return self.version >= (8, 0, 0)

    def format_for_update_clause(self, clause) -> Tuple[str, tuple]:
        """Format ClickHouse-specific FOR UPDATE clause."""
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.impl.clickhouse.expression.locking import ClickHouseLockStrength

        all_params = []

        strength = getattr(clause, "strength", ClickHouseLockStrength.UPDATE)

        if strength == ClickHouseLockStrength.SHARE:
            if not self.supports_for_share():
                raise UnsupportedFeatureError(self.name, "FOR SHARE (requires ClickHouse 8.0+)")

        sql_parts = [strength.value]

        if clause.of_columns:
            of_parts = []
            for col in clause.of_columns:
                if isinstance(col, str):
                    of_parts.append(self.format_identifier(col))
                else:
                    col_sql, col_params = col.to_sql()
                    of_parts.append(col_sql)
                    all_params.extend(col_params)
            if of_parts:
                sql_parts.append(f"OF {', '.join(of_parts)}")

        if clause.nowait:
            if not self.supports_for_update_nowait():
                raise UnsupportedFeatureError(self.name, "NOWAIT (requires ClickHouse 8.0+)")
            sql_parts.append("NOWAIT")
        elif clause.skip_locked:
            if not self.supports_for_update_skip_locked():
                raise UnsupportedFeatureError(self.name, "SKIP LOCKED (requires ClickHouse 8.0+)")
            sql_parts.append("SKIP LOCKED")

        return " ".join(sql_parts), tuple(all_params)
