# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_id_generator.py
import multiprocessing
import os

import pytest

from rhosocial.activerecord.backend.impl.clickhouse import id_generator as id_generator_module
from rhosocial.activerecord.backend.impl.clickhouse.id_generator import (
    SnowflakeIDGenerator,
    _boot_marker,
    _claim_machine_id,
    _process_is_gone,
    _slot_lock_dir,
    _slot_owner,
    generate_id_sequence,
)


def _generate_ids_in_process(count: int) -> list[int]:
    generator = SnowflakeIDGenerator()
    return [generator.next_id() for _ in range(count)]


def test_default_generator_ids_are_unique_across_processes():
    context = multiprocessing.get_context("spawn")
    with context.Pool(processes=4) as pool:
        batches = pool.map(_generate_ids_in_process, [5] * 4)

    ids = [identifier for batch in batches for identifier in batch]
    assert len(set(ids)) == len(ids)


@pytest.fixture
def slot_dir(tmp_path, monkeypatch):
    """Point the slot bookkeeping at an isolated directory.

    The claim files live under the system temp directory, which the real
    generator already shares. Redirecting them keeps these tests from
    competing with it, and with each other, for slots.
    """
    directory = tmp_path / "slots"
    directory.mkdir()
    monkeypatch.setattr(id_generator_module, "_slot_lock_dir", lambda: str(directory))
    return directory


def _write_slot(directory, slot: int, pid: int) -> str:
    path = directory / f"slot-{slot}"
    path.write_text(str(pid))
    return str(path)


# ── _boot_marker ─────────────────────────────────────────────────────────────


def test_boot_marker_reads_the_kernel_boot_id(tmp_path, monkeypatch):
    boot_id = tmp_path / "boot_id"
    boot_id.write_text("boot-1234\n")
    monkeypatch.setattr(id_generator_module, "_BOOT_ID_PATH", str(boot_id))

    assert _boot_marker() == "boot-1234"


def test_boot_marker_falls_back_to_process_one_ctime(monkeypatch):
    monkeypatch.setattr(id_generator_module, "_BOOT_ID_PATH", "/nonexistent/boot_id")

    assert _boot_marker().isdigit()


def test_boot_marker_falls_back_to_a_placeholder(monkeypatch):
    def unreadable(*args, **kwargs):
        raise OSError("no boot id")

    monkeypatch.setattr(id_generator_module, "_BOOT_ID_PATH", "/nonexistent/boot_id")
    monkeypatch.setattr(id_generator_module.os, "stat", unreadable)

    assert _boot_marker() == "unknown-boot"


# ── _slot_lock_dir ───────────────────────────────────────────────────────────


