# tests/rhosocial/activerecord_clickhouse_test/feature/backend/test_id_generator.py
import multiprocessing

from rhosocial.activerecord.backend.impl.clickhouse.id_generator import SnowflakeIDGenerator


def _generate_ids_in_process(count: int) -> list[int]:
    generator = SnowflakeIDGenerator()
    return [generator.next_id() for _ in range(count)]


def test_default_generator_ids_are_unique_across_processes():
    context = multiprocessing.get_context("spawn")
    with context.Pool(processes=4) as pool:
        batches = pool.map(_generate_ids_in_process, [5] * 4)

    ids = [identifier for batch in batches for identifier in batch]
    assert len(set(ids)) == len(ids)
