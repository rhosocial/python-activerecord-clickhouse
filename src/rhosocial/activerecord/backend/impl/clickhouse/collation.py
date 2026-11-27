# src/rhosocial/activerecord/backend/impl/clickhouse/collation.py
"""Collation names are carried, not validated.

ClickHouse has no collation objects and applies no MySQL-style collation rules:
a column's ordering comes from its type and from the query. A portable
declaration may still carry a collation name, so the formatter passes it through
unchanged instead of refusing it. ``validate_clickhouse_collation_name`` is the
hook ``ClickHouseCollationMixin`` calls; the two helpers below are pass-throughs
of the same kind. None of them validates anything, because there is no catalogue
to validate against.
"""

from typing import Optional


class ClickHouseCollation:
    """The single default token a portable declaration may name.

    ``DEFAULT`` names nothing on this engine: there is no collation catalogue,
    so the value is never compared with a server-side one.
    """

    DEFAULT = "utf8"


class ClickHouseCollationValidator:
    """A pass-through: every name is accepted because there is nothing to check."""

    @staticmethod
    def is_supported(name: str) -> bool:
        return True

    @staticmethod
    def validate(name: str) -> str:
        return name


def validate_clickhouse_collation_name(name: str, version: Optional[tuple] = None) -> str:
    """Return the collation name unchanged.

    Args:
        name: Collation name carried by a portable declaration.
        version: Optional server version tuple; unused, since no version gates
            a check that does not exist.

    Returns:
        The collation name, unchanged.
    """
    return name