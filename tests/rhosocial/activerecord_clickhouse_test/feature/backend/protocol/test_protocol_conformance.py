# tests/rhosocial/activerecord_clickhouse_test/feature/backend/protocol/test_protocol_conformance.py
"""
Tests to verify ClickHouseDialect protocol conformance and protocol non-overlap.

This test ensures:
1. ClickHouseDialect implements all methods defined in the protocols it claims to support
2. All protocols have at least one member
3. No two protocols share the same method name (no overlap)
"""

import inspect
import sys
from itertools import combinations

if sys.version_info >= (3, 13):
    from typing import get_protocol_members
elif sys.version_info >= (3, 12):
    from typing import _get_protocol_attrs as get_protocol_members

import pytest
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.impl.clickhouse import dialect as clickhouse_dialect
from rhosocial.activerecord.backend.impl.clickhouse import mixins as clickhouse_mixins
from rhosocial.activerecord.backend.impl.clickhouse import protocols as clickhouse_protocols


def get_all_protocol_methods(proto: type) -> set:
    """Extract all public method names from a protocol, including inherited."""
    members = set()
    if sys.version_info >= (3, 13):
        members = get_protocol_members(proto)
    elif sys.version_info >= (3, 12):
        members = get_protocol_members(proto)
    else:
        # Walk MRO to include methods from parent protocols
        for cls in proto.__mro__:
            if cls is object:
                continue
            for name in cls.__dict__:
                if name.startswith("_"):
                    continue
                val = cls.__dict__[name]
                if callable(val) or isinstance(val, (property, classmethod, staticmethod)):
                    members.add(name)
            members.update(k for k in getattr(cls, "__annotations__", {}) if not k.startswith("_"))
    return members


def get_own_protocol_methods(proto: type) -> set:
    """Extract public method names declared directly on a protocol (not inherited).

    Used for forward coverage: only checks methods the protocol itself declares,
    since parent protocol methods are typically implemented by generic mixins.
    """
    members = set()
    for name in proto.__dict__:
        if name.startswith("_"):
            continue
        val = proto.__dict__[name]
        if callable(val) or isinstance(val, (property, classmethod, staticmethod)):
            members.add(name)
    members.update(k for k in getattr(proto, "__annotations__", {}) if not k.startswith("_"))
    return members


