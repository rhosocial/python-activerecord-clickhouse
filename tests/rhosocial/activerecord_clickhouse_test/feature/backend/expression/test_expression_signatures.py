# tests/rhosocial/activerecord_clickhouse_test/feature/backend/expression/test_expression_signatures.py
"""
Tests for ClickHouse expression signature compliance.

This module verifies that expression classes follow the format signature
compliance pattern where each expression declares a format_method property
that returns the name of the dialect method used to render it.

The partition expressions it previously covered
(``ClickHousePartitionNameListExpression``, a MySQL ``p0, p1, ...`` name list)
are gone: ClickHouse has no DDL-declared partition names to list. What is
covered now is the partition-id clause family, which is ClickHouse's own.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHouseAttachPartitionExpression,
    ClickHouseDetachPartitionExpression,
    ClickHouseDropPartitionExpression,
)


@pytest.fixture(scope="module")
def dialect():
    """A dialect carrying the scenario server's version shape (26.7.3)."""
    return ClickHouseDialect(version=(26, 7, 3))


class TestClickHousePartitionIdExpressions:
    """Signature compliance for the three ``ALTER TABLE ... <verb> PARTITION ID`` clauses."""

    EXPRESSIONS = (
        (ClickHouseDropPartitionExpression, "format_drop_partition_statement", "DROP"),
        (ClickHouseDetachPartitionExpression, "format_detach_partition_statement", "DETACH"),
        (ClickHouseAttachPartitionExpression, "format_attach_partition_statement", "ATTACH"),
    )

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_format_method_names_the_dialect_formatter(self, dialect, expr_class, formatter, verb):
        """Each class declares exactly the ``format_*`` that renders it."""
        expr = expr_class(dialect, "visits", "202601")
        assert expr.format_method == formatter
        # Read off the class too, the way the structural sweep does.
        assert expr_class.format_method.fget(expr_class) == formatter
        # ...and the declared constant stays in step with the verb the shared
        # renderer uses, so the three clauses cannot drift apart.
        assert formatter == f"format_{expr_class.verb.lower()}_partition_statement"

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_declared_formatter_exists_on_the_dialect(self, dialect, expr_class, formatter, verb):
        assert callable(getattr(dialect, formatter, None))

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_renders_the_clickhouse_clause(self, dialect, expr_class, formatter, verb):
        """Rendering targets the ``PARTITION ID`` spelling, quoted as a literal."""
        expr = expr_class(dialect, "visits", "202601")
        sql, params = expr.to_sql()
        assert sql == f"ALTER TABLE `visits` {verb} PARTITION ID '202601'"
        assert params == ()

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_partition_id_is_stored_verbatim(self, dialect, expr_class, formatter, verb):
        """The id is kept as given, so ``system.parts.partition_id`` is the source of truth."""
        expr = expr_class(dialect, "visits", "202601_3_3_0")
        assert expr.partition_id == "202601_3_3_0"
        assert "'202601_3_3_0'" in expr.to_sql()[0]

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_quote_inside_partition_id_is_escaped(self, dialect, expr_class, formatter, verb):
        """An embedded quote is doubled, not passed through (see format_literal)."""
        sql, _ = expr_class(dialect, "visits", "a'b").to_sql()
        assert "'a''b'" in sql

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_schema_qualifies_the_table(self, dialect, expr_class, formatter, verb):
        """A ``schema`` argument renders the two-part ClickHouse identifier."""
        sql, _ = expr_class(dialect, "visits", "202601", schema="db1").to_sql()
        assert sql.startswith("ALTER TABLE `db1`.`visits` ")

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_empty_table_raises(self, dialect, expr_class, formatter, verb):
        with pytest.raises(ValueError, match="table must be a non-empty string"):
            expr_class(dialect, "  ", "202601")

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_empty_partition_id_raises(self, dialect, expr_class, formatter, verb):
        with pytest.raises(ValueError, match="partition_id must be a non-empty string"):
            expr_class(dialect, "visits", "   ")

    @pytest.mark.parametrize("expr_class,formatter,verb", EXPRESSIONS)
    def test_non_string_partition_id_raises(self, dialect, expr_class, formatter, verb):
        with pytest.raises(TypeError, match="partition_id must be a string"):
            expr_class(dialect, "visits", 202601)