# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/dml.py
from typing import Any, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import InsertStatement


class ClickHouseDMLOperationMixin:
    """ClickHouse DML operations mixin.

    ClickHouse does not support INSERT IGNORE, REPLACE INTO, LOAD DATA,
    or ON DUPLICATE KEY UPDATE. All supports_* methods return False and
    format methods raise UnsupportedFeatureError.
    """

    def supports_insert_ignore(self) -> bool:
        return False

    def supports_replace_into(self) -> bool:
        return False

    def supports_load_data(self) -> bool:
        return False

    def format_load_data_statement(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "LOAD DATA",
            suggestion="ClickHouse does not support LOAD DATA INFILE; use INSERT or clickhouse-client --query."
        )

    def format_on_conflict_clause(self, expr: Any) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name, "ON DUPLICATE KEY UPDATE",
            suggestion=(
                "ClickHouse does not support ON DUPLICATE KEY UPDATE; "
                "use INSERT with ReplacingMergeTree or other merge mechanisms."
            ),
        )

    def format_insert_statement(self, expr: "InsertStatement") -> Tuple[str, tuple]:
        """Format a ClickHouse INSERT statement.

        ClickHouse does not support INSERT IGNORE / REPLACE INTO / ON CONFLICT;
        those dialect options raise UnsupportedFeatureError. INSERT ... RETURNING
        is supported.

        Raises:
            TypeError: ``expr.into`` is not a Table. A View or an Index would
                otherwise have its own name rendered as the inserted-into table's.
            UnsupportedFeatureError: ``REPLACE INTO``, ``INSERT IGNORE`` or a
                conflict clause, none of which ClickHouse has.
        """
        if not isinstance(expr.into, Table):
            raise TypeError(
                f"InsertStatement.into must be a Table, "
                f"got {type(expr.into).__name__}"
            )
        if self.strict_validation:
            expr.validate(strict=True)

        # The core node spells these ``or_replace`` / ``or_ignore``; reading
        # the names the contract declares makes the two refusals below real
        # (they used to probe ``replace`` / ``ignore``, fields no InsertStatement
        # carries, so an INSERT OR REPLACE silently rendered as a plain INSERT).
        if expr.or_replace:
            raise UnsupportedFeatureError(
                self.name, "REPLACE INTO",
                suggestion="ClickHouse does not support REPLACE INTO."
            )
        if expr.or_ignore:
            raise UnsupportedFeatureError(
                self.name, "INSERT IGNORE",
                suggestion="ClickHouse does not support INSERT IGNORE."
            )
        if expr.on_conflict:
            raise UnsupportedFeatureError(
                self.name, "ON CONFLICT / ON DUPLICATE KEY",
                suggestion="ClickHouse does not support upsert conflict clauses."
            )

        all_params: List[Any] = []
        table_sql, table_params = expr.into.to_sql()
        all_params.extend(table_params)

        parts = ["INSERT INTO", table_sql]

        if expr.columns:
            columns_sql = "(" + ", ".join([self.format_identifier(c) for c in expr.columns]) + ")"
            parts.append(columns_sql)

        from rhosocial.activerecord.backend.expression.statements import (
            DefaultValuesSource,
            SelectSource,
            ValuesSource,
        )

        if isinstance(expr.source, DefaultValuesSource):
            parts.append("DEFAULT VALUES")
        elif isinstance(expr.source, ValuesSource):
            # A cell is either an expression or a bare host value, and the
            # core owns that decision in one place -- re-rendering the rows
            # here (the old loop called ``val.to_sql()`` unconditionally, so
            # a bare scalar cell crashed) would fork it. ClickHouse's VALUES
            # spelling is the base's, so the whole branch is the delegation.
            source_sql, source_params = self.format_insert_values_source(expr.source)
            parts.append(source_sql)
            all_params.extend(source_params)
        elif isinstance(expr.source, SelectSource):
            s_sql, s_params = expr.source.select_query.to_sql()
            parts.append(s_sql)
            all_params.extend(s_params)

        sql = " ".join(parts)

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)