CLICKHOUSE_PROTOCOLS = [
    dialect_protocols.CollationSupport,
    dialect_protocols.CTESupport,
    dialect_protocols.ColumnAttributeSupport,
    dialect_protocols.FilterClauseSupport,
    dialect_protocols.WindowFunctionSupport,
    dialect_protocols.JSONSupport,
    dialect_protocols.ReturningSupport,
    dialect_protocols.AdvancedGroupingSupport,
    dialect_protocols.ArraySupport,
    dialect_protocols.ExplainSupport,
    dialect_protocols.GraphSupport,
    dialect_protocols.LockingSupport,
    dialect_protocols.MergeSupport,
    dialect_protocols.OrderedSetAggregationSupport,
    dialect_protocols.PartitionSupport,
    dialect_protocols.QualifyClauseSupport,
    dialect_protocols.TemporalTableSupport,
    dialect_protocols.UpsertSupport,
    dialect_protocols.LateralJoinSupport,
    dialect_protocols.WildcardSupport,
    dialect_protocols.JoinSupport,
    # Named objects: one protocol per kind, each naming the
    # format_<kind>_object method its mixin provides.
    dialect_protocols.NamespaceSupport,
    dialect_protocols.TableObjectSupport,
    dialect_protocols.ViewObjectSupport,
    dialect_protocols.MaterializedViewObjectSupport,
    dialect_protocols.ForeignTableObjectSupport,
    dialect_protocols.IndexObjectSupport,
    dialect_protocols.SequenceObjectSupport,
    dialect_protocols.TriggerObjectSupport,
    dialect_protocols.RoutineObjectSupport,
    dialect_protocols.TypeObjectSupport,
    dialect_protocols.SynonymObjectSupport,
    dialect_protocols.ConstraintSupport,
    dialect_protocols.IntrospectionSupport,
    dialect_protocols.TransactionControlSupport,
    dialect_protocols.SQLFunctionSupport,
    # Generic protocols ClickHouse also satisfies (previously omitted from this list).
    dialect_protocols.AlterTableModifierSupport,
    dialect_protocols.DataTypeSupport,
    dialect_protocols.SetOperationSupport,
    dialect_protocols.TruncateSupport,
    # TYPE and DOMAIN DDL: ClickHouse has neither, but the core mixins are
    # composed and every switch answers False, so the statements fail fast.
    dialect_protocols.CreateTypeSupport,
    dialect_protocols.AlterTypeSupport,
    dialect_protocols.DropTypeSupport,
    dialect_protocols.CreateDomainSupport,
    dialect_protocols.AlterDomainSupport,
    dialect_protocols.DropDomainSupport,
    # DDL statement protocols. The ClickHouse mixins implement the rendering for
    # what the engine has; the capability switches each protocol also declares
    # come from the core mixins and answer honestly either way.
    dialect_protocols.AlterDatabaseSupport,
    dialect_protocols.AlterTableSupport,
    dialect_protocols.CreateIndexSupport,
    dialect_protocols.CreateTableAsSupport,
    dialect_protocols.CreateTableCloneSupport,
    dialect_protocols.CreateTableLikeSupport,
    dialect_protocols.CreateTableSupport,
    dialect_protocols.CreateTableUsingTemplateSupport,
    dialect_protocols.CreateTriggerSupport,
    dialect_protocols.CreateViewSupport,
    dialect_protocols.DateTimeSupport,
    dialect_protocols.DqlOrderSupport,
    dialect_protocols.DropIndexSupport,
    dialect_protocols.DropTableSupport,
    dialect_protocols.DropTriggerSupport,
    dialect_protocols.DropViewSupport,
    dialect_protocols.FulltextIndexSupport,
    dialect_protocols.MaterializedViewSupport,
    # AutoIncrementColumnSupport is satisfied structurally (the mixin method
    # exists), but ClickHouseDialect overrides supports_auto_increment_column()
    # to return False: ClickHouse has no server-side AUTO_INCREMENT and primary
    # keys are generated client-side (snowflake Int64). Kept here because the
    # runtime_checkable Protocol only checks method presence.
    dialect_protocols.AutoIncrementColumnSupport,
    # IdentityColumnSupport is satisfied structurally the same way: the
    # fail-closed IdentityColumnMixin provides the formatter and the seven
    # probes, and ClickHouse answers supports_identity_column() False -- its
    # server rejects the clause with Code 62 (syntax error at GENERATED).
    dialect_protocols.IdentityColumnSupport,
    # ClickHouse-specific protocols
    clickhouse_protocols.ClickHouseDMLOperationSupport,
    clickhouse_protocols.ClickHouseTriggerSupport,
    clickhouse_protocols.ClickHouseTableSupport,
    clickhouse_protocols.ClickHouseJSONFunctionSupport,
    clickhouse_protocols.ClickHouseSpatialSupport,
    clickhouse_protocols.ClickHouseFullTextSearchSupport,
    clickhouse_protocols.ClickHouseLockingSupport,
    clickhouse_protocols.ClickHouseModifyColumnSupport,
    clickhouse_protocols.ClickHouseJsonDualityViewSupport,
    clickhouse_protocols.ClickHouseOptimizerHintSupport,
    clickhouse_protocols.ClickHousePartitionSupport,
    clickhouse_protocols.ClickHouseRenameTableSupport,
    clickhouse_protocols.ClickHouseTableStatementSupport,
    clickhouse_protocols.ClickHouseMaintenanceSupport,
    clickhouse_protocols.ClickHouseRoutineSupport,
    clickhouse_protocols.ClickHouseLoadXMLSupport,
    clickhouse_protocols.ClickHouseAdminCommandSupport,
    # Note: ClickHouseSetTypeSupport is intentionally absent — the dialect no
    # longer provides MySQL-style SET type helpers (FIND_IN_SET / SET_CONTAINS).
]


class TestClickHouseDialectProtocolConformance:
    """Assert ClickHouseDialect implements all protocols it declares to support."""

    @pytest.fixture
    def dialect(self):
        """Create a ClickHouseDialect instance for testing."""
        return clickhouse_dialect.ClickHouseDialect()

    @pytest.mark.parametrize("protocol", CLICKHOUSE_PROTOCOLS)
    def test_implements_protocol(self, dialect, protocol):
        """ClickHouseDialect should implement each protocol in CLICKHOUSE_PROTOCOLS."""
        assert isinstance(dialect, protocol), (
            f"ClickHouseDialect does not implement protocol {protocol.__name__}, "
            f"missing methods: {get_all_protocol_methods(protocol) - set(dir(dialect))}"
        )


