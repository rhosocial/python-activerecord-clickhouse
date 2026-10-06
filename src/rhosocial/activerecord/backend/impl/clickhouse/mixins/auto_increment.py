# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/auto_increment.py


class ClickHouseAutoIncrementMixin:
    """ClickHouse identity / auto-increment support checks.

    ClickHouse has neither server-side mechanism. Its grammar has no bare
    ``AUTO_INCREMENT`` marker, and the SQL-standard
    ``GENERATED {ALWAYS|BY DEFAULT} AS IDENTITY`` clause is refused with
    ``Code: 62. Syntax error: failed at position 40 (GENERATED)`` -- measured
    against ClickHouse 26.7. Primary keys are generated client-side (snowflake
    Int64) before inserting new records.

    Both probes answer ``False`` and the formatters inherited from core consult
    them: each request is refused with ``UnsupportedFeatureError`` instead of
    rendering SQL the server rejects. That is the point of the split -- the old
    single ``supports_auto_increment()`` answered ``False`` while the formatter
    rendered the standard clause anyway, because nothing read the probe.
    """

    def supports_auto_increment_column(self) -> bool:
        """Whether a bare ``AUTO_INCREMENT`` column marker is accepted.

        ``False``: ClickHouse's grammar has no such marker; its seed is a
        table-level option that does not exist here either.
        """
        return False

    def supports_identity_column(self) -> bool:
        """Whether ``GENERATED ... AS IDENTITY`` is accepted.

        ``False``: ClickHouse 26.7 rejects the clause with ``Code: 62``
        (syntax error at ``GENERATED``), for ``BY DEFAULT`` and ``ALWAYS``
        alike, with or without sequence options.
        """
        return False
