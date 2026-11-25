# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/mixins/test_shared_formatter_guard.py
"""Guard: one private statement renderer per public ``format_*`` entry point.

A private ``_render_*`` / ``_format_*`` method that is called by two or more
public ``format_*`` methods in the same class is one renderer serving several
node kinds. The defect that prompted this guard is
``_format_partition_id_statement``: ``DROP`` / ``DETACH`` / ``ATTACH`` shared
it and passed a ``verb``, so the node kind was never checked by the formatter
that named it and the per-kind gate lived in the shared body. It has been
inlined into the three formatters, each of which now validates its own node.

A shared renderer is allowed only when it renders a *sub-node* that
legitimately appears inside several statements (``ColumnDefinition`` inside
``CREATE TABLE``), and only with a written reason in
:data:`ALLOWED_SHARED_RENDERERS`. The list is asserted for equality against
what the source contains, in both directions:

* a new shared renderer fails, because it is not on the list;
* a stale entry fails, because the method is no longer shared (or gone).

The scan is also proved non-vacuous against a fabricated source, so a scanner
that stops seeing methods cannot silently pass every check.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.clickhouse import mixins as mixins_package
from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect
from rhosocial.activerecord.backend.impl.clickhouse.expression.partition import (
    ClickHouseAttachPartitionStatement,
    ClickHouseDetachPartitionStatement,
    ClickHouseDropPartitionStatement,
)

#: ``(module file, class, private method)`` identifying one renderer.
Renderer = Tuple[str, str, str]

#: The private renderer prefixes this guard treats as statement renderers.
_PRIVATE_RENDERER_PREFIXES = ("_render_", "_format_")

#: The only shared renderers allowed, each with the reason it may be shared.
ALLOWED_SHARED_RENDERERS: Dict[Renderer, str] = {
    (
        "ddl_table.py",
        "ClickHouseTableMixin",
        "_render_column_definition",
    ): (
        "Renders a sub-node, not a statement: ``ColumnDefinition`` is reused "
        "inside ``CREATE TABLE``, while ``format_column_definition`` is its "
        "one-to-one entry point. The argument's own kind is still validated "
        "in the body, and no statement-kind gate moves into it -- the "
        "``omit_unenforceable`` / ``widen_integers`` flags are CREATE TABLE "
        "adaptation switches, not capability gates."
    ),
}

#: The public formatters the three partition-id statements dispatch to. Their
#: private helper was the defect; this guard pins it stays inlined.
_PARTITION_ID_FORMATTERS = (
    ("DROP", ClickHouseDropPartitionStatement),
    ("DETACH", ClickHouseDetachPartitionStatement),
    ("ATTACH", ClickHouseAttachPartitionStatement),
)


def _method_calls(method: ast.FunctionDef) -> Set[str]:
    """Names called as ``self.<name>(...)`` anywhere in *method*'s body."""
    return {
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    }


def _scan_source(source: str, module: str) -> Tuple[List[Renderer], Set[str]]:
    """Scan one module's source.

    Returns the shared private renderers found and the public ``format_*``
    method names seen, so a test can prove the scan reached the tree it
    claims to inspect.
    """
    offenders: List[Renderer] = []
    seen_public: Set[str] = set()
    tree = ast.parse(source)

    for class_node in ast.walk(tree):
        if not isinstance(class_node, ast.ClassDef):
            continue
        methods = {
            child.name: child
            for child in class_node.body
            if isinstance(child, ast.FunctionDef)
        }
        public_calls = {
            name: _method_calls(method)
            for name, method in methods.items()
            if name.startswith("format_")
        }
        seen_public.update(public_calls)

        for name in methods:
            if not name.startswith(_PRIVATE_RENDERER_PREFIXES):
                continue
            callers = {
                public_name
                for public_name, calls in public_calls.items()
                if name in calls
            }
            if len(callers) >= 2:
                offenders.append((module, class_node.name, name))

    return offenders, seen_public


def _scan_package() -> Tuple[List[Renderer], Set[str]]:
    """Scan every module in ``impl/clickhouse/mixins``."""
    directory = Path(mixins_package.__file__).resolve().parent
    offenders: List[Renderer] = []
    seen_public: Set[str] = set()
    for module_path in sorted(directory.glob("*.py")):
        found, seen = _scan_source(
            module_path.read_text(encoding="utf-8"), module_path.name
        )
        offenders.extend(found)
        seen_public.update(seen)
    return offenders, seen_public


