# src/rhosocial/activerecord/backend/impl/clickhouse/mixins/schema.py


class ClickHouseSchemaMixin:
    """ClickHouse schema (database) support."""

    def supports_schema(self) -> bool:
        """Whether a schema qualifier can be rendered and used.

        True, and what it names needs saying plainly: ClickHouse has no schema
        concept in the language. ``CREATE SCHEMA`` and ``SHOW SCHEMAS`` are
        syntax errors, and no ``currentSchema()`` function exists -- the server
        suggests ``currentSchemas``/``current_schemas`` instead.

        A ``schema_name`` is therefore accepted and used as a *database*:
        ``schema_name="app"`` renders as ```app```.```users```. The parameter is
        honoured even though the word "schema" is not. It was previously False,
        which contradicted the renderer: the qualifier was emitted either way
        and the server accepted it.
        """
        return True

    def supports_create_schema(self) -> bool:
        """Whether CREATE SCHEMA is supported.

        ClickHouse uses CREATE DATABASE, not CREATE SCHEMA.
        """
        return False

    def supports_drop_schema(self) -> bool:
        """Whether DROP SCHEMA is supported.

        ClickHouse uses DROP DATABASE, not DROP SCHEMA.
        """
        return False

    def supports_schema_if_not_exists(self) -> bool:
        """Whether CREATE SCHEMA IF NOT EXISTS is supported."""
        return False

    def supports_schema_if_exists(self) -> bool:
        """Whether DROP SCHEMA IF EXISTS is supported."""
        return False
