# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_identifier_quoting.py
"""
Comprehensive tests for ClickHouseDialect identifier quoting.

Covers format_identifier backtick quoting, internal-backtick escaping,
need_quote passthrough, reserved-word detection (case-insensitive),
IdentifierQuotingWarning emission, and balanced-quote security
invariants. Also exercises format_column integration with
format_identifier for table-qualified and aliased column references.
"""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.warnings import IdentifierQuotingWarning


class TestClickHouseIdentifierQuoting:
    """Test ClickHouseDialect format_identifier and reserved words."""

    # ------------------------------------------------------------------ #
    #  format_identifier – default (need_quote=True)                     #
    # ------------------------------------------------------------------ #

    def test_format_identifier_default_backtick_quotes(self):
        d = ClickHouseDialect()
        assert d.format_identifier("users") == "`users`"

    def test_format_identifier_preserves_case(self):
        d = ClickHouseDialect()
        assert d.format_identifier("MyTable") == "`MyTable`"
        assert d.format_identifier("ALLCAPS") == "`ALLCAPS`"

    def test_format_identifier_with_underscores(self):
        d = ClickHouseDialect()
        assert d.format_identifier("user_name") == "`user_name`"

    def test_format_identifier_with_digits(self):
        d = ClickHouseDialect()
        assert d.format_identifier("table1") == "`table1`"

    def test_format_identifier_with_leading_digit(self):
        d = ClickHouseDialect()
        assert d.format_identifier("1table") == "`1table`"

    # ------------------------------------------------------------------ #
    #  format_identifier – need_quote=False                              #
    # ------------------------------------------------------------------ #

    def test_format_identifier_need_quote_false(self):
        d = ClickHouseDialect()
        assert d.format_identifier("users", need_quote=False) == "users"

    def test_format_identifier_need_quote_false_preserves_case(self):
        d = ClickHouseDialect()
        assert d.format_identifier("MyTable", need_quote=False) == "MyTable"

    def test_format_identifier_need_quote_false_no_escaping(self):
        d = ClickHouseDialect()
        assert d.format_identifier("my`table", need_quote=False) == "my`table"

    # ------------------------------------------------------------------ #
    #  format_identifier – internal backtick escaping                    #
    # ------------------------------------------------------------------ #

    def test_format_identifier_escapes_internal_backticks(self):
        d = ClickHouseDialect()
        assert d.format_identifier("my`table") == "`my``table`"

    def test_format_identifier_escapes_multiple_internal_backticks(self):
        d = ClickHouseDialect()
        assert d.format_identifier("a``b") == "`a````b`"

    def test_format_identifier_escapes_consecutive_backticks(self):
        d = ClickHouseDialect()
        assert d.format_identifier("a```b") == "`a``````b`"

    def test_format_identifier_escapes_leading_trailing_backtick(self):
        d = ClickHouseDialect()
        assert d.format_identifier("`col`") == "```col```"

    def test_format_identifier_only_backticks_double(self):
        d = ClickHouseDialect()
        # "``" → escaped="````" → wrapped "``````"
        assert d.format_identifier("``") == "``````"

    def test_format_identifier_single_backtick_only(self):
        d = ClickHouseDialect()
        # "`" → escaped="``" → wrapped "````"
        assert d.format_identifier("`") == "````"

    def test_format_identifier_triple_backtick(self):
        d = ClickHouseDialect()
        # "```" → escaped="``````" → wrapped "````````"
        assert d.format_identifier("```") == "````````"

    def test_format_identifier_no_backticks_unchanged(self):
        d = ClickHouseDialect()
        assert d.format_identifier("simple") == "`simple`"

    # ------------------------------------------------------------------ #
    #  format_identifier – edge cases                                    #
    # ------------------------------------------------------------------ #

    def test_format_identifier_empty_string(self):
        d = ClickHouseDialect()
        assert d.format_identifier("") == "``"

    def test_format_identifier_empty_string_no_quote(self):
        d = ClickHouseDialect()
        assert d.format_identifier("", need_quote=False) == ""

    def test_format_identifier_whitespace_identifier(self):
        d = ClickHouseDialect()
        assert d.format_identifier("my table") == "`my table`"

    def test_format_identifier_special_characters(self):
        d = ClickHouseDialect()
        assert d.format_identifier("col-name") == "`col-name`"
        assert d.format_identifier("col.name") == "`col.name`"

    def test_format_identifier_unicode(self):
        d = ClickHouseDialect()
        assert d.format_identifier("用户表") == "`用户表`"

    # ------------------------------------------------------------------ #
    #  reserved_words – type and content                                 #
    # ------------------------------------------------------------------ #

    def test_reserved_words_is_frozenset(self):
        d = ClickHouseDialect()
        assert isinstance(d.reserved_words, frozenset)

    def test_reserved_words_contains_clickhouse_specific(self):
        d = ClickHouseDialect()
        assert "engine" in d.reserved_words
        assert "partition" in d.reserved_words
        assert "merge" in d.reserved_words
        assert "settings" in d.reserved_words
        assert "sample" in d.reserved_words
        assert "final" in d.reserved_words

    def test_reserved_words_all_lowercase(self):
        d = ClickHouseDialect()
        for word in d.reserved_words:
            assert word == word.lower(), f"Reserved word is not lowercase: {word!r}"

    # ------------------------------------------------------------------ #
    #  is_reserved_word                                                   #
    # ------------------------------------------------------------------ #

    def test_is_reserved_word_case_insensitive(self):
        d = ClickHouseDialect()
        assert d.is_reserved_word("SELECT") is True
        assert d.is_reserved_word("select") is True
        assert d.is_reserved_word("Select") is True
        assert d.is_reserved_word("sElEcT") is True

    def test_is_reserved_word_non_reserved(self):
        d = ClickHouseDialect()
        assert d.is_reserved_word("users") is False
        assert d.is_reserved_word("my_table") is False

    def test_is_reserved_word_clickhouse_specific(self):
        d = ClickHouseDialect()
        assert d.is_reserved_word("ENGINE") is True
        assert d.is_reserved_word("engine") is True
        assert d.is_reserved_word("FINAL") is True
        assert d.is_reserved_word("SAMPLE") is True
        assert d.is_reserved_word("SETTINGS") is True

    def test_is_reserved_word_empty_string(self):
        d = ClickHouseDialect()
        assert d.is_reserved_word("") is False

    # ------------------------------------------------------------------ #
    #  IdentifierQuotingWarning emission                                 #
    # ------------------------------------------------------------------ #

    def test_reserved_word_warning_emitted(self):
        d = ClickHouseDialect()
        with pytest.warns(IdentifierQuotingWarning, match="select"):
            d.format_identifier("select", need_quote=False)

    def test_reserved_word_warning_uppercase_emitted(self):
        d = ClickHouseDialect()
        with pytest.warns(IdentifierQuotingWarning, match="SELECT"):
            d.format_identifier("SELECT", need_quote=False)

    def test_no_warning_for_non_reserved_word(self):
        d = ClickHouseDialect()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", IdentifierQuotingWarning)
            d.format_identifier("users", need_quote=False)

    def test_no_warning_when_need_quote_true(self):
        d = ClickHouseDialect()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", IdentifierQuotingWarning)
            d.format_identifier("select", need_quote=True)

    def test_warning_message_contains_dialect_name(self):
        d = ClickHouseDialect()
        with pytest.warns(IdentifierQuotingWarning, match="ClickHouse"):
            d.format_identifier("select", need_quote=False)

    def test_warning_message_contains_identifier(self):
        d = ClickHouseDialect()
        with pytest.warns(IdentifierQuotingWarning, match="'insert'"):
            d.format_identifier("insert", need_quote=False)

    # ------------------------------------------------------------------ #
    #  Balanced quotes – security invariant                              #
    # ------------------------------------------------------------------ #

    def test_balanced_quotes_security(self):
        d = ClickHouseDialect()
        for ident in ["users", "my`table", "a``b"]:
            result = d.format_identifier(ident)
            assert result.count("`") % 2 == 0, f"Unbalanced backticks: {result}"

    def test_balanced_quotes_empty_string(self):
        d = ClickHouseDialect()
        result = d.format_identifier("")
        assert result.count("`") % 2 == 0

    def test_balanced_quotes_only_backticks(self):
        d = ClickHouseDialect()
        for ident in ["`", "``", "```", "````", "`````"]:
            result = d.format_identifier(ident)
            assert result.count("`") % 2 == 0, (
                f"Unbalanced backticks for {ident!r}: {result}"
            )

    # ------------------------------------------------------------------ #
    #  Dialect instance independence                                     #
    # ------------------------------------------------------------------ #

    def test_separate_instances_independent(self):
        d1 = ClickHouseDialect()
        d2 = ClickHouseDialect()
        assert d1.format_identifier("test") == d2.format_identifier("test")
        assert d1.reserved_words == d2.reserved_words

    # ------------------------------------------------------------------ #
    #  format_column integration                                         #
    # ------------------------------------------------------------------ #

    def _make_expr(self, table=None, name="col", alias=None):
        """Build a lightweight expression-like object for format_column."""
        from types import SimpleNamespace
        return SimpleNamespace(table=table, name=name, alias=alias)

    def test_format_column_column_only(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table=None, name="id")
        sql, params = d.format_column(expr)
        assert sql == "`id`"
        assert params == ()

    def test_format_column_table_qualified(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table="users", name="email")
        sql, params = d.format_column(expr)
        assert sql == "`users`.`email`"
        assert params == ()

    def test_format_column_with_alias(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table="users", name="email", alias="e")
        sql, params = d.format_column(expr)
        assert sql == "`users`.`email` AS `e`"
        assert params == ()

    def test_format_column_reserved_table_name(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table="select", name="id")
        sql, params = d.format_column(expr)
        assert sql == "`select`.`id`"
        assert params == ()

    def test_format_column_reserved_column_name(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table=None, name="order")
        sql, params = d.format_column(expr)
        assert sql == "`order`"
        assert params == ()

    def test_format_column_escapes_backtick_in_table(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table="my`table", name="col")
        sql, params = d.format_column(expr)
        assert sql == "`my``table`.`col`"

    def test_format_column_escapes_backtick_in_column(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table="t", name="my`col")
        sql, params = d.format_column(expr)
        assert sql == "`t`.`my``col`"

    def test_format_column_escapes_backtick_in_alias(self):
        d = ClickHouseDialect()
        expr = self._make_expr(table="t", name="col", alias="a`lias")
        sql, params = d.format_column(expr)
        assert sql == "`t`.`col` AS `a``lias`"
