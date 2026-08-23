# src/rhosocial/activerecord/backend/impl/clickhouse/id_generator.py
"""ClickHouse integer primary key generation.

ClickHouse does not support ``AUTO_INCREMENT``. To keep the generic
``IntegerPKMixin`` (id=None, auto-generated) semantics working, the backend
generates a 64-bit snowflake-style ID in the client before inserting a new
record. The generated ID is stored in ``QueryResult.last_insert_id`` so the
model layer can assign it back to the instance.

Format (64-bit):
    - 41 bits: milliseconds since a custom epoch
    - 10 bits: machine/worker id
    - 12 bits: per-millisecond sequence
"""

import threading
import time
from typing import Optional


class SnowflakeIDGenerator:
    """Thread-safe 64-bit snowflake-style ID generator."""

    # 41 bits give ~69 years from epoch.
    EPOCH_MS: int = 1_700_000_000_000  # 2023-11-14T22:13:20Z

    _MACHINE_BITS: int = 10
    _SEQUENCE_BITS: int = 12
    _MACHINE_MAX: int = (1 << _MACHINE_BITS) - 1
    _SEQUENCE_MAX: int = (1 << _SEQUENCE_BITS) - 1
    _SEQUENCE_SHIFT: int = 0
    _MACHINE_SHIFT: int = _SEQUENCE_BITS
    _TIMESTAMP_SHIFT: int = _SEQUENCE_BITS + _MACHINE_BITS

    def __init__(self, machine_id: Optional[int] = None) -> None:
        if machine_id is None:
            machine_id = int(hash(threading.current_thread().name)) % (self._MACHINE_MAX + 1)
        if not 0 <= machine_id <= self._MACHINE_MAX:
            raise ValueError(f"machine_id out of range [0, {self._MACHINE_MAX}]")
        self._machine_id: int = machine_id
        self._last_timestamp: int = -1
        self._sequence: int = 0
        self._lock = threading.Lock()

    def next_id(self) -> int:
        with self._lock:
            timestamp = self._current_timestamp()
            if timestamp < self._last_timestamp:
                timestamp = self._last_timestamp
            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & self._SEQUENCE_MAX
                if self._sequence == 0:
                    timestamp = self._wait_next_millis(timestamp)
            else:
                self._sequence = 0
            self._last_timestamp = timestamp
            return (
                (timestamp << self._TIMESTAMP_SHIFT)
                | (self._machine_id << self._MACHINE_SHIFT)
                | self._sequence
            )

    def next_sequence(self, count: int) -> list:
        """Generate ``count`` strictly-increasing consecutive IDs.

        Used by ``bulk_insert`` where the model layer assigns ids as
        ``last_insert_id + j``; consecutive IDs keep that arithmetic valid.
        """
        with self._lock:
            timestamp = self._current_timestamp()
            if timestamp < self._last_timestamp:
                timestamp = self._last_timestamp
            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & self._SEQUENCE_MAX
                if self._sequence == 0:
                    timestamp = self._wait_next_millis(timestamp)
            else:
                self._sequence = 0
            base = (
                (timestamp << self._TIMESTAMP_SHIFT)
                | (self._machine_id << self._MACHINE_SHIFT)
                | self._sequence
            )
            self._last_timestamp = timestamp
            ids = []
            for j in range(count):
                seq = (self._sequence + j) & self._SEQUENCE_MAX
                if seq < self._sequence and j > 0:
                    timestamp = self._wait_next_millis(timestamp)
                    self._last_timestamp = timestamp
                    self._sequence = 0
                    seq = 0
                ids.append(
                    (timestamp << self._TIMESTAMP_SHIFT)
                    | (self._machine_id << self._MACHINE_SHIFT)
                    | seq
                )
                if seq == self._SEQUENCE_MAX:
                    timestamp = self._wait_next_millis(timestamp)
                    self._last_timestamp = timestamp
            self._sequence = (self._sequence + count - 1) & self._SEQUENCE_MAX
            return ids

    def _current_timestamp(self) -> int:
        return int(time.time() * 1000) - self.EPOCH_MS

    def _wait_next_millis(self, last_timestamp: int) -> int:
        timestamp = self._current_timestamp()
        while timestamp <= last_timestamp:
            time.sleep(0.001)
            timestamp = self._current_timestamp()
        return timestamp


_generator = SnowflakeIDGenerator()


def generate_id() -> int:
    """Generate a single snowflake-style 64-bit integer ID."""
    return _generator.next_id()


def generate_id_sequence(count: int) -> list:
    """Generate ``count`` consecutive snowflake-style integer IDs."""
    if count <= 0:
        return []
    return _generator.next_sequence(count)
