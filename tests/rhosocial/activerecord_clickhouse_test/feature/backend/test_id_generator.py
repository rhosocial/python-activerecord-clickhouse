# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_id_generator.py
import multiprocessing

import pytest

from rhosocial.activerecord.backend.impl.clickhouse.id_generator import (
    SnowflakeIDGenerator,
    _allocate_machine_id,
)


def _generate_ids_in_process(count: int) -> list[int]:
    generator = SnowflakeIDGenerator()
    return [generator.next_id() for _ in range(count)]


def _machine_id_in_process(_: int) -> int:
    return SnowflakeIDGenerator()._machine_id


def test_default_generator_ids_are_unique_across_processes():
    context = multiprocessing.get_context("spawn")
    with context.Pool(processes=4) as pool:
        batches = pool.map(_generate_ids_in_process, [5] * 4)

    ids = [identifier for batch in batches for identifier in batch]
    assert len(set(ids)) == len(ids)


def test_live_processes_never_share_a_machine_id():
    """The generator must not hand the same machine slot to two live processes.

    Hashing the pid used to allow this, and two processes on one slot emit
    identical IDs for the same millisecond and sequence.
    """
    context = multiprocessing.get_context("spawn")
    with context.Pool(processes=8) as pool:
        machine_ids = pool.map(_machine_id_in_process, range(8))

    assert len(set(machine_ids)) == len(machine_ids)


def test_allocation_skips_slots_held_by_live_processes(monkeypatch):
    """A slot owned by a live process is stepped over rather than reused."""
    import rhosocial.activerecord.backend.impl.clickhouse.id_generator as module

    own = module.os.getpid()
    capacity = SnowflakeIDGenerator._MACHINE_MAX + 1
    own_slot = own % capacity
    next_slot = (own + 1) % capacity
    holder = own_slot + capacity                      # a pid that maps to own_slot
    assert holder not in range(own, own + capacity)

    monkeypatch.setattr(module, "_process_alive", lambda pid: pid == holder)
    monkeypatch.setattr(module.os, "getpid", lambda: own)

    assert module._allocate_machine_id(capacity) == next_slot


def test_explicit_machine_id_is_still_accepted():
    generator = SnowflakeIDGenerator(machine_id=7)
    assert generator._machine_id == 7
    with pytest.raises(ValueError):
        SnowflakeIDGenerator(machine_id=SnowflakeIDGenerator._MACHINE_MAX + 1)
