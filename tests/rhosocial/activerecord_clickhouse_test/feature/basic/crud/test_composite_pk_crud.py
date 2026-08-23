# tests/rhosocial/activerecord_clickhouse_test/feature/basic/crud/test_composite_pk_crud.py
"""
Bridge file for composite PK CRUD tests from the testsuite.
"""
from rhosocial.activerecord.testsuite.feature.basic.crud.test_composite_pk_crud import *  # noqa: F403

import pytest  # noqa: E402


# ClickHouse MergeTree PRIMARY KEY is a sparse sort key and does NOT enforce
# row uniqueness, so duplicate-PK inserts succeed instead of raising
# IntegrityError. These generic tests assume unique enforcement and are skipped.
def _clickhouse_insert_duplicate_pk(self, order_item_class):
    pytest.skip("ClickHouse MergeTree does not enforce primary key uniqueness")


TestCompositePKInsert.test_insert_duplicate_pk = _clickhouse_insert_duplicate_pk
TestCompositePKWithColumnMapping.test_insert_duplicate_pk_raises = _clickhouse_insert_duplicate_pk