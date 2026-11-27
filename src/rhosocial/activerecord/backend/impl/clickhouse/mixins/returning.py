# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/returning.py
"""ClickHouse has no RETURNING clause; the whole family answers False.

The generic ``ReturningMixin`` defaults three of its members to True --
``expressions``, ``alias`` and ``wildcard``. ClickHouse's DML grammar has no
RETURNING clause at all, so those three advertised a clause the engine rejects,
while the three statement-kind probes answered False and the INSERT formatter
appended one anyway. Declaring the family here makes the answer and the reason
live in one place; the formatter refuses by name instead of rendering invalid
SQL.
"""


class ClickHouseReturningMixin:
    """Every RETURNING probe answers False."""

    def supports_returning_insert(self) -> bool:
        """False: ``INSERT`` has no RETURNING clause."""
        return False

    def supports_returning_update(self) -> bool:
        """False: ``ALTER TABLE ... UPDATE`` has no RETURNING clause."""
        return False

    def supports_returning_delete(self) -> bool:
        """False: ``ALTER TABLE ... DELETE`` has no RETURNING clause."""
        return False

    def supports_returning_expressions(self) -> bool:
        """False: no RETURNING clause, so no expression list to project."""
        return False

    def supports_returning_alias(self) -> bool:
        """False: no RETURNING clause, so no alias form to render."""
        return False

    def supports_returning_wildcard(self) -> bool:
        """False: no RETURNING clause, so no wildcard form to render."""
        return False

    def supports_returning_single_row(self) -> bool:
        """False: no RETURNING clause, so no single-row form."""
        return False

    def supports_returning_old_new(self) -> bool:
        """False: no RETURNING clause, so no OLD/NEW references."""
        return False

    def supports_returning_into(self) -> bool:
        """False: no RETURNING clause, so no INTO target."""
        return False