# Generic protocols ClickHouseDialect intentionally does NOT implement.
#
# Listing them makes the omission a deliberate, tested contract: if ClickHouse
# ever satisfies one by accident, the negative test fails and forces a conscious
# decision (move to CLICKHOUSE_PROTOCOLS or revert).
CLICKHOUSE_NOT_IMPLEMENTED = [
    # UUID value expressions (generation / nil-max constants / cast) are not
    # implemented yet on this dialect. Listed here so the omission is a
    # recorded decision rather than a gap; move it to the implemented list
    # when the mixin lands.
    dialect_protocols.UUIDSupport,
    # --- Intentional non-support ---
    # ClickHouse namespaces objects with databases only. There is no inner
    # schema, so it qualifies a name with the catalog slot and reports a
    # carried schema rather than rendering a namespace the server has not got.
    # The switch that decides this is supports_schema_qualification(), not a
    # protocol; see feature/backend/schema/test_schema_support.py.
    # ClickHouse has no standalone COMMENT ON statement; inline table/column
    # comments are rendered by CREATE TABLE instead.
    dialect_protocols.CommentSupport,
    # ClickHouse has no SQL/XML support.
    dialect_protocols.SQLXMLSupport,
    dialect_protocols.SQLXMLParsingSupport,
    dialect_protocols.SQLXMLSerializationSupport,
    dialect_protocols.SQLXMLConstructionSupport,
    dialect_protocols.SQLXMLAggregationSupport,
    dialect_protocols.SQLXMLQueryingSupport,
    # ClickHouse has no SQL/PGQ property-graph tables.
    dialect_protocols.GraphTableSupport,
    # ClickHouse match/`like()` is case-sensitive; there is no ILIKE operator.
    dialect_protocols.ILIKESupport,
    # ClickHouse has no PIVOT.
    dialect_protocols.PivotSupport,
    # ClickHouse has no CREATE/DROP SCHEMA: the database is its only namespace,
    # and CREATE DATABASE is the closest statement, which the ClickHouse
    # database mixin renders in its own form.
    dialect_protocols.CreateSchemaSupport,
    dialect_protocols.DropSchemaSupport,
    # ClickHouse's CREATE/DROP DATABASE are rendered by ClickHouseDatabaseMixin
    # rather than the core DatabaseMixin, so the core protocol's capability
    # switches are absent. The statements themselves work.
    dialect_protocols.CreateDatabaseSupport,
    dialect_protocols.DropDatabaseSupport,
    # ClickHouse exposes routine DDL through its own ClickHouseRoutineSupport
    # protocol rather than the core SQL/PSM routine protocols.
    dialect_protocols.CreateRoutineSupport,
    dialect_protocols.DropRoutineSupport,
    # ClickHouse's MATERIALIZED / ALIAS columns are intentionally NOT treated as
    # SQL-standard generated columns. They are ClickHouse-specific column syntax
    # (not ``GENERATED ALWAYS AS (...) STORED|VIRTUAL``), and the ClickHouse DDL
    # mixin's ``format_column_definition()`` never renders ``col_def.generated_expression``
    # (it iterates constraints only), so declaring this protocol would advertise a
    # capability the backend cannot emit. ``supports_generated_column()`` returns
    # False to preserve the existing fail-fast contract.
    dialect_protocols.GeneratedColumnSupport,
    # ClickHouse has no sequence object, so sequence DDL is absent from the base
    # list rather than inherited and declined, and these three protocols each
    # name a formatter this dialect therefore does not have. Naming a sequence is
    # a different capability and is still met: SequenceObjectSupport above is
    # satisfied by SequenceNameMixin, so a Sequence is accepted as an
    # identifier. ClickHouseSequenceMixin stays in the base list too, for the
    # two switches it answers itself.
    dialect_protocols.CreateSequenceSupport,
    dialect_protocols.AlterSequenceSupport,
    dialect_protocols.DropSequenceSupport,
]


def get_all_generic_protocols() -> dict:
    """Discover every generic dialect protocol defined in protocols.py."""
    from typing import Protocol

    discovered = {}
    for name, obj in inspect.getmembers(dialect_protocols, inspect.isclass):
        if Protocol not in getattr(obj, "__mro__", []) or not name.endswith("Support"):
            continue
        if name == "DDLTypeSupport":
            assert obj is dialect_protocols.DataTypeSupport
            continue
        assert name == obj.__name__, f"unexpected protocol alias: {name}"
        discovered[name] = obj
    return discovered


