# src/rhosocial/activerecord/backend/impl/clickhouse/adapters.py
import datetime
import json
import uuid
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Tuple, Type, Union, Optional
from datetime import timedelta

from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter


class ClickHouseBlobAdapter(SQLTypeAdapter):
    """
    Adapts Python bytes to ClickHouse String (used for binary data) and vice-versa.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {bytes: [bytes]}

    def to_database(self, value: bytes, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        return value

    def from_database(
        self,
        value: Any,
        target_type: Type,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[bytes]:
        if value is None:
            return None
        # ClickHouse connector usually returns bytes directly for BLOB types
        return value


class ClickHouseArrayAdapter(SQLTypeAdapter):
    """
    Adapts Python list/tuple to a ClickHouse array literal string.

    ClickHouse array literals use single-quoted string elements
    (``['a', 'b']``); the JSON-style double quoting produced by
    ``json.dumps`` is rejected by the server when binding parameters for
    ``Array(T)`` columns. Nested lists are rendered recursively.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {list: [str], tuple: [str]}

    def _render(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, (list, tuple)):
            return "[" + ", ".join(self._render(v) for v in value) + "]"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        if isinstance(value, uuid.UUID):
            return f"'{value}'"
        if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
            return f"'{value.isoformat()}'"
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (int, float)):
            return str(value)
        raise TypeError(f"Unsupported array element type: {type(value).__name__}")

    def to_database(
        self,
        value: Union[list, tuple],
        target_type: Type,
        options: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if value is None:
            return None
        return self._render(value)

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[list]:
        """Convert stored array data back to a Python list.

        The clickhouse-connect driver returns real Python lists for
        ``Array(T)`` columns. Values stored in ``String`` columns come back as
        text — either the array literal we wrote (single-quoted elements) or
        JSON — both of which are parsed here.
        """
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                import json

                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return parsed
                except ValueError:
                    # Fall back to ClickHouse's single-quoted array literal,
                    # which is *not* valid JSON.
                    inner = text[1:-1].strip()
                    if not inner:
                        return []
                    items = []
                    for part in inner.split(","):
                        part = part.strip()
                        if len(part) >= 2 and part[0] == "'" and part[-1] == "'":
                            part = part[1:-1].replace("\\'", "'").replace("\\\\", "\\")
                        items.append(part)
                    return items
        return value


class ClickHouseJSONAdapter(SQLTypeAdapter):
    """
    Adapts Python dict/list to ClickHouse JSON or String type and vice-versa.

    ClickHouse has a native JSON type (accepts dict) and also supports storing
    JSON as String. This adapter serializes to JSON string for write operations
    (compatible with both JSON and String columns) and deserializes from JSON
    string when reading.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {dict: [str], list: [str]}

    def to_database(self, value: Union[dict, list], target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        # ClickHouse JSON/String columns store JSON as a string, so we serialize
        return json.dumps(value, ensure_ascii=False)

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[Union[dict, list]]:
        if value is None or value == "":
            return None
        # ClickHouse connector might return str for JSON, or already dict/list for some drivers
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)


class ClickHouseUUIDAdapter(SQLTypeAdapter):
    """
    Adapts Python UUID to ClickHouse CHAR(36) and vice-versa.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {uuid.UUID: [str]}

    def to_database(self, value: uuid.UUID, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        return str(value)

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class ClickHouseBooleanAdapter(SQLTypeAdapter):
    """
    Adapts Python bool to ClickHouse Bool and vice-versa.

    ClickHouse Bool is natively backed by Python bool. The adapter also accepts
    the integer 0/1 representation (e.g. UInt8 columns) for compatibility.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {bool: [int]}

    def to_database(self, value: bool, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        # bool -> int conversion is optional but keeps compatibility with UInt8 columns
        return 1 if value else 0

    def from_database(
        self,
        value: Any,
        target_type: Type,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[bool]:
        if value is None:
            return None
        # ClickHouse Bool is natively bool; 0/1 ints (e.g. from UInt8) are also accepted
        return bool(value)


class ClickHouseDecimalAdapter(SQLTypeAdapter):
    """
    Adapts Python Decimal to ClickHouse DECIMAL/NUMERIC (or float/str) and vice-versa.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Decimal: [Decimal, float, str]}

    def to_database(self, value: Decimal, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        if target_type is Decimal:
            return value
        if target_type is float:
            return float(value)
        if target_type is str:
            return str(value)
        raise TypeError(f"Cannot convert {type(value).__name__} to {target_type.__name__}")

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        # Converts str, float, int to Decimal
        return Decimal(str(value))


class ClickHouseDateAdapter(SQLTypeAdapter):
    """
    Adapts Python date to ClickHouse DATE string (YYYY-MM-DD) and vice-versa.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {datetime.date: [datetime.date]}

    def to_database(self, value: datetime.date, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        return value.isoformat()  # "YYYY-MM-DD"

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[datetime.date]:
        if value is None:
            return None
        if isinstance(value, datetime.date):
            return value
        return datetime.date.fromisoformat(str(value))


class ClickHouseTimeAdapter(SQLTypeAdapter):
    """
    Adapts Python time to ClickHouse TIME string (HH:MM:SS) and vice-versa.

    ClickHouse connector-python returns timedelta for TIME columns, but accepts
    string format for insertion. This adapter handles both cases.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {datetime.time: [datetime.timedelta, str]}

    def to_database(self, value: datetime.time, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        return value.isoformat(timespec="microseconds")  # "HH:MM:SS.ffffff"

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[datetime.time]:
        if value is None:
            return None
        if isinstance(value, datetime.time):
            return value
        if isinstance(value, timedelta):  # Handle timedelta returned by clickhouse-connector-python
            total_seconds = int(value.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return datetime.time(hours, minutes, seconds, value.microseconds)
        return datetime.time.fromisoformat(str(value))


class ClickHouseDatetimeAdapter(SQLTypeAdapter):
    """
    Adapts Python datetime to ClickHouse DATETIME/TIMESTAMP string and vice-versa.
    Normalizes to UTC.
    """

    def __init__(self, clickhouse_version: Optional[Tuple[int, int, int]] = None):
        """
        Args:
            clickhouse_version: ClickHouse server version tuple (major, minor, patch).
                           If None, defaults to (8, 0, 0).
        """
        self._clickhouse_version = clickhouse_version or (8, 0, 0)

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {datetime.datetime: [datetime.datetime, str]}

    def to_database(self, value: datetime.datetime, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        # Normalise to naive UTC and emit ClickHouse's canonical text form.
        # Space-separated with fractional seconds: 'T'-separated isoformat()
        # is rejected by the strict parser on 25.8/26.3, while the fractional
        # part is accepted by DateTime64 columns (timestamp fixtures all use
        # DateTime64(6)) and preserved losslessly in String columns.
        if value.tzinfo is not None:
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[datetime.datetime]:
        if value is None:
            return None
        # The driver returns a naive datetime; we assume it's UTC and make it aware.
        # Note: This assumes the ClickHouse session timezone is set to UTC (+00:00).
        # If your ClickHouse server uses a different timezone, you should configure
        # time_zone in the connection config or use TIMESTAMP column type.
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.timezone.utc)
            return value  # It's already aware, respect it.
        if isinstance(value, str):
            dt = datetime.datetime.fromisoformat(str(value))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        # Fallback for unexpected types
        return datetime.datetime.fromisoformat(str(value)).replace(tzinfo=datetime.timezone.utc)


class ClickHouseEnumAdapter(SQLTypeAdapter):
    """
    Adapts Python Enum to ClickHouse Enum8/Enum16 type and vice-versa.

    ClickHouse Enum8/Enum16 stores enum values as strings natively (with an
    internal numeric index). This adapter uses the string representation by
    default for better readability and compatibility.

    Can optionally use ClickHouse's internal 1-based integer index for
    performance (see use_int_storage).
    """

    def __init__(self, use_int_storage: bool = False):
        """
        Initialize ClickHouse Enum adapter.

        Args:
            use_int_storage: If True, writes using ClickHouse's internal 1-based
                           integer index for Enum8/Enum16 values. If False, uses
                           the string representation (default, recommended).
        """
        self._use_int_storage = use_int_storage

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Enum: [str, int]}

    def to_database(self, value: Enum, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Convert Python Enum to database value.

        Supports three scenarios:
        1. Python Enum -> ClickHouse String (default): returns string
        2. Python Enum -> ClickHouse Enum8/Enum16 field: returns string (same as default)
        3. Python Enum -> ClickHouse INT: returns integer (requires use_int_storage or int-based enum)

        Args:
            value: Python Enum instance
            target_type: Target database type (str or int)
            options: Optional settings:
                - 'use_int_storage': Override instance setting for this call
                - 'enum_values': List of allowed values for validation
                - 'clickhouse_enum_type': Set to True if target field is ClickHouse Enum8/Enum16
                  (no behavioral change, but used for documentation/validation)

        Returns:
            str or int representation of the enum

        Raises:
            ValueError: If enum value is not in allowed values
            TypeError: If target_type is not str or int
        """
        if value is None:
            return None

        # Validate against allowed values if provided
        enum_values = options.get("enum_values") if options else None
        if enum_values and value.value not in enum_values:
            raise ValueError(f"Invalid enum value '{value.value}'. Allowed values: {enum_values}")

        # Note: clickhouse_enum_type option doesn't change behavior
        # because ClickHouse Enum8/Enum16 accepts and returns strings by default
        # This option is just for documentation/validation purposes

        # Determine which representation to use
        use_int = options.get("use_int_storage", self._use_int_storage) if options else self._use_int_storage

        if target_type is str:
            # Default: use string representation (enum member value)
            # Works for both String and ClickHouse Enum8/Enum16 fields
            return str(value.value)

        if target_type is int:
            if use_int:
                # Use ClickHouse's internal 1-based index for Enum8/Enum16
                # Get the enum class members in definition order
                enum_members = list(type(value))
                return enum_members.index(value) + 1
            else:
                # Use the enum's value if it's already an int
                if isinstance(value.value, int):
                    return value.value
                raise TypeError(
                    "Cannot convert string-based enum to int. "
                    "Set 'use_int_storage=True' to use ClickHouse internal index, "
                    "or ensure enum values are integers."
                )

        raise TypeError(f"Cannot convert {type(value).__name__} to {target_type.__name__}")

    def from_database(
        self,
        value: Any,
        target_type: Type[Enum],
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[Enum]:
        """
        Convert database value to Python Enum.

        Args:
            value: Database value (str or int)
            target_type: Target Python Enum class
            options: Optional settings (currently unused)

        Returns:
            Python Enum instance

        Raises:
            ValueError: If value is invalid for the enum
            TypeError: If value type is not str or int
        """
        if value is None:
            return None

        if isinstance(value, str):
            # Lookup by value (for string enums)
            # First try to match the value directly
            for member in target_type:
                if str(member.value) == value:
                    return member
            # If not found, try name lookup as fallback
            try:
                return target_type[value]
            except KeyError:
                raise ValueError(
                    f"Invalid enum value '{value}'. Valid values: {[m.value for m in target_type]}"
                ) from None

        if isinstance(value, int):
            # Try to interpret as ClickHouse Enum8/Enum16 internal index (1-based)
            enum_members = list(target_type)
            if 1 <= value <= len(enum_members):
                return enum_members[value - 1]

            # If out of range, try direct value lookup
            # (in case enum values themselves are integers)
            try:
                return target_type(value)
            except ValueError:
                raise ValueError(
                    f"Invalid enum index {value}. Valid range: 1-{len(enum_members)} or matching enum values"
                ) from None

        raise TypeError(f"Cannot convert {type(value).__name__} to {target_type.__name__}")


class ClickHouseSetAdapter(SQLTypeAdapter):
    """
    ClickHouse does not have a SET type; this adapter is retained only for
    compatibility and always fails.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {set: [str], frozenset: [str]}

    def to_database(
        self, value: Union[set, frozenset], target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        raise NotImplementedError(
            "ClickHouse does not have a SET type; ClickHouseSetAdapter is retained only for compatibility "
            "and always fails. Use Array/Tuple columns instead."
        )

    def from_database(
        self,
        value: Any,
        target_type: Type,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[Union[set, frozenset]]:
        raise NotImplementedError(
            "ClickHouse does not have a SET type; ClickHouseSetAdapter is retained only for compatibility "
            "and always fails. Use Array/Tuple columns instead."
        )


class ClickHouseVectorAdapter(SQLTypeAdapter):
    """
    Adapts Python list of floats to ClickHouse VECTOR type and vice-versa.

    ClickHouse VECTOR type (9.0+) is used for AI/ML applications to store
    multi-dimensional vectors. Supports up to 16,384 dimensions.

    Storage format:
    - Binary format internally (optimized for similarity operations)
    - Can be read/written as string representation '[1.0,2.0,3.0]'

    Supported distance functions:
    - DISTANCE_EUCLIDEAN: Euclidean (L2) distance
    - DISTANCE_COSINE: Cosine similarity distance
    - DISTANCE_DOT: Dot product distance
    """

    # Maximum dimension supported by ClickHouse 9.0
    MAX_VECTOR_DIMENSION = 16384

    def __init__(self, dimension: Optional[int] = None):
        """
        Initialize VECTOR adapter.

        Args:
            dimension: Optional expected vector dimension for validation.
                      If None, no dimension validation is performed.
        """
        self._dimension = dimension

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        # list[float] -> VECTOR (stored as binary or string)
        return {list: [bytes, str]}

    def to_database(self, value: List[float], target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Convert Python list of floats to ClickHouse VECTOR format.

        Args:
            value: List of float values
            target_type: Target database type (bytes or str)
            options: Optional settings:
                - 'dimension': Override expected dimension for validation

        Returns:
            String representation '[v1,v2,...]' or binary format

        Raises:
            ValueError: If dimension exceeds maximum or doesn't match expected
            TypeError: If value contains non-float elements
        """
        if value is None:
            return None

        dimension = options.get("dimension", self._dimension) if options else self._dimension

        if len(value) > self.MAX_VECTOR_DIMENSION:
            raise ValueError(
                f"Vector dimension {len(value)} exceeds maximum supported dimension {self.MAX_VECTOR_DIMENSION}"
            )

        if dimension is not None and len(value) != dimension:
            raise ValueError(f"Vector dimension {len(value)} doesn't match expected dimension {dimension}")

        # Validate all elements are floats or can be converted
        for i, v in enumerate(value):
            if not isinstance(v, (int, float)):
                raise TypeError(f"Vector element at index {i} is not a number: {type(v).__name__}")

        # ClickHouse accepts string format '[1.0,2.0,3.0]' for VECTOR
        # or use STRING_TO_VECTOR function
        vector_str = "[" + ",".join(str(float(v)) for v in value) + "]"

        if target_type is bytes:
            return vector_str.encode("utf-8")
        return vector_str

    def _decode_vector_from_bytes(self, value: bytes) -> List[float]:
        """
        Decode ClickHouse VECTOR from binary format.

        Args:
            value: Binary data (either UTF-8 encoded string or packed floats)

        Returns:
            List of float values

        Raises:
            ValueError: If binary format is invalid
        """
        # Try UTF-8 decode first (string format stored as bytes)
        try:
            return self._decode_vector_from_string(value.decode("utf-8"))
        except UnicodeDecodeError:
            pass

        # Binary format: packed IEEE 754 float32 values (little-endian)
        import struct

        float_count = len(value) // 4
        if len(value) % 4 != 0:
            raise ValueError(
                f"Invalid VECTOR binary length: {len(value)} bytes (must be multiple of 4 for float32 values)"
            ) from None
        return list(struct.unpack(f"<{float_count}f", value))

    def _decode_vector_from_string(self, value: str) -> List[float]:
        """
        Decode ClickHouse VECTOR from string format.

        Args:
            value: String representation like '[1.0,2.0,3.0]'

        Returns:
            List of float values

        Raises:
            ValueError: If string cannot be parsed
        """
        # Remove brackets and split
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]

        if not value:
            return []

        # Split by comma and convert to floats
        try:
            return [float(v.strip()) for v in value.split(",")]
        except ValueError as e:
            raise ValueError(f"Cannot parse VECTOR value: {value}") from e

    def from_database(
        self,
        value: Any,
        target_type: Type,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[List[float]]:
        """
        Convert ClickHouse VECTOR to Python list of floats.

        Args:
            value: Database value (bytes, str, or already parsed list)
            target_type: Target Python type (list)
            options: Optional settings (currently unused)

        Returns:
            List of float values

        Raises:
            TypeError: If target_type is not list
            ValueError: If value cannot be parsed
        """
        if value is None:
            return None

        if target_type is not list:
            raise TypeError(f"ClickHouse VECTOR adapter only supports list target type, got {target_type.__name__}")

        # Already a list (some drivers might parse it)
        if isinstance(value, list):
            return [float(v) for v in value]

        # Binary format
        if isinstance(value, bytes):
            return self._decode_vector_from_bytes(value)

        # String format
        if isinstance(value, str):
            return self._decode_vector_from_string(value)

        raise TypeError(f"Cannot convert {type(value).__name__} to vector (list of floats)")
