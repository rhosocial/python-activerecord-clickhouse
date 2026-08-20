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
    from .functionality import ClickHouseShowFunctionality, AsyncClickHouseShowFunctionality


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

    Provides the show() factory method that returns an AsyncClickHouseShowFunctionality
    instance for executing ClickHouse SHOW commands asynchronously.
    """

    def show(self) -> "AsyncClickHouseShowFunctionality":
        """Return an AsyncClickHouseShowFunctionality instance."""
        return self._create_show_functionality()

    def _create_show_functionality(self) -> "AsyncClickHouseShowFunctionality":
        """Create async ClickHouse SHOW functionality instance.

        Returns:
            AsyncClickHouseShowFunctionality instance with version awareness.
        """
        from .functionality import AsyncClickHouseShowFunctionality

        # Get server version for feature adaptation
        version = getattr(self, "_version", None)
        if version is None and hasattr(self, "_version"):
            version = self._version
        return AsyncClickHouseShowFunctionality(self, version)