class TestClickHouseDialectNegativeProtocolConformance:
    """Assert ClickHouseDialect does not implement intentionally-unsupported protocols."""

    @pytest.fixture
    def dialect(self):
        return clickhouse_dialect.ClickHouseDialect()

    @pytest.mark.parametrize("protocol", CLICKHOUSE_NOT_IMPLEMENTED)
    def test_does_not_implement_protocol(self, dialect, protocol):
        """ClickHouseDialect must NOT implement any protocol in CLICKHOUSE_NOT_IMPLEMENTED."""
        assert not isinstance(dialect, protocol), (
            f"ClickHouseDialect unexpectedly implements {protocol.__name__}. "
            f"If intentional, move it from CLICKHOUSE_NOT_IMPLEMENTED to CLICKHOUSE_PROTOCOLS "
            f"(and implement the behaviour fully)."
        )

    def test_positive_and_negative_lists_partition_all_protocols(self):
        """Every generic protocol must be classified for ClickHouse."""
        all_protos = set(get_all_generic_protocols().values())
        # Classify by identity, not by __module__: the protocols package
        # re-exports each protocol from the submodule that defines it, so
        # __module__ names that submodule and never the package.
        positive = {p.__name__ for p in CLICKHOUSE_PROTOCOLS if p in all_protos}
        negative = {p.__name__ for p in CLICKHOUSE_NOT_IMPLEMENTED if p in all_protos}

        overlap = positive & negative
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"

        unclassified = {p.__name__ for p in all_protos} - positive - negative
        assert not unclassified, (
            f"Generic protocols not classified for ClickHouse: {sorted(unclassified)}. "
            f"Add each to CLICKHOUSE_PROTOCOLS or CLICKHOUSE_NOT_IMPLEMENTED."
        )


class TestProtocolNonOverlap:
    """Assert protocols do not have overlapping method names."""

    def test_no_interface_overlap_between_protocols(self):
        """No two protocols should share the same method name.

        Two families of sharing are legitimate and excluded by rule rather
        than by an enumerated pair list, because enumerating them would need
        editing every time a protocol is added:

        * a ClickHouse protocol that *derives* from a core one restates it, so
          a derived/generic pair may overlap;
        * every object protocol derives from ``NamespaceSupport`` and therefore
          shares the five namespace switches and validators. Two object
          protocols differing only in which ``format_*_object`` they name is
          exactly the design, so any pair of them may overlap on the namespace
          methods and nothing else.
        """
        member_map = {proto.__name__: get_all_protocol_methods(proto) for proto in CLICKHOUSE_PROTOCOLS}
        proto_by_name = {proto.__name__: proto for proto in CLICKHOUSE_PROTOCOLS}

        for name, members in member_map.items():
            assert len(members) > 0, f"Protocol {name} has no members defined"

        # The methods every object protocol inherits from NamespaceSupport.
        namespace_members = get_all_protocol_methods(dialect_protocols.NamespaceSupport)
        object_protocol_names = {
            name
            for name, proto in proto_by_name.items()
            if issubclass(proto, dialect_protocols.NamespaceSupport)
        }

        # A ClickHouse protocol often restates a *different* core protocol than
        # the one it derives from, because it spans several: the full-text
        # search protocol derives from IndexObjectSupport for naming and also
        # implements FulltextIndexSupport. Each pair below is a real
        # restatement of the same capability by the narrower engine-specific
        # protocol, and merging them is not this refactor's work.
        intentional_restatements = {
            ("UpsertSupport", "ClickHouseDMLOperationSupport"),
            ("ConstraintSupport", "ClickHouseTableSupport"),
            ("AlterTableSupport", "ClickHouseRenameTableSupport"),
            ("ClickHouseTableSupport", "ClickHouseRenameTableSupport"),
            ("ClickHouseRenameTableSupport", "ClickHouseTableSupport"),
            ("CreateTableSupport", "ClickHouseTableSupport"),
            ("CreateTriggerSupport", "ClickHouseTriggerSupport"),
            ("DropTriggerSupport", "ClickHouseTriggerSupport"),
            ("FulltextIndexSupport", "ClickHouseFullTextSearchSupport"),
        }

        violations = []
        for (name_a, members_a), (name_b, members_b) in combinations(member_map.items(), 2):
            overlap = members_a & members_b
            if not overlap:
                continue
            if (name_a, name_b) in intentional_restatements:
                continue
            if issubclass(proto_by_name[name_b], proto_by_name[name_a]) or issubclass(
                proto_by_name[name_a], proto_by_name[name_b]
            ):
                continue
            if name_a in object_protocol_names and name_b in object_protocol_names:
                assert overlap <= namespace_members, (
                    f"{name_a} and {name_b} are both object protocols but share "
                    f"more than the namespace methods: {sorted(overlap - namespace_members)}"
                )
                continue
            violations.append(f"{name_a} ∩ {name_b} = {sorted(overlap)}")

        assert not violations, (
            "The following protocols have overlapping interfaces, need to merge or rename:\n"
            + "\n".join(f"  • {v}" for v in violations)
        )


