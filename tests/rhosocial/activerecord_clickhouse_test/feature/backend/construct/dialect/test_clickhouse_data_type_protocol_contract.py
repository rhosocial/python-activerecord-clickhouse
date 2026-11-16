# tests/.../test_clickhouse_data_type_protocol_contract.py
"""ClickHouse's own 1:1 formatter/probe contract (D10)."""

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.dialect import ClickHouseDialect

VERSIONS = [(26, 7, 3)]


@pytest.mark.parametrize("version", VERSIONS)
def test_formatter_and_probe_families_are_one_to_one(version):
    dialect = ClickHouseDialect(version=version)
    format_names = {
        member[len("format_data_type_") :]
        for member in dir(dialect)
        if member.startswith("format_data_type_")
    }
    probe_names = {
        member[len("supports_data_type_") :]
        for member in dir(dialect)
        if member.startswith("supports_data_type_")
    }
    assert format_names, "the dialect must implement a format_data_type_* family"
    assert format_names == probe_names, (
        f"format-only: {sorted(format_names - probe_names)}, "
        f"probe-only: {sorted(probe_names - format_names)}"
    )

    supported = set(dialect.supports_data_types())
    assert supported <= format_names
    for name in sorted(format_names - supported):
        probe = getattr(dialect, f"supports_data_type_{name}")
        assert probe() is False, f"{name} has a formatter but no False probe explains its absence"
