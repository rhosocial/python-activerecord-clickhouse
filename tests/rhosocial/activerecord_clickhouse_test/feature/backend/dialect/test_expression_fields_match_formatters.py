# tests/rhosocial/activerecord_clickhouse_test/feature/backend/dialect/test_expression_fields_match_formatters.py
"""A formatter may not read a field its statement does not carry.

A statement formatter that reads ``expr.schema_name`` needs the expression to
have that attribute. When the formatter was changed to qualify names and the
expression was not given the field, the result is not wrong SQL -- it is an
``AttributeError`` on a statement that can never be built, which is how
SQLServerColumnstoreIndexExpression reached CI.

These were source scans rather than runtime tests. A scan does not work here:
whether the field exists depends on inheritance reaching core, which lives in
another repository, and on **core_kwargs forwarding. Reading the source of this
repository can see neither, so a scan reported defects that were not there --
two were chased down and both were false alarms -- while a field genuinely
removed still passed. Building the statement answers the question the defect
actually asks: does this statement build, and does the schema reach the SQL?
"""
import importlib
import inspect

import pytest

#: Statement fields a formatter may read that some expression classes carry
#: under a different name. Reading these by their own name is the defect.
#: TruncateExpression names the field `schema`; the DDL statements name it
#: `schema_name`. ClickHouse's TRUNCATE is the one formatter on this backend
#: that reads the alias, so the alias is exercised below rather than excused.
KNOWN_ALIASES = {
    "schema": {"TruncateExpression"},
}


class TestQualifiedStatementsRender:
    """A statement whose formatter qualifies names must build with a schema.

    Checked by building each statement and rendering it, not by scanning
    source. Each case names the statement and how to build it, so adding
    coverage for a newly qualified object type is one entry rather than a new
    mechanism.

    ClickHouse has no schema in the language -- a ``schema_name`` is rendered as
    a database -- and it quotes with backticks, so the expected SQL below
    carries ```app```.`name` where ``app`` was passed in.
    """

    @pytest.fixture
    def dialect(self):
        from rhosocial.activerecord.backend.impl.clickhouse.dialect import (
            ClickHouseDialect,
        )

        return ClickHouseDialect(version=(24, 0, 0))

    def test_create_view_inherits_the_field_from_core(self, dialect):
        """The case a source scan got wrong in both directions.

        CreateViewExpression lives in core and assigns schema_name there. A
        scan of this repository sees the formatter reading the field and no
        assignment at all, so it either misses a field that is there or reports
        one that is not, depending on how it resolves the base. Building it
        settles the question.
        """
        from rhosocial.activerecord.backend.expression import (
            Column,
            CreateViewExpression,
            QueryExpression,
        )

        query = QueryExpression(dialect, [Column(dialect, "id")], from_="orders")
        expr = CreateViewExpression(dialect, view_name="v_orders", query=query)
        assert expr.to_sql()[0] == (
            "CREATE VIEW `v_orders` AS SELECT `id` FROM `orders`"
        ), expr.to_sql()[0]
        qualified = CreateViewExpression(
            dialect, view_name="v_orders", query=query, schema_name="app"
        )
        assert qualified.to_sql()[0] == (
            "CREATE VIEW `app`.`v_orders` AS SELECT `id` FROM `orders`"
        ), qualified.to_sql()[0]

    def test_drop_view(self, dialect):
        from rhosocial.activerecord.backend.expression import DropViewExpression

        expr = DropViewExpression(dialect, view_name="v_orders")
        assert expr.to_sql()[0] == "DROP VIEW `v_orders`", expr.to_sql()[0]
        qualified = DropViewExpression(
            dialect, view_name="v_orders", schema_name="app"
        )
        assert qualified.to_sql()[0] == "DROP VIEW `app`.`v_orders`", (
            qualified.to_sql()[0]
        )

    def test_truncate_reads_the_schema_alias(self, dialect):
        """The one formatter here that reads ``expr.schema``, not ``schema_name``.

        TruncateExpression carries the field under the core alias, so the
        keyword is ``schema`` here. Pinning it means renaming the field in core
        breaks this rather than silently rendering an unqualified name.
        """
        from rhosocial.activerecord.backend.expression import TruncateExpression

        expr = TruncateExpression(dialect, table_name="orders")
        assert expr.to_sql()[0] == "TRUNCATE TABLE `orders`", expr.to_sql()[0]
        qualified = TruncateExpression(dialect, table_name="orders", schema="app")
        assert qualified.to_sql()[0] == "TRUNCATE TABLE `app`.`orders`", (
            qualified.to_sql()[0]
        )

    def test_column_without_a_table_drops_the_schema_loudly(self, dialect):
        """``format_column`` reads the field and then deliberately ignores it.

        ClickHouse qualifies by database, not schema, so a schema on a bare
        column cannot be rendered. The dialect warns instead of raising, which
        is a decision worth holding in place: if the field ever goes missing,
        this fails with AttributeError rather than passing.
        """
        from rhosocial.activerecord.backend.expression import Column

        with pytest.warns(UserWarning, match="dropping schema_name='app'"):
            sql, _ = Column(dialect, "id", schema_name="app").to_sql()
        assert sql == "`id`", sql

        # With a table the qualifier still does not reach the SQL, and no
        # warning is raised: a column reference is table-qualified only.
        qualified, _ = Column(dialect, "id", table="orders", schema_name="app").to_sql()
        assert qualified == "`orders`.`id`", qualified


class TestExpressionSignatures:
    """The expressions this backend's formatters qualify must take the field."""

    @pytest.mark.parametrize(
        "import_path,class_name,field",
        [
            (
                "rhosocial.activerecord.backend.expression.statements.ddl_view",
                "CreateViewExpression",
                "schema_name",
            ),
            (
                "rhosocial.activerecord.backend.expression.statements.ddl_view",
                "DropViewExpression",
                "schema_name",
            ),
            (
                "rhosocial.activerecord.backend.expression.statements.ddl_truncate",
                "TruncateExpression",
                "schema",
            ),
            (
                "rhosocial.activerecord.backend.expression.core",
                "Column",
                "schema_name",
            ),
        ],
    )
    def test_qualified_expression_accepts_schema_field(self, import_path, class_name, field):
        module = importlib.import_module(import_path)
        cls = getattr(module, class_name)
        params = inspect.signature(cls.__init__).parameters
        assert field in params, (
            f"{class_name} is qualified by its formatter, so it needs the "
            f"{field} field; got {list(params)}"
        )
        assert params[field].default is None, (
            f"{class_name} must default {field} to None -- None is what "
            f"means unqualified"
        )
