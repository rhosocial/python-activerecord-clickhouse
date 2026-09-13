# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/constraint.py


class ClickHouseConstraintMixin:
    """ClickHouse constraint support."""

    def supports_primary_key_constraint(self) -> bool:
        """Whether PRIMARY KEY constraint is supported."""
        return True

    def supports_unique_constraint(self) -> bool:
        """ClickHouse does not support UNIQUE constraints."""
        return False

    def supports_not_null_constraint(self) -> bool:
        """Whether NOT NULL constraint is supported."""
        return True

    def supports_foreign_key_constraint(self) -> bool:
        """ClickHouse does not support FOREIGN KEY constraints."""
        return False

    def supports_fk_on_delete(self) -> bool:
        return False

    def supports_fk_on_update(self) -> bool:
        return False

    def supports_add_constraint(self) -> bool:
        """ClickHouse does not support ALTER TABLE ADD CONSTRAINT."""
        return False

    def supports_drop_constraint(self) -> bool:
        """ClickHouse does not support ALTER TABLE DROP CONSTRAINT."""
        return False

    def supports_drop_table_cascade(self) -> bool:
        """ClickHouse DROP TABLE does not support CASCADE."""
        return False

    def supports_drop_table_restrict(self) -> bool:
        """ClickHouse DROP TABLE does not support RESTRICT."""
        return False

    def supports_check_constraint(self) -> bool:
        """Whether CHECK constraints are enforced."""
        return False

    def supports_constraint_enforced(self) -> bool:
        """Whether ENFORCED/NOT ENFORCED constraint control is supported."""
        return False

    def supports_fk_match(self) -> bool:
        """Whether MATCH {SIMPLE|PARTIAL|FULL} is supported."""
        return False

    def supports_deferrable_constraint(self) -> bool:
        """Whether DEFERRABLE constraints are supported."""
        return False

    def supports_generated_column(self) -> bool:
        """Whether generated (computed) columns are supported."""
        return False

    def supports_default_column_value_expression(self) -> bool:
        """Whether DEFAULT column values can use expressions."""
        return True  # ClickHouse supports expressions in DEFAULT values