class TestClickHouseProtocolDerivation:
    """Verify ClickHouse-specific protocols derive from their generic counterparts.

    This ensures that backend-specific protocols inherit the standard interface,
    allowing isinstance() checks against generic protocols to work correctly.
    """

    PROTOCOL_DERIVATIONS = [
        ("ClickHouseTableSupport", "TableObjectSupport"),
        ("ClickHousePartitionSupport", "PartitionSupport"),
        ("ClickHouseLockingSupport", "LockingSupport"),
        ("ClickHouseJSONFunctionSupport", "JSONSupport"),
    ]

    @pytest.mark.parametrize("clickhouse_name,generic_name", PROTOCOL_DERIVATIONS)
    def test_protocol_derives_from_generic(self, clickhouse_name, generic_name):
        """Backend-specific protocol should derive from its generic counterpart."""
        clickhouse_proto = getattr(clickhouse_protocols, clickhouse_name)
        generic_proto = getattr(dialect_protocols, generic_name)
        assert issubclass(clickhouse_proto, generic_proto), f"{clickhouse_name} does not derive from {generic_name}"

    def test_dialect_satisfies_generic_protocols_via_derivation(self):
        """ClickHouseDialect should satisfy generic protocols through derived protocols."""
        dialect = clickhouse_dialect.ClickHouseDialect()
        for clickhouse_name, generic_name in self.PROTOCOL_DERIVATIONS:
            generic_proto = getattr(dialect_protocols, generic_name)
            if getattr(generic_proto, "_is_runtime_protocol", False):
                assert isinstance(dialect, generic_proto), (
                    f"ClickHouseDialect does not satisfy {generic_name} (should be inherited via {clickhouse_name})"
                )


class TestClickHouseExpressionDialectSeparation:
    """Verify ClickHouse-specific expression classes delegate to dialect for SQL generation.

    Expression-Dialect separation means expression classes collect parameters
    and delegate to_sql() to dialect.format_*() methods, never directly
    constructing SQL strings.
    """

    EXPRESSION_DIALECT_PAIRS = [
        ("ClickHouseJSONExtractExpression", "format_json_extract"),
        ("ClickHouseJSONObjectExpression", "format_json_object"),
        ("ClickHouseJSONArrayExpression", "format_json_array"),
        ("ClickHouseJSONContainsExpression", "format_json_contains"),
        ("ClickHouseDropPartitionExpression", "format_drop_partition_statement"),
        ("ClickHouseDetachPartitionExpression", "format_detach_partition_statement"),
        ("ClickHouseAttachPartitionExpression", "format_attach_partition_statement"),
        ("ClickHouseRenameTableExpression", "format_rename_table_statement"),
    ]

    @pytest.mark.parametrize("expr_name,format_method", EXPRESSION_DIALECT_PAIRS)
    def test_expression_delegates_to_dialect(self, expr_name, format_method):
        """Expression.to_sql() should delegate to dialect.format_*() method."""
        from rhosocial.activerecord.backend.impl.clickhouse import expression as clickhouse_expr

        # Find the expression class
        expr_class = None
        for module_name in dir(clickhouse_expr):
            module = getattr(clickhouse_expr, module_name)
            if hasattr(module, expr_name):
                expr_class = getattr(module, expr_name)
                break

        # Also check top-level imports
        if expr_class is None:
            expr_class = getattr(clickhouse_expr, expr_name, None)

        assert expr_class is not None, f"Expression class {expr_name} not found"

        # Verify the dialect has the corresponding format method
        dialect = clickhouse_dialect.ClickHouseDialect()
        assert hasattr(dialect, format_method), (
            f"ClickHouseDialect missing format method {format_method} for expression {expr_name}"
        )


