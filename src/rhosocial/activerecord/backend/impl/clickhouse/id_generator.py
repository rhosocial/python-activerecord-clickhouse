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

The 10 machine bits have to be unique per process, and hashing the pid into them
is not enough: two processes that start together can hash to the same slot and
then emit identical ids. The slot is therefore claimed with an atomic
O_CREAT|O_EXCL create, so the kernel decides the winner.
"""

import os
import tempfile
import threading
import time
from typing import Optional


_RECLAIM_ATTEMPTS = 3
_BOOT_ID_PATH = "/proc/sys/kernel/random/boot_id"


def _boot_marker() -> str:
    """Identify the current boot, so slot files cannot outlive it.

    Without this, files left by a previous boot would name pids that the current
    boot may already have handed out to unrelated processes, and the liveness
    check would then treat a free slot as busy.
    """
    try:
        with open(_BOOT_ID_PATH) as handle:
            return handle.read().strip()
    except OSError:
        pass
    try:
        return str(int(os.stat("/proc/1").st_ctime))
    except OSError:
        return "unknown-boot"


def _slot_lock_dir() -> str:
    """Return the directory holding the per-slot claim files, creating it."""
    directory = os.path.join(
        tempfile.gettempdir(), f"rhosocial-clickhouse-snowflake-{_boot_marker()}"
    )
    os.makedirs(directory, exist_ok=True)
    return directory


def _slot_owner(path: str) -> Optional[int]:
    """Return the pid that claimed *path*, or None if it is unreadable."""
    try:
        with open(path) as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return None


def _process_is_gone(pid: int) -> bool:
    """Whether *pid* names no live process.

    Signal 0 checks existence without delivering anything. A process owned by
    another user raises PermissionError, which still means it is alive.
    """
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    except OSError:
        return True
    return False


def _claim_machine_id(capacity: int, start: int) -> Optional[int]:
    """Claim a machine slot that no other live process holds.

    The claim is an O_CREAT|O_EXCL create, which the kernel makes atomic, so two
    processes starting together cannot both win the same slot. Deriving the slot
    from the pid and then testing whether that pid is alive cannot give the same
    guarantee: the test and the claim are separate steps, and processes starting
    at the same moment both find the slot free and both take it.

    A slot whose recorded owner is gone is reclaimed, so a crashed process does
    not leak its slot for good.

    Returns:
        The claimed slot, or None if every slot is held by a live process.
    """
    directory = _slot_lock_dir()
    for offset in range(capacity):
        slot = (start + offset) % capacity
        path = os.path.join(directory, f"slot-{slot}")
        for _ in range(_RECLAIM_ATTEMPTS):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                owner = _slot_owner(path)
                if owner is None or not _process_is_gone(owner):
                    break
                if _slot_owner(path) != owner:
                    break
                try:
                    os.unlink(path)
                except OSError:
                    break
                continue
            try:
                os.write(fd, str(os.getpid()).encode("ascii"))
            finally:
                os.close(fd)
            return slot
    return None


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
            capacity = self._MACHINE_MAX + 1
            machine_id = _claim_machine_id(capacity, os.getpid() % capacity)
            if machine_id is None:
                raise RuntimeError(
                    f"every one of the {capacity} snowflake machine ids is held by a "
                    "live process; cannot guarantee unique ids"
                )
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
