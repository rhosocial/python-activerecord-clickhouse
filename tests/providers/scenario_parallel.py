# tests/providers/scenario_parallel.py
"""ClickHouse backend scenario-parallel pytest plugin.

This plugin pins every test of the same scenario to a single xdist worker
(by appending an ``@<scenario>`` suffix to the node id, consumed by
``--dist=loadgroup``), while tests of different scenarios run in parallel.
Without ``--scenario-parallel`` the plugin is a no-op.

Loading contexts:

1. ClickHouse project's own tests (``pytest tests/``): the plugin is loaded
   automatically through ``pytest_plugins`` declared in ``tests/conftest.py``.
2. External ``rhosocial-activerecord-testsuite`` tests: ``tests/conftest.py``
   is not on pytest's collection path, so the plugin must be loaded
   explicitly:

       PYTHONPATH=tests pytest -p providers.scenario_parallel \
           --scenario-parallel -n <scenario-count> --dist=loadgroup \
           ../python-activerecord-testsuite/src/rhosocial/activerecord/testsuite/feature/<category>/
"""

import os

import pytest


def _get_scenario_names():
    """Lazy import to avoid side effects during conftest loading."""
    try:
        from providers.scenarios import SCENARIO_MAP

        return set(SCENARIO_MAP.keys()), list(SCENARIO_MAP.keys())
    except Exception:
        return set(), []


def _extract_scenario_from_item(item, scenario_name_set):
    """Extract scenario name from item's callspec.

    Returns:
        str:  scenario name when exactly one scenario param is found
        None: no scenario params (not a scenario-parametrized test)
        list: multiple distinct scenario names (cross-scenario test)
    """
    callspec = getattr(item, "callspec", None)
    if callspec is None:
        return None
    scenario_values = [v for v in callspec.params.values() if isinstance(v, str) and v in scenario_name_set]
    if len(scenario_values) == 1:
        return scenario_values[0]
    if len(scenario_values) >= 2:
        return scenario_values  # cross-scenario: caller checks isinstance(result, list)
    return None


def _add_xdist_group_marker(item, group_name):
    """Append @group_name suffix to item._nodeid for loadgroup scheduling."""
    suffix = f"@{group_name}"
    if suffix not in item.nodeid:
        item._nodeid = item.nodeid + suffix


def pytest_addoption(parser):
    parser.addoption(
        "--scenario-parallel",
        action="store_true",
        default=False,
        help="Scenario parallel mode: distribute scenarios across workers, keep each scenario on one worker.",
    )
    # NOTE: The generic --scenarios option is intentionally NOT registered here.
    # It is registered by tests/conftest.py (ClickHouse project's own tests) or by
    # the testsuite's root conftest (external testsuite runs). Registering it
    # from this plugin would collide with whichever conftest already added it.


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "xdist_group(name): specify the xdist group for a test (provided by pytest-xdist).",
    )

    # Propagate --scenarios to environment variable so that all conftest.py
    # instances (which load SCENARIO_MAP independently) can filter consistently.
    scenarios_opt = config.getoption("--scenarios", default=None)
    if scenarios_opt:
        os.environ["CLICKHOUSE_ACTIVE_SCENARIOS"] = scenarios_opt


def _is_backend_single_test(item):
    """Check if a test uses clickhouse_backend_single or async_clickhouse_backend_single.

    These fixtures connect to the first scenario's database but are not
    scenario-parametrized. In --scenario-parallel mode they must be pinned
    to the first scenario's worker to avoid table conflicts.
    """
    fixturenames = getattr(item, "fixturenames", None)
    if fixturenames is None:
        return False
    return "clickhouse_backend_single" in fixturenames or "async_clickhouse_backend_single" in fixturenames


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--scenario-parallel", default=False):
        return

    scenario_name_set, scenario_name_list = _get_scenario_names()
    if not scenario_name_set:
        return

    first_scenario = scenario_name_list[0]
    scenario_items = []
    cross_scenario_items = []
    backend_single_items = []
    normal_items = []

    for item in items:
        result = _extract_scenario_from_item(item, scenario_name_set)
        if isinstance(result, list):
            # Cross-scenario test: uses fixtures from multiple scenarios simultaneously.
            # Running concurrently with per-scenario workers causes table conflicts on
            # shared database instances, so skip during parallel mode. Run separately
            # without --scenario-parallel for serial execution.
            item.add_marker(
                pytest.mark.skip(
                    reason="Cross-scenario test skipped in --scenario-parallel mode. "
                    "Run without --scenario-parallel for serial execution."
                )
            )
            cross_scenario_items.append(item)
        elif isinstance(result, str):
            _add_xdist_group_marker(item, result)
            scenario_items.append(item)
        elif _is_backend_single_test(item):
            # Non-parametrized fixture using first scenario's DB.
            # Pin to the first scenario's worker to avoid table conflicts.
            _add_xdist_group_marker(item, first_scenario)
            backend_single_items.append(item)
        else:
            normal_items.append(item)

    def sort_key(item):
        result = _extract_scenario_from_item(item, scenario_name_set)
        if not isinstance(result, str):
            return ("~", 0)
        try:
            scenario_idx = scenario_name_list.index(result)
        except ValueError:
            scenario_idx = 0
        base = item.nodeid.split("[")[0] if "[" in item.nodeid else item.nodeid
        return (base, scenario_idx)

    scenario_items.sort(key=sort_key)
    items[:] = scenario_items + backend_single_items + normal_items + cross_scenario_items

    groups: dict = {}
    for item in scenario_items:
        sn = _extract_scenario_from_item(item, scenario_name_set)
        if isinstance(sn, str):
            base = item.nodeid.split("[")[0] if "[" in item.nodeid else item.nodeid
            groups.setdefault(base, set()).add(sn)

    print(
        f"\n[ScenarioParallel] {len(items)} items: "
        f"{len(scenario_items)} scenario-param + "
        f"{len(backend_single_items)} backend-single @{first_scenario} + "
        f"{len(normal_items)} normal + "
        f"{len(cross_scenario_items)} cross-scenario (skipped)"
    )
    print(f"[ScenarioParallel] {len(groups)} test methods, {len(scenario_name_list)} scenarios in parallel")
    print(f"[ScenarioParallel] Suggested: --dist=loadgroup -n {len(scenario_name_list)}")