#!/usr/bin/env bash
# ===========================================================================
# demo_async.sh — async migration execution (--async) for MySQL
#
# Scenarios:
#   - apply UP with --async
#   - dry-run with --async
#   - rollback DOWN with --async
#
# Requires: aiomysql
#
# Usage:
#   cd python-activerecord-mysql
#   PYTHONPATH=src \
#     bash src/rhosocial/activerecord/backend/impl/mysql/examples/named_migrations/demo_async.sh
# ===========================================================================
set -euo pipefail

if [ -d "./src" ]; then
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"
fi

MODULE="rhosocial.activerecord.backend.impl.mysql.examples.named_migrations"
FQN="${MODULE}.migrations.V001CreateUsers"
STORE="./demo_mysql_async_mig.json"
VENV_PYTHON="${DEMO_VENV_PYTHON:-python3}"
PYTHON="$VENV_PYTHON -m rhosocial.activerecord.backend.impl.mysql"

rm -f "$STORE"
echo "=== Async Migration (--async) for MySQL ==="
echo

echo "[1] Async dry-run (preview SQL, no changes):"
$PYTHON named-migration "$FQN" --host localhost --database test \
    --direction up --dry-run --async
echo

echo "[2] Async apply UP:"
$PYTHON named-migration "$FQN" --host localhost --database test \
    --direction up --async --record-store "$STORE"
echo

echo "[3] Async rollback DOWN:"
$PYTHON named-migration "$FQN" --host localhost --database test \
    --direction down --async --record-store "$STORE"
echo

rm -f "$STORE"
echo "=== Async Migration Demo Complete for MySQL ==="