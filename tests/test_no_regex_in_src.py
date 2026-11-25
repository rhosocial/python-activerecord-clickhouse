# tests/test_no_regex_in_src.py
"""Guard: the backend's ``src`` tree never uses the regular-expression module.

Reading a ClickHouse type spelling is a character scan, not a pattern match:
``impl/clickhouse/_scan.py`` states each rule (leading word, balanced
parenthesis, top-level comma, digit run, quoted number pair) directly, and
``impl/clickhouse/introspection/type_parser.py`` is its only consumer.  The
rule this module guards is that ``src`` does not import the module at all; a
test may still use a regular expression to assert generated SQL, but
production code may not.

Two independent scans, so an alias or an attribute-only use cannot slip
through:

* ``ast`` finds ``import re`` / ``import re as ...`` and every ``from re
  import ...``, whatever the bound name;
* a token scan finds a ``NAME`` token spelled ``re`` followed by ``.`` in
  code.  String and comment tokens are not code, so documentation that names
  the module does not trip the scan.

The scanners are exercised against fabricated offending sources as well, so a
scanner that stops finding imports or attributes cannot pass silently.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path
from typing import List, Tuple

_SRC = Path(__file__).resolve().parent.parent / "src"

#: Token kinds that carry no code and are skipped before the ``re.`` scan.
_NON_CODE_TOKENS = frozenset(
    {
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.COMMENT,
    }
)


def _iter_sources() -> List[Tuple[Path, str]]:
    """Every ``src/**/*.py`` file in this repository, read as UTF-8."""
    return [(path, path.read_text(encoding="utf-8")) for path in sorted(_SRC.rglob("*.py"))]


def _import_violations(source: str) -> List[Tuple[int, str]]:
    """``(line, module)`` for every import that names the regular-expression module."""
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re" or alias.name.startswith("re."):
                    found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "re" or node.module.startswith("re."):
                found.append((node.lineno, node.module))
    return found


def _attribute_violations(source: str) -> List[Tuple[int, str]]:
    """``(line, "re.")`` for every ``re`` name token immediately followed by ``.``."""
    tokens = [
        token
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in _NON_CODE_TOKENS
    ]
    found = []
    for index, token in enumerate(tokens[:-1]):
        if token.type != tokenize.NAME or token.string != "re":
            continue
        following = tokens[index + 1]
        if following.type == tokenize.OP and following.string == ".":
            found.append((token.start[0], "re."))
    return found


class TestNoRegexInSrc:
    """The production tree holds neither an import nor an attribute use."""

    def test_no_src_module_imports_the_regex_module(self):
        offenders = []
        for path, source in _iter_sources():
            for lineno, detail in _import_violations(source):
                offenders.append(f"{path.relative_to(_SRC).as_posix()}:{lineno}: {detail}")
        assert not offenders, offenders

    def test_no_src_module_uses_a_regex_attribute(self):
        offenders = []
        for path, source in _iter_sources():
            for lineno, detail in _attribute_violations(source):
                offenders.append(f"{path.relative_to(_SRC).as_posix()}:{lineno}: {detail}")
        assert not offenders, offenders

    def test_the_scan_reaches_the_parser_and_its_scan_helper(self):
        """Non-vacuity: the tree the rule is about was actually walked."""
        names = {path.relative_to(_SRC).as_posix() for path, _source in _iter_sources()}
        assert len(names) > 100, len(names)
        assert "rhosocial/activerecord/backend/impl/clickhouse/_scan.py" in names
        assert (
            "rhosocial/activerecord/backend/impl/clickhouse/introspection/type_parser.py" in names
        )


_FABRICATED_IMPORT = "import re\n\npattern = re.compile('a')\n"
_FABRICATED_ALIASED_IMPORT = "import re as regex\n\nvalue = regex.escape('a')\n"
_FABRICATED_FROM_IMPORT = "from re import compile\n\nvalue = compile('a')\n"
_FABRICATED_ATTRIBUTE = "value = re.search('a', 'b')\n"
_FABRICATED_PROSE = '"""Documentation may mention re.compile; it is not code."""\nvalue = 1\n'
_FABRICATED_CLEAN = "import math\n\nvalue = math.pi\n"


class TestScannerDetectsFabricatedViolations:
    """Each scanner flags a fabricated violation, so it cannot pass vacuously."""

    def test_an_import_is_flagged(self):
        assert _import_violations(_FABRICATED_IMPORT) == [(1, "re")]

    def test_an_aliased_import_is_flagged(self):
        assert _import_violations(_FABRICATED_ALIASED_IMPORT) == [(1, "re")]

    def test_a_from_import_is_flagged(self):
        assert _import_violations(_FABRICATED_FROM_IMPORT) == [(1, "re")]

    def test_an_attribute_use_is_flagged(self):
        assert _attribute_violations(_FABRICATED_IMPORT) == [(3, "re.")]
        assert _attribute_violations(_FABRICATED_ATTRIBUTE) == [(1, "re.")]

    def test_prose_in_a_string_or_comment_is_not_code(self):
        assert _import_violations(_FABRICATED_PROSE) == []
        assert _attribute_violations(_FABRICATED_PROSE) == []

    def test_a_clean_module_is_not_flagged(self):
        assert _import_violations(_FABRICATED_CLEAN) == []
        assert _attribute_violations(_FABRICATED_CLEAN) == []
