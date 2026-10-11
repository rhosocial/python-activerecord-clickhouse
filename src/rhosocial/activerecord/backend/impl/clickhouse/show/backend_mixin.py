# src/rhosocial/activerecord/backend/impl/clickhouse/show/backend_mixin.py
"""
ClickHouse backend mixins for the ``show()`` factory method.

.. warning::
    **Neither mixin is mixed into a ClickHouse backend.** Neither
    ``ClickHouseBackend`` nor ``AsyncClickHouseBackend`` lists them in its MRO,
    so ``backend.show()`` raises ``AttributeError``; verified by introspection,
    not by reading. The reachable path into this package is
    ``backend.introspector.show`` (``SyncShowIntrospector`` /
    ``AsyncShowIntrospector`` in ``..introspection.show_introspector``), which
    builds the same expressions through the same dialect mixin and carries its
    own parsers.

    They are kept because they are importable, documented API: deleting them
    would be a breaking change for any caller importing them directly, whereas
    mixing them in would change ``backend.show()`` from an ``AttributeError``
    into a working call and so deserves its own decision.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .functionality import ClickHouseShowFunctionality


class ClickHouseShowMixin:
    """ClickHouse backend mixin for SHOW functionality.

    Provides the show() factory method that returns a ClickHouseShowFunctionality
    instance for executing ClickHouse SHOW commands. Not currently composed
    into a backend — see the module warning.
    """

    def show(self) -> "ClickHouseShowFunctionality":
        """Return a ClickHouseShowFunctionality instance."""
        return self._create_show_functionality()

    def _create_show_functionality(self) -> "ClickHouseShowFunctionality":
        """Create ClickHouse SHOW functionality instance.

        Returns:
            ClickHouseShowFunctionality instance. The version it records comes
            from the backend and is not compared against any threshold.
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

    Refuses rather than providing an async implementation, because the
    ``clickhouse-connect`` driver is synchronous. Not currently composed into
    ``AsyncClickHouseBackend`` either; the async backend reaches this package
    through ``AsyncShowIntrospector``.
    """

    def show(self):
        """Raise NotImplementedError: async SHOW functionality is not supported."""
        raise NotImplementedError(
            "ClickHouse show functionality is synchronous; use "
            "await backend.introspector.show.<command>() instead."
        )

    def _create_show_functionality(self):
        """Raise NotImplementedError: async SHOW functionality is not supported."""
        raise NotImplementedError(
            "ClickHouse show functionality is synchronous; use "
            "await backend.introspector.show.<command>() instead."
        )
