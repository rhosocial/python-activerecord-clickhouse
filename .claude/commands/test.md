Run the full test suite for python-activerecord-clickhouse.

**Prerequisites:**
```bash
cd /mnt/i/GitHubRepositories/rhosocial/python-activerecord-clickhouse
source .venv/bin/activate
export PYTHONPATH=src
```

**Run tests:**
```bash
pytest tests/ -v
```

**Test directories:**
- `tests/rhosocial/activerecord_clickhouse_test/feature/basic/` - Basic CRUD tests
- `tests/rhosocial/activerecord_clickhouse_test/feature/query/` - Query tests
- `tests/rhosocial/activerecord_clickhouse_test/feature/backend/` - Backend-specific tests

Show test results and any failures. Focus on failing tests and suggest fixes.