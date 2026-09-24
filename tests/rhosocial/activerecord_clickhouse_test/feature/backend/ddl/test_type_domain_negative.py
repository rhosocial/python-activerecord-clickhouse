# tests/rhosocial/activerecord_clickhouse_test/feature/backend/ddl/test_type_domain_negative.py
"""Negative TYPE and DOMAIN DDL contracts for ClickHouse."""

from __future__ import annotations

import pytest

from rhosocial.activerecord.backend.dialect import (
    DataTypeMixin,
    DataTypeSupport,
    DomainMixin,
    DomainSupport,
    UserDefinedTypeMixin,
    UserDefinedTypeSupport,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import Literal
from rhosocial.activerecord.backend.expression.statements import (
    AlterDomainExpression,
    AlterTypeExpression,
    CreateDomainExpression,
    CreateTypeExpression,
    DomainCheckConstraint,
    DomainNullability,
    DomainValueExpression,
    DropDomainDefaultAction,
    DropDomainExpression,
    DropTypeExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    TypeAlterAction,
    TypeDefinition,
)
from rhosocial.activerecord.backend.expression.types import DataType, IntegerType
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.types import (
    ClickHouseEnum8Type,
    ClickHouseEnum16Type,
)
from rhosocial.activerecord.backend.impl.clickhouse.mixins.types import (
    ClickHouseTypeSupportMixin,
)
from rhosocial.activerecord.backend.impl.clickhouse.protocols import (
    ClickHouseSetTypeSupport,
)


class _NegativeTypeDefinition(TypeDefinition):
    @property
    def definition_kind(self) -> str:
        return "negative"


class _NegativeTypeAlterAction(TypeAlterAction):
    @property
    def action_kind(self) -> str:
        return "negative"


TYPE_DOMAIN_SUPPORT_METHODS = (
    "supports_type_objects",
    "supports_create_type",
    "supports_alter_type",
    "supports_drop_type",
    "supports_create_type_if_not_exists",
    "supports_create_type_or_replace",
    "supports_alter_type_if_exists",
    "supports_drop_type_if_exists",
    "supports_multiple_type_alter_actions",
    "supports_domains",
    "supports_create_domain",
    "supports_alter_domain",
    "supports_drop_domain",
    "supports_domain_default",
    "supports_domain_checks",
    "supports_named_domain_checks",
    "supports_multiple_domain_checks",
    "supports_domain_collation",
    "supports_multiple_domain_alter_actions",
    "supports_drop_domain_if_exists",
    "supports_drop_domain_cascade",
    "supports_drop_domain_restrict",
    "supports_unnamed_domain_check_drop",
)

TYPE_FORMATTERS = (
    "format_create_type_statement",
    "format_alter_type_statement",
    "format_drop_type_statement",
    "format_type_definition",
    "format_type_alter_action",
)

DOMAIN_FORMATTERS = (
    "format_create_domain_statement",
    "format_alter_domain_statement",
    "format_drop_domain_statement",
    "format_domain_value_expression",
    "format_domain_check_constraint",
    "format_domain_alter_action",
)


@pytest.fixture
def dialect() -> ClickHouseDialect:
    return ClickHouseDialect(version=(26, 7, 1))


def test_type_and_domain_protocols_and_mixins_are_composed(
    dialect: ClickHouseDialect,
) -> None:
    assert isinstance(dialect, DataTypeSupport)
    assert isinstance(dialect, UserDefinedTypeSupport)
    assert isinstance(dialect, DomainSupport)
    assert isinstance(dialect, UserDefinedTypeMixin)
    assert isinstance(dialect, DomainMixin)

    mro = ClickHouseDialect.__mro__
    for mixin, protocol in (
        (UserDefinedTypeMixin, UserDefinedTypeSupport),
        (DomainMixin, DomainSupport),
    ):
        assert mixin in mro
        assert protocol in mro
        assert mro.index(mixin) < mro.index(protocol)

    assert issubclass(ClickHouseTypeSupportMixin, DataTypeMixin)
    assert issubclass(ClickHouseTypeSupportMixin, DataTypeSupport)
    assert mro.index(ClickHouseTypeSupportMixin) < mro.index(DataTypeSupport)
    assert not issubclass(ClickHouseTypeSupportMixin, UserDefinedTypeMixin)
    assert not issubclass(ClickHouseTypeSupportMixin, DomainMixin)


def test_core_type_and_domain_formatters_own_the_mro() -> None:
    for method_name in TYPE_FORMATTERS:
        assert getattr(ClickHouseDialect, method_name) is getattr(
            UserDefinedTypeMixin,
            method_name,
        )
    for method_name in DOMAIN_FORMATTERS:
        assert getattr(ClickHouseDialect, method_name) is getattr(
            DomainMixin,
            method_name,
        )


def test_schema_level_type_and_domain_support_is_false(
    dialect: ClickHouseDialect,
) -> None:
    for method_name in TYPE_DOMAIN_SUPPORT_METHODS:
        assert getattr(dialect, method_name)() is False, method_name

    for nullability in DomainNullability:
        assert dialect.supports_domain_nullability(nullability) is False

    assert dialect.supported_type_definitions() == ()
    assert dialect.supports_type_definition(_NegativeTypeDefinition) is False
    assert dialect.supports_type_alter_action(_NegativeTypeAlterAction) is False
    assert dialect.supports_alter_domain_action(DropDomainDefaultAction) is False


def test_type_formatters_and_expressions_fail_fast(dialect: ClickHouseDialect) -> None:
    definition = _NegativeTypeDefinition(dialect)
    action = _NegativeTypeAlterAction(dialect)
    expressions = (
        CreateTypeExpression(
            dialect,
            "status",
            definition,
            if_not_exists=True,
        ),
        AlterTypeExpression(
            dialect,
            "status",
            [action],
            if_exists=True,
        ),
        DropTypeExpression(dialect, "status", if_exists=True),
        definition,
        action,
    )

    for method_name, expression in zip(TYPE_FORMATTERS, expressions, strict=True):
        with pytest.raises(UnsupportedFeatureError):
            getattr(dialect, method_name)(expression)
        with pytest.raises(UnsupportedFeatureError):
            expression.to_sql()


def test_domain_formatters_and_expressions_fail_fast(dialect: ClickHouseDialect) -> None:
    condition = DomainValueExpression(dialect) > Literal(
        dialect,
        0,
        inline_literals=True,
    )
    check = DomainCheckConstraint(dialect, condition, name="positive")
    action = DropDomainDefaultAction(dialect)
    expressions = (
        CreateDomainExpression(
            dialect,
            "positive",
            IntegerType(dialect),
            checks=[check],
            collation="en_US",
        ),
        AlterDomainExpression(dialect, "positive", [action]),
        DropDomainExpression(dialect, "positive"),
        DomainValueExpression(dialect),
        check,
        action,
    )

    for method_name, expression in zip(DOMAIN_FORMATTERS, expressions, strict=True):
        with pytest.raises(UnsupportedFeatureError):
            getattr(dialect, method_name)(expression)
        with pytest.raises(UnsupportedFeatureError):
            expression.to_sql()


def test_clickhouse_enum_types_remain_data_types(dialect: ClickHouseDialect) -> None:
    enum8 = ClickHouseEnum8Type(dialect, values=[("active", 1), ("inactive", 0)])
    enum16 = ClickHouseEnum16Type(dialect, values=[("active", 1), ("inactive", 0)])

    for data_type, support_name, sql in (
        (enum8, "supports_data_type_clickhouse_enum8", "Enum8"),
        (enum16, "supports_data_type_clickhouse_enum16", "Enum16"),
    ):
        assert isinstance(data_type, DataType)
        assert not isinstance(data_type, TypeDefinition)
        assert getattr(dialect, support_name)() is True
        rendered, params = data_type.to_sql()
        assert rendered.startswith(sql)
        assert params == ()


def test_set_protocol_is_not_used_as_a_type_domain_contract(
    dialect: ClickHouseDialect,
) -> None:
    assert ClickHouseSetTypeSupport not in ClickHouseDialect.__mro__
    assert not isinstance(dialect, ClickHouseSetTypeSupport)