class TestSharedRendererAllowList:
    """The allow-list equals what the production tree actually shares."""

    def test_shared_renderers_match_the_allow_list(self):
        offenders, _seen = _scan_package()
        actual = set(offenders)
        allowed = set(ALLOWED_SHARED_RENDERERS)
        assert actual == allowed, (
            "shared renderers not allow-listed: "
            f"{sorted(actual - allowed)}; "
            f"allow-listed but no longer shared: {sorted(allowed - actual)}"
        )

    def test_every_allow_list_entry_has_a_written_reason(self):
        for renderer, reason in ALLOWED_SHARED_RENDERERS.items():
            assert isinstance(reason, str) and len(reason.strip()) >= 40, (
                f"{renderer}: the allow-list entry needs a written reason"
            )

    def test_the_scan_reaches_the_partition_formatters(self):
        """Non-vacuity: the scanner sees the tree the rule is about."""
        offenders, seen = _scan_package()
        for verb, _cls in _PARTITION_ID_FORMATTERS:
            name = f"format_{verb.lower()}_partition_statement"
            assert name in seen, f"the scan did not see {name}"
        assert (
            "ddl_table.py",
            "ClickHouseTableMixin",
            "_render_column_definition",
        ) in offenders, "the known allowed shared renderer was not detected"

    def test_no_partition_id_shared_renderer_remains(self):
        """``_format_partition_id_statement`` was the defect; it must stay gone."""
        offenders, _seen = _scan_package()
        assert not any(
            renderer[2] == "_format_partition_id_statement"
            for renderer in offenders
        )
        source = (
            Path(mixins_package.__file__).resolve().parent / "partition.py"
        ).read_text(encoding="utf-8")
        assert "def _format_partition_id_statement" not in source


_FABRICATED_SHARED = """
class SharedMixin:
    def _render_thing(self, expr):
        return "x", ()

    def format_a(self, expr):
        return self._render_thing(expr)

    def format_b(self, expr):
        return self._render_thing(expr)
"""


_FABRICATED_SINGLE_CALLER = """
class SingleMixin:
    def _render_thing(self, expr):
        return "x", ()

    def format_a(self, expr):
        return self._render_thing(expr)

    def _helper(self):
        return self._render_thing(None)
"""


class TestScannerDetectsASharedRendererFabricated:
    """The scanner flags a fabricated violation, not only the production tree."""

    def test_a_shared_renderer_is_flagged(self):
        offenders, seen = _scan_source(_FABRICATED_SHARED, "fabricated.py")
        assert offenders == [("fabricated.py", "SharedMixin", "_render_thing")]
        assert {"format_a", "format_b"} <= seen

    def test_a_single_public_caller_is_not_flagged(self):
        offenders, _seen = _scan_source(
            _FABRICATED_SINGLE_CALLER, "fabricated.py"
        )
        assert offenders == []


@pytest.fixture(scope="module")
def dialect():
    return ClickHouseDialect(version=(26, 7, 3))


class TestPartitionFormattersOwnTheirNodes:
    """Each formatter accepts only its own node and keeps its own gate."""

    @pytest.mark.parametrize(
        "verb,node_class",
        _PARTITION_ID_FORMATTERS,
        ids=[verb for verb, _cls in _PARTITION_ID_FORMATTERS],
    )
    def test_own_node_renders_its_own_clause(self, dialect, verb, node_class):
        formatter = getattr(dialect, f"format_{verb.lower()}_partition_statement")
        expr = node_class(dialect, "visits", "202601")
        assert formatter(expr) == (
            f"ALTER TABLE `visits` {verb} PARTITION ID '202601'",
            (),
        )

    @pytest.mark.parametrize(
        "verb,node_class",
        _PARTITION_ID_FORMATTERS,
        ids=[verb for verb, _cls in _PARTITION_ID_FORMATTERS],
    )
    def test_another_kind_is_refused_not_rendered(self, dialect, verb, node_class):
        formatter = getattr(dialect, f"format_{verb.lower()}_partition_statement")
        for other_verb, other_class in _PARTITION_ID_FORMATTERS:
            if other_verb == verb:
                continue
            other = other_class(dialect, "visits", "202601")
            with pytest.raises(
                TypeError,
                match=(
                    f"format_{verb.lower()}_partition_statement expects a "
                    f"{node_class.__name__}"
                ),
            ):
                formatter(other)

    @pytest.mark.parametrize(
        "verb,node_class",
        _PARTITION_ID_FORMATTERS,
        ids=[verb for verb, _cls in _PARTITION_ID_FORMATTERS],
    )
    def test_a_duck_typed_object_is_refused(self, dialect, verb, node_class):
        formatter = getattr(dialect, f"format_{verb.lower()}_partition_statement")

        class _Duck:
            table = "visits"
            schema = None
            partition_id = "202601"

        with pytest.raises(TypeError, match=node_class.__name__):
            formatter(_Duck())

    @pytest.mark.parametrize(
        "verb,node_class",
        _PARTITION_ID_FORMATTERS,
        ids=[verb for verb, _cls in _PARTITION_ID_FORMATTERS],
    )
    @pytest.mark.parametrize("partition_id", ["   ", 202601])
    def test_the_gate_still_names_its_own_verb(
        self, dialect, verb, node_class, partition_id
    ):
        formatter = getattr(dialect, f"format_{verb.lower()}_partition_statement")
        expr = node_class(dialect, "visits", "202601")
        expr.partition_id = partition_id
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            formatter(expr)
        assert excinfo.value.feature_name == f"{verb} PARTITION"