def test_slot_lock_dir_is_namespaced_by_boot_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(id_generator_module.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(id_generator_module, "_boot_marker", lambda: "boot-xyz")

    directory = _slot_lock_dir()
    again = _slot_lock_dir()

    assert os.path.basename(directory) == "rhosocial-clickhouse-snowflake-boot-xyz"
    assert os.path.isdir(directory)
    assert again == directory


# ── _slot_owner ──────────────────────────────────────────────────────────────


def test_slot_owner_returns_the_recorded_pid(slot_dir):
    path = _write_slot(slot_dir, 5, 4321)

    assert _slot_owner(path) == 4321


def test_slot_owner_returns_none_for_a_missing_file(slot_dir):
    assert _slot_owner(str(slot_dir / "slot-absent")) is None


def test_slot_owner_returns_none_for_an_unparsable_file(slot_dir):
    path = slot_dir / "slot-6"
    path.write_text("not-a-pid")

    assert _slot_owner(str(path)) is None


# ── _process_is_gone ─────────────────────────────────────────────────────────


def test_process_is_gone_rejects_non_positive_pids():
    assert _process_is_gone(0) is True
    assert _process_is_gone(-1) is True


def test_process_is_gone_reports_a_live_process():
    assert _process_is_gone(os.getpid()) is False


def test_process_is_gone_detects_an_absent_process(monkeypatch):
    def missing(pid, signal):
        raise ProcessLookupError

    monkeypatch.setattr(id_generator_module.os, "kill", missing)

    assert _process_is_gone(4321) is True


def test_process_is_gone_treats_permission_denied_as_alive(monkeypatch):
    def denied(pid, signal):
        raise PermissionError

    monkeypatch.setattr(id_generator_module.os, "kill", denied)

    assert _process_is_gone(4321) is False


def test_process_is_gone_treats_other_errors_as_gone(monkeypatch):
    def broken(pid, signal):
        raise OSError

    monkeypatch.setattr(id_generator_module.os, "kill", broken)

    assert _process_is_gone(4321) is True


# ── _claim_machine_id ────────────────────────────────────────────────────────


def test_claim_takes_the_preferred_slot(slot_dir):
    assert _claim_machine_id(8, 3) == 3
    assert _slot_owner(str(slot_dir / "slot-3")) == os.getpid()


def test_claim_skips_slots_held_by_live_processes(slot_dir):
    _write_slot(slot_dir, 0, os.getpid())

    assert _claim_machine_id(8, 0) == 1


def test_claim_skips_slots_whose_owner_is_unreadable(slot_dir):
    (slot_dir / "slot-0").write_text("garbage")

    assert _claim_machine_id(8, 0) == 1


def test_claim_reclaims_a_slot_whose_owner_is_gone(slot_dir, monkeypatch):
    _write_slot(slot_dir, 0, 4321)
    monkeypatch.setattr(id_generator_module, "_process_is_gone", lambda pid: True)

    assert _claim_machine_id(8, 0) == 0
    assert _slot_owner(str(slot_dir / "slot-0")) == os.getpid()


def test_claim_gives_up_when_the_owner_changes_mid_reclaim(slot_dir, monkeypatch):
    _write_slot(slot_dir, 0, 4321)
    monkeypatch.setattr(id_generator_module, "_process_is_gone", lambda pid: True)

    owners = iter([4321, 9999])
    monkeypatch.setattr(id_generator_module, "_slot_owner", lambda path: next(owners))

    assert _claim_machine_id(8, 0) == 1


def test_claim_gives_up_when_the_stale_slot_cannot_be_removed(slot_dir, monkeypatch):
    _write_slot(slot_dir, 0, 4321)
    monkeypatch.setattr(id_generator_module, "_process_is_gone", lambda pid: True)

    def unremovable(path):
        raise OSError("read-only slot directory")

    monkeypatch.setattr(id_generator_module.os, "unlink", unremovable)

    assert _claim_machine_id(8, 0) == 1


def test_claim_returns_none_when_every_slot_is_held(slot_dir):
    _write_slot(slot_dir, 0, os.getpid())
    _write_slot(slot_dir, 1, os.getpid())

    assert _claim_machine_id(2, 0) is None
    assert _claim_machine_id(2, 1) is None


def test_claim_stops_reclaiming_after_the_attempt_budget(slot_dir, monkeypatch):
    _write_slot(slot_dir, 0, 4321)
    monkeypatch.setattr(id_generator_module, "_process_is_gone", lambda pid: True)

    recreated = []

    def vanishing(path):
        recreated.append(path)
        return None

    monkeypatch.setattr(id_generator_module.os, "unlink", vanishing)

    assert _claim_machine_id(8, 0) == 1
    assert len(recreated) == id_generator_module._RECLAIM_ATTEMPTS


# ── SnowflakeIDGenerator construction ────────────────────────────────────────


def test_generator_claims_a_slot_when_none_is_given(slot_dir):
    generator = SnowflakeIDGenerator()

    assert 0 <= generator._machine_id <= SnowflakeIDGenerator._MACHINE_MAX
    assert (slot_dir / f"slot-{generator._machine_id}").exists()


def test_generator_raises_when_every_slot_is_taken(monkeypatch):
    monkeypatch.setattr(id_generator_module, "_claim_machine_id", lambda capacity, start: None)

    with pytest.raises(RuntimeError, match="snowflake machine ids is held by a live process"):
        SnowflakeIDGenerator()


@pytest.mark.parametrize("machine_id", [-1, SnowflakeIDGenerator._MACHINE_MAX + 1])
def test_generator_rejects_an_out_of_range_machine_id(machine_id):
    with pytest.raises(ValueError, match="machine_id out of range"):
        SnowflakeIDGenerator(machine_id=machine_id)


# ── id generation ────────────────────────────────────────────────────────────


def test_next_id_is_strictly_increasing():
    generator = SnowflakeIDGenerator(machine_id=7)

    ids = [generator.next_id() for _ in range(100)]

    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_next_id_rolls_into_a_new_millisecond_when_the_sequence_exhausts(monkeypatch):
    generator = SnowflakeIDGenerator(machine_id=7)
    monkeypatch.setattr(SnowflakeIDGenerator, "_SEQUENCE_MAX", 1)

    ids = [generator.next_id() for _ in range(4)]

    assert len(set(ids)) == 4


def test_next_sequence_returns_consecutive_ids():
    generator = SnowflakeIDGenerator(machine_id=7)

    ids = generator.next_sequence(5)

    assert len(ids) == 5
    assert ids == sorted(ids)
    assert len(set(ids)) == 5


def test_next_sequence_continues_after_a_previous_batch():
    generator = SnowflakeIDGenerator(machine_id=7)

    first = generator.next_sequence(3)
    second = generator.next_sequence(3)

    assert second[0] > first[-1]
    assert len(set(first + second)) == 6


@pytest.mark.parametrize("count", [0, -1])
def test_generate_id_sequence_rejects_a_non_positive_count(count):
    assert generate_id_sequence(count) == []


def test_generate_id_sequence_returns_distinct_ids():
    ids = generate_id_sequence(10)

    assert len(ids) == 10
    assert len(set(ids)) == 10
