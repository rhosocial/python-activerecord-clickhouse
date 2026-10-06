# src/rhosocial/activerecord/backend/impl/clickhouse/protocols/json.py
"""ClickHouse JSON function protocol.

Split out of the former single-module ``clickhouse/protocols.py``; one
concern per module so the protocol surface stays legible.
"""

from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import JSONSupport


@runtime_checkable
class ClickHouseJSONFunctionSupport(JSONSupport, Protocol):
    """ClickHouse JSON function protocol.

    Feature Source: ClickHouse 5.7+

    ClickHouse JSON functions:
    - JSON_ARRAY, JSON_OBJECT
    - JSON_EXTRACT, JSON_SET, JSON_REMOVE
    - JSON_SEARCH, JSON_CONTAINS, JSON_KEYS

    Official Documentation:
    - JSON Functions: https://dev.clickhouse.com/doc/refman/8.0/en/json-functions.html

    Version Requirements:
    - JSON type: ClickHouse 5.7+
    - JSONTABLE: ClickHouse 8.0.4+
    """

    def supports_json_type(self) -> bool:
        """Whether JSON data type is supported (ClickHouse 5.7+)."""
        ...

    def supports_json_merge_patch(self) -> bool:
        """Whether JSON_MERGE_PATCH is supported (ClickHouse 8.0.3+)."""
        ...

    def supports_json_table(self) -> bool:
        """Whether JSON_TABLE is supported (ClickHouse 8.0.4+)."""
        ...

    def supports_json_function(self, function_name: str) -> bool:
        """Whether a specific JSON function is supported.

        Args:
            function_name: Name of the JSON function (e.g. 'json_extract')

        Returns:
            True if the function is supported
        """
        ...

    def format_json_extract(self, expr) -> Tuple[str, tuple]:
        """Format JSON_EXTRACT function call."""
        ...

    def format_json_unquote(self, expr) -> Tuple[str, tuple]:
        """Format JSON_UNQUOTE function call."""
        ...

    def format_json_object(self, expr) -> Tuple[str, tuple]:
        """Format JSON_OBJECT function call."""
        ...

    def format_json_array(self, expr) -> Tuple[str, tuple]:
        """Format JSON_ARRAY function call."""
        ...

    def format_json_contains(self, expr) -> Tuple[str, tuple]:
        """Format JSON_CONTAINS function call."""
        ...

    def format_json_set(self, expr) -> Tuple[str, tuple]:
        """Format JSON_SET function call."""
        ...

    def format_json_remove(self, expr) -> Tuple[str, tuple]:
        """Format JSON_REMOVE function call."""
        ...

    def format_json_type(self, expr) -> Tuple[str, tuple]:
        """Format JSON_TYPE function call."""
        ...

    def format_json_valid(self, expr) -> Tuple[str, tuple]:
        """Format JSON_VALID function call."""
        ...

    def format_json_search(self, expr) -> Tuple[str, tuple]:
        """Format JSON_SEARCH function call."""
        ...
