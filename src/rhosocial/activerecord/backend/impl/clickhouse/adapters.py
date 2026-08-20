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
    Adapts Python bytes to ClickHouse BLOB and vice-versa.
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


class ClickHouseJSONAdapter(SQLTypeAdapter):
    """
    Adapts Python dict/list to ClickHouse JSON and vice-versa.
    Serializes to JSON string when writing, deserializes from JSON string when reading.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {dict: [str], list: [str]}

    def to_database(self, value: Union[dict, list], target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
        # ClickHouse JSON type often stores as TEXT, so we serialize to string
        return json.dumps(value, ensure_ascii=False)

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[Union[dict, list]]:
        if value is None:
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
    Adapts Python bool to ClickHouse TINYINT(1) (or similar integer type) and vice-versa.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {bool: [int]}

    def to_database(self, value: bool, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        if value is None:
            return None
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
        # ClickHouse returns int (0 or 1) for TINYINT(1)
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
        # If the datetime object is timezone-aware, normalize to UTC and make it naive
        # for the database driver, which expects naive datetimes.
        if value.tzinfo is not None:
            utc_dt = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            # ClickHouse 5.7.8+ supports ISO 8601 format, older versions need traditional format
            if self._clickhouse_version >= (5, 7, 8):
                return utc_dt.isoformat()
            else:
                return utc_dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        # If it's already naive, assume it's in the desired timezone (conventionally UTC)
        return value

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
    Adapts Python Enum to ClickHouse ENUM type and vice-versa.

    ClickHouse ENUM stores values as integers internally (1, 2, 3...) but displays as strings.
    This adapter supports both string and integer representations.

    By default, uses string representation for better readability and compatibility.
    Can optionally use ClickHouse's internal integer representation for performance.
    """

    def __init__(self, use_int_storage: bool = False):
        """
        Initialize ClickHouse ENUM adapter.

        Args:
            use_int_storage: If True, uses integer representation when writing to database
                           (ClickHouse stores ENUM as 1-based index). If False, uses string
                           representation (default, recommended).
        """
        self._use_int_storage = use_int_storage

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Enum: [str, int]}

    def to_database(self, value: Enum, target_type: Type, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Convert Python Enum to database value.

        Supports three scenarios:
        1. Python Enum -> ClickHouse VARCHAR/TEXT (default): returns string
        2. Python Enum -> ClickHouse ENUM field: returns string (same as default)
        3. Python Enum -> ClickHouse INT: returns integer (requires use_int_storage or int-based enum)

        Args:
            value: Python Enum instance
            target_type: Target database type (str or int)
            options: Optional settings:
                - 'use_int_storage': Override instance setting for this call
                - 'enum_values': List of allowed values for validation
                - 'clickhouse_enum_type': Set to True if target field is ClickHouse ENUM type
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
        # because ClickHouse ENUM type accepts and returns strings by default
        # This option is just for documentation/validation purposes

        # Determine which representation to use
        use_int = options.get("use_int_storage", self._use_int_storage) if options else self._use_int_storage

        if target_type is str:
            # Default: use string representation (enum member value)
            # Works for both VARCHAR and ClickHouse ENUM fields
            return str(value.value)

        if target_type is int:
            if use_int:
                # Use ClickHouse's internal integer index (1-based)
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
            # Try to interpret as ClickHouse ENUM index (1-based)
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
    Adapts Python set/frozenset to ClickHouse SET type and vice-versa.

    ClickHouse SET is a string object that can have zero or more values,
    each chosen from a predefined list. Values are stored as integers
    (bit flags) internally but displayed/queried as comma-separated strings.

    Features:
    - Maximum 64 members (bit flags in BIGINT)
    - Values are automatically sorted on storage
    - Supports FIND_IN_SET and LIKE operations
    """

    def __init__(self, allowed_values: Optional[List[str]] = None):
        """
        Initialize ClickHouse SET adapter.

        Args:
            allowed_values: Optional list of allowed SET values for validation.
                           If None, no validation is performed during conversion.
        """
        self._allowed_values = allowed_values

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {set: [str], frozenset: [str]}

    def to_database(
        self, value: Union[set, frozenset], target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Convert Python set/frozenset to ClickHouse SET string.

        Args:
            value: Python set or frozenset
            target_type: Target database type (str)
            options: Optional settings:
                - 'allowed_values': Override instance allowed values for validation

        Returns:
            Comma-separated string of sorted values

        Raises:
            ValueError: If values exceed 64 members or contain invalid values
            TypeError: If target_type is not str
        """
        if value is None:
            return None

        if target_type is not str:
            raise TypeError(f"ClickHouse SET adapter only supports str target type, got {target_type.__name__}")

        if len(value) > 64:
            raise ValueError(f"ClickHouse SET supports maximum 64 members, got {len(value)}")

        # Get allowed values from options or instance
        allowed_values = options.get("allowed_values", self._allowed_values) if options else self._allowed_values

        if allowed_values is not None:
            invalid_values = [v for v in value if v not in allowed_values]
            if invalid_values:
                raise ValueError(f"Invalid SET values: {invalid_values}. Allowed values: {allowed_values}")

        # ClickHouse automatically sorts SET values on storage
        sorted_values = sorted(str(v) for v in value)
        return ",".join(sorted_values) if sorted_values else ""

    def _decode_set_from_int(
        self, value: int, target_type: Type, allowed_values: Optional[List[str]]
    ) -> Union[set, frozenset]:
        """
        Decode ClickHouse SET from integer bit flags.

        Args:
            value: Integer bit flags
            target_type: Target Python type (set or frozenset)
            allowed_values: List of allowed values for decoding

        Returns:
            Python set or frozenset

        Raises:
            ValueError: If allowed_values is not provided
        """
        if allowed_values is None:
            raise ValueError(
                "Cannot decode SET from integer without allowed_values. "
                "Provide allowed_values in constructor or options."
            )

        result = set()
        for i, val in enumerate(allowed_values):
            if value & (1 << i):
                result.add(val)

        return frozenset(result) if target_type is frozenset else result

    def _decode_set_from_string(self, value: str, target_type: Type) -> Union[set, frozenset]:
        """
        Decode ClickHouse SET from comma-separated string.

        Args:
            value: Comma-separated string
            target_type: Target Python type (set or frozenset)

        Returns:
            Python set or frozenset
        """
        if not value:
            result = set()
        else:
            result = set(value.split(","))
        return frozenset(result) if target_type is frozenset else result

    def from_database(
        self,
        value: Any,
        target_type: Type,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[Union[set, frozenset]]:
        """
        Convert ClickHouse SET string to Python set/frozenset.

        Args:
            value: Database value (str or int)
            target_type: Target Python type (set or frozenset)
            options: Optional settings (currently unused)

        Returns:
            Python set or frozenset

        Raises:
            TypeError: If target_type is not set or frozenset
        """
        if value is None:
            return None

        # Handle integer storage (bit flags)
        if isinstance(value, int):
            allowed_values = self._allowed_values or (options.get("allowed_values") if options else None)
            return self._decode_set_from_int(value, target_type, allowed_values)

        # Handle string storage (comma-separated)
        if isinstance(value, str):
            return self._decode_set_from_string(value, target_type)

        raise TypeError(f"Cannot convert {type(value).__name__} to {target_type.__name__}")


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