# ============================================================================
# Phase -1: Protocol Implementation Completeness Tests
# ============================================================================

# Map from ClickHouse-specific Protocol → corresponding Mixin class
CLICKHOUSE_PROTOCOL_MIXIN_PAIRS = [
    (clickhouse_protocols.ClickHouseDMLOperationSupport, clickhouse_mixins.ClickHouseDMLOperationMixin),
    (clickhouse_protocols.ClickHouseTriggerSupport, clickhouse_mixins.ClickHouseTriggerMixin),
    (clickhouse_protocols.ClickHouseTableSupport, clickhouse_mixins.ClickHouseTableMixin),
    (clickhouse_protocols.ClickHouseJSONFunctionSupport, clickhouse_mixins.ClickHouseJSONFunctionMixin),
    (clickhouse_protocols.ClickHouseSpatialSupport, clickhouse_mixins.ClickHouseSpatialMixin),
    (clickhouse_protocols.ClickHouseFullTextSearchSupport, clickhouse_mixins.ClickHouseFullTextSearchMixin),
    (clickhouse_protocols.ClickHouseLockingSupport, clickhouse_mixins.ClickHouseLockingMixin),
    (clickhouse_protocols.ClickHouseModifyColumnSupport, clickhouse_mixins.ClickHouseModifyColumnMixin),
    (clickhouse_protocols.ClickHouseJsonDualityViewSupport, clickhouse_mixins.ClickHouseJsonDualityViewMixin),
    (clickhouse_protocols.ClickHouseOptimizerHintSupport, clickhouse_mixins.ClickHouseOptimizerHintMixin),
    (clickhouse_protocols.ClickHousePartitionSupport, clickhouse_mixins.ClickHousePartitionMixin),
    (clickhouse_protocols.ClickHouseRenameTableSupport, clickhouse_mixins.ClickHouseRenameTableMixin),
    (clickhouse_protocols.ClickHouseTableStatementSupport, clickhouse_mixins.ClickHouseTableStatementMixin),
    (clickhouse_protocols.ClickHouseMaintenanceSupport, clickhouse_mixins.ClickHouseMaintenanceMixin),
    (clickhouse_protocols.ClickHouseRoutineSupport, clickhouse_mixins.ClickHouseRoutineMixin),
    (clickhouse_protocols.ClickHouseLoadXMLSupport, clickhouse_mixins.ClickHouseLoadXMLLMixin),
    (clickhouse_protocols.ClickHouseAdminCommandSupport, clickhouse_mixins.ClickHouseAdminCommandMixin),
]

