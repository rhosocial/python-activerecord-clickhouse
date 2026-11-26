# tests/test_support_switches_take_no_arguments.py
"""Guard: every ``supports_*`` in ``src`` is a parameterless bool switch.

A capability flag answers "does this dialect have capability k", so its only
input is the dialect instance and its only answer is one bool. A method that
needs a name or a kind belongs to a closed-vocabulary sibling switch, a
format-time validation, or -- when it answers a catalogue -- a ``suggest_*``
value. None of those may wear the ``supports_*`` name.

The scan is an ``ast`` walk over ``src/**/*.py``; it also asserts the walk
reached the tree, and is exercised against fabricated offending sources in
``tmp_path`` so a scanner that stops finding anything cannot pass silently.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Sequence, Union

_SRC = Path(__file__).resolve().parent.parent / "src"

_ModuleFunction = Union[ast.FunctionDef, ast.AsyncFunctionDef]


def _source_files() -> List[Path]:
    """Every ``src/**/*.py`` file in this repository."""
    return [
        path
        for path in sorted(_SRC.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _required_arguments(func: _ModuleFunction) -> List[str]:
    """Parameters that must be passed, excluding ``self``."""
    args = func.args
    positional = list(args.args)
    required = positional[1 : len(positional) - len(args.defaults)]
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=False):
        if default is None:
            required.append(arg)
    return [a.arg for a in required]


def _annotates_bool(func: _ModuleFunction) -> bool:
    """A switch declares ``-> bool``, bare or quoted."""
    annotation = func.returns
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name) and annotation.id == "bool":
        return True
    return isinstance(annotation, ast.Constant) and annotation.value == "bool"


def _offenders(tree: ast.Module, label: str) -> List[str]:
    """Every ``supports_*`` in the tree that is not a parameterless bool."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("supports_"):
            continue
        missing = _required_arguments(node)
        if missing:
            found.append(f"{label}:{node.lineno} {node.name}({', '.join(missing)})")
        elif not _annotates_bool(node):
            found.append(f"{label}:{node.lineno} {node.name} does not return bool")
    return found


def _offenders_in_text(source: str, label: str = "probe") -> List[str]:
    return _offenders(ast.parse(source), label)


def _scan(paths: Sequence[Path], label_for) -> List[str]:
    found = []
    for path in paths:
        found.extend(
            _offenders(
                ast.parse(path.read_text(encoding="utf-8")),
                label_for(path),
            )
        )
    return found


def test_every_support_switch_is_parameterless_bool() -> None:
    """The rule, over the real source tree."""
    files = _source_files()
    assert files, f"no source files found under {_SRC}"
    offenders = _scan(files, lambda path: path.name)
    assert not offenders, "\n".join(offenders)


def test_the_scan_reaches_the_source_tree() -> None:
    """The file set is not accidentally empty (or nearly so)."""
    files = _source_files()
    assert len(files) > 50, f"only {len(files)} source files were scanned"


def test_the_scan_flags_a_required_positional(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, name) -> bool:\n"
        "        return False\n",
        encoding="utf-8",
    )
    assert _scan([probe], lambda path: path.name)


def test_the_scan_flags_a_required_keyword_only(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, *, kind) -> bool:\n"
        "        return False\n",
        encoding="utf-8",
    )
    assert _scan([probe], lambda path: path.name)


def test_the_scan_flags_a_non_bool_annotation(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "from typing import Dict\n"
        "class P:\n"
        "    def supports_thing(self) -> Dict[str, bool]:\n"
        "        return {}\n",
        encoding="utf-8",
    )
    offenders = _scan([probe], lambda path: path.name)
    assert offenders and "does not return bool" in offenders[0]


def test_the_scan_flags_a_missing_annotation(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self):\n"
        "        return False\n",
        encoding="utf-8",
    )
    offenders = _scan([probe], lambda path: path.name)
    assert offenders and "does not return bool" in offenders[0]


def test_the_scan_accepts_a_defaulted_parameter(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, name=None) -> bool:\n"
        "        return False\n",
        encoding="utf-8",
    )
    assert not _scan([probe], lambda path: path.name)


def test_the_scan_accepts_a_quoted_bool_annotation(tmp_path: Path) -> None:
    probe = tmp_path / "_probe.py"
    probe.write_text(
        'class P:\n    def supports_thing(self) -> "bool":\n        return False\n',
        encoding="utf-8",
    )
    assert not _scan([probe], lambda path: path.name)
