# tests/rhosocial/activerecord_clickhouse_test/feature/backend/construct/expression/test_special_registry_injection.py
"""Regression guard: special-constructor state cannot depend on import order.

The harness used to build a module-level ``_SPECIAL_REGISTRY`` that the round-trip
matrix populated at *import* time. Which constructors ``make_instance`` saw
therefore depended on which test module pytest collected first. Now each consumer
owns a :class:`SpecialConstructorRegistry` and passes it explicitly, so importing
any module -- in either order -- must leave a fresh registry's keys unchanged.
"""

import importlib.util
import sys
from pathlib import Path

from expression_roundtrip_harness import SpecialConstructorRegistry

EXPRESSION_DIR = Path(__file__).resolve().parent
CONSTRUCT_DIR = EXPRESSION_DIR.parent


def load_test_module(path, name):
    """Execute a test module by file path under a private module name."""
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fresh_registry_keys():
    return set(SpecialConstructorRegistry().entries)


def test_registry_keys_are_independent_of_import_order():
    """Both import orders in one process leave a fresh registry unchanged."""
    roundtrip = EXPRESSION_DIR / "test_expression_roundtrip_all.py"
    consumer = CONSTRUCT_DIR / "types" / "test_type_protocol.py"

    baseline = fresh_registry_keys()

    load_test_module(roundtrip, "rt_order_probe_ab")
    load_test_module(consumer, "consumer_order_probe_ab")
    assert fresh_registry_keys() == baseline, "roundtrip -> consumer import changed the registry"

    load_test_module(consumer, "consumer_order_probe_ba")
    load_test_module(roundtrip, "rt_order_probe_ba")
    assert fresh_registry_keys() == baseline, "consumer -> roundtrip import changed the registry"