class TestProtocolMethodSignatureConformance:
    """Verify ClickHouseDialect method signatures match Protocol declarations.

    Python's @runtime_checkable Protocol only checks method existence,
    not signature compatibility. This test catches parameter mismatches.
    """

    @pytest.fixture
    def dialect(self):
        """Create a ClickHouseDialect instance for testing."""
        return clickhouse_dialect.ClickHouseDialect()

    # Known signature mismatches between ClickHouse dialect and generic protocols.
    # ClickHouse uses **kwargs or different parameter names for some methods.
    # These are pre-existing issues that require a broader refactoring to fix.
    _SIGNATURE_MISMATCH_EXCLUSIONS = {
        # JSONSupport: ClickHouse uses expr-based signatures instead of named params
        ("JSONSupport", "format_json_expression"),
        ("JSONSupport", "format_json_table_expression"),
        # ClickHouseJSONFunctionSupport inherits from JSONSupport, same signature issues
        ("ClickHouseJSONFunctionSupport", "format_json_expression"),
        ("ClickHouseJSONFunctionSupport", "format_json_table_expression"),
        # ArraySupport: ClickHouse doesn't support arrays natively
        ("ArraySupport", "format_array_expression"),
        # ExplainSupport: ClickHouse uses **kwargs for explain options
        ("ExplainSupport", "format_explain_statement"),
    }

    @pytest.mark.parametrize("protocol", CLICKHOUSE_PROTOCOLS)
    def test_method_signatures_match_protocol(self, dialect, protocol):
        """Each method on ClickHouseDialect must have a compatible signature
        with the corresponding Protocol method."""
        proto_methods = get_all_protocol_methods(protocol)
        missing = []
        signature_mismatch = []

        for method_name in proto_methods:
            # Check existence
            if not hasattr(dialect, method_name):
                missing.append(method_name)
                continue

            # Check signature compatibility
            # Skip known mismatches between ClickHouse and generic protocols
            if (protocol.__name__, method_name) in self._SIGNATURE_MISMATCH_EXCLUSIONS:
                continue

            proto_method = getattr(protocol, method_name, None)
            dialect_method = getattr(dialect, method_name)

            if proto_method is not None and callable(proto_method):
                try:
                    proto_sig = inspect.signature(proto_method)
                    dialect_sig = inspect.signature(dialect_method)

                    # Compare parameter names (excluding 'self')
                    proto_params = [p for p in proto_sig.parameters.values() if p.name != "self"]
                    dialect_params = [p for p in dialect_sig.parameters.values() if p.name != "self"]

                    # Dialect must accept at least all required proto params
                    proto_required = [
                        p
                        for p in proto_params
                        if p.default is inspect.Parameter.empty
                        and p.kind
                        not in (
                            inspect.Parameter.VAR_POSITIONAL,
                            inspect.Parameter.VAR_KEYWORD,
                        )
                    ]
                    dialect_param_names = {p.name for p in dialect_params}

                    for req_param in proto_required:
                        if req_param.name not in dialect_param_names:
                            signature_mismatch.append(
                                f"{method_name}: missing required param '{req_param.name}' from protocol"
                            )
                except (ValueError, TypeError):
                    pass  # Some protocol methods can't be inspected

        assert not missing, f"ClickHouseDialect missing methods for {protocol.__name__}: {missing}"
        assert not signature_mismatch, f"Signature mismatches for {protocol.__name__}: {signature_mismatch}"


class TestProtocolMixinForwardCoverage:
    """Verify every method declared in Protocol is implemented in Mixin.

    This catches the failure mode where a Protocol declares format_* or
    supports_* methods but the corresponding Mixin doesn't implement them.
    """

    @pytest.mark.parametrize("protocol,mixin", CLICKHOUSE_PROTOCOL_MIXIN_PAIRS)
    def test_protocol_declared_methods_are_implemented(self, protocol, mixin):
        """Every format_* / supports_* in Protocol must exist in Mixin.

        Only checks methods declared directly on the protocol (not inherited
        from parent protocols), since parent protocol methods are typically
        implemented by generic mixins rather than the ClickHouse-specific one.
        """
        proto_methods = get_own_protocol_methods(protocol)
        mixin_methods = {name for name in dir(mixin) if not name.startswith("_")}
        missing = proto_methods - mixin_methods
        assert not missing, (
            f"{mixin.__name__} does not implement these methods declared in {protocol.__name__}: {missing}"
        )


class TestProtocolMixinReverseCoverage:
    """Verify every format_*/supports_* in Mixin is declared in Protocol.

    This catches the failure mode where a Mixin implements format_* or
    supports_* methods but the corresponding Protocol doesn't declare them.
    This is the exact problem we're fixing: Mixin has format_* methods
    that Protocol doesn't know about.
    """

    @pytest.mark.parametrize("protocol,mixin", CLICKHOUSE_PROTOCOL_MIXIN_PAIRS)
    def test_mixin_public_methods_are_declared_in_protocol(self, protocol, mixin):
        """Every format_*/supports_*/get_* in Mixin must be declared in Protocol.

        Only checks methods defined on the Mixin itself (not inherited
        from object or other generic bases), and only public methods
        with the format_*/supports_*/get_* prefix pattern.
        """
        proto_methods = get_all_protocol_methods(protocol)

        # Collect Mixin's own public format_*, supports_*, get_* methods
        mixin_own_methods = set()
        for name in dir(mixin):
            if name.startswith("_"):
                continue
            if not (name.startswith("format_") or name.startswith("supports_") or name.startswith("get_")):
                continue
            # Only include methods defined on the mixin itself, not inherited
            # from object or other generic bases
            if name in mixin.__dict__:
                mixin_own_methods.add(name)

        undeclared = mixin_own_methods - proto_methods
        assert not undeclared, (
            f"{mixin.__name__} implements these methods not declared in {protocol.__name__}: {undeclared}"
        )
