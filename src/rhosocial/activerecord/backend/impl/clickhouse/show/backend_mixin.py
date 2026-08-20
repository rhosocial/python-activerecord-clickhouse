# src/rhosocial/activerecord/backend/impl/clickhouse/show/backend_mixin.py
"""
ClickHouse backend mixins for SHOW functionality.

This module provides mixin classes that add the show() factory method
to ClickHouse backends. The show() method returns a ClickHouseShowFunctionality
instance that provides all ClickHouse SHOW commands.

.. warning::
    This module was copied from the MySQL backend template and contains
    MySQL-style SQL functions/show commands. ClickHouse uses different
    function names (e.g. ``JSONExtract*``) and a different SHOW command
    subset. May generate non-ClickHouse SQL; verify before use.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .functionality import ClickHouseShowFunctionality


class ClickHouseShowMixin:
    """ClickHouse backend mixin for SHOW functionality.

    Provides the show() factory method that returns a ClickHouseShowFunctionality
    instance for executing ClickHouse SHOW commands.
    """

    def show(self) -> "ClickHouseShowFunctionality":
        """Return a ClickHouseShowFunctionality instance."""
        return self._create_show_functionality()

    def _create_show_functionality(self) -> "ClickHouseShowFunctionality":
        """Create ClickHouse SHOW functionality instance.

        Returns:
            ClickHouseShowFunctionality instance with version awareness.
        """
        from .functionality import ClickHouseShowFunctionality

        # Get server version for feature adaptation
        version = getattr(self, "_version", None)
        if version is None and hasattr(self, "get_server_version"):
            try:
                version = self.get_server_version()
            except Exception:
                version = None
        return ClickHouseShowFunctionality(self, version)


class AsyncClickHouseShowMixin:
    """Async ClickHouse backend mixin for SHOW functionality.

    ClickHouse backend is synchronous-only (clickhouse-connect is a sync-only
    driver), so no async SHOW functionality is provided.
    """

    def show(self):
        """Raise NotImplementedError: async SHOW functionality is not supported."""
        raise NotImplementedError(
            "ClickHouse backend is synchronous-only; async SHOW functionality is not supported."
        )

    def _create_show_functionality(self):
        """Raise NotImplementedError: async SHOW functionality is not supported."""
        raise NotImplementedError(
            "ClickHouse backend is synchronous-only; async SHOW functionality is not supported."
        )
