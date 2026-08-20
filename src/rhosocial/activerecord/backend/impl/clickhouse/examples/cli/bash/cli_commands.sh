#!/bin/bash
# cli_commands.sh - Complete MySQL CLI command examples
#
# This script demonstrates all available CLI commands in the MySQL backend.
# Run this script to see examples of each command category.
#
# Usage:
#   ./cli_commands.sh [COMMAND] [OPTIONS]
#
# Commands:
#   info           - Display MySQL environment information
#   query          - Execute SQL queries
#   introspect     - Database introspection
#   status         - Display server status
#   named-expression    - Execute named expressions
#   named-procedure - Execute named procedures
#   named-procedure-graph - Execute procedure graphs
#   named-connection - Manage named connections
#   all            - Run all command examples (default)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONSAFEPATH=1

# Default connection parameters (override via environment)
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DATABASE="${MYSQL_DATABASE:-test}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"

export MYSQL_HOST MYSQL_PORT MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD

PYTHON_CMD="python -m rhosocial.activerecord.backend.impl.mysql"
CONN_ARGS="--host $MYSQL_HOST --port $MYSQL_PORT --database $MYSQL_DATABASE --user $MYSQL_USER --password $MYSQL_PASSWORD"

# Command: info
run_info() {
    echo ""
    echo "=========================================="
    echo "Command: info"
    echo "=========================================="
    echo ""

    echo "--- Basic info ---"
    $PYTHON_CMD info

    echo ""
    echo "--- Verbose info (protocol families) ---"
    $PYTHON_CMD info -v

    echo ""
    echo "--- Detailed verbose (all details) ---"
    $PYTHON_CMD info -vv

    echo ""
    echo "--- JSON output ---"
    $PYTHON_CMD info -o json
}

# Command: query
run_query() {
    echo ""
    echo "=========================================="
    echo "Command: query"
    echo "=========================================="
    echo ""

    echo "--- Simple SELECT ---"
    $PYTHON_CMD query $CONN_ARGS "SELECT 1 as test, 'hello' as greeting" 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- SELECT with WHERE ---"
    $PYTHON_CMD query $CONN_ARGS "SELECT * FROM users WHERE id = 1" 2>/dev/null || echo "(Requires running MySQL server with users table)"

    echo ""
    echo "--- JSON output ---"
    $PYTHON_CMD query $CONN_ARGS "SELECT 1 as test" -o json 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- CSV output ---"
    $PYTHON_CMD query $CONN_ARGS "SELECT 1 as test" -o csv 2>/dev/null || echo "(Requires running MySQL server)"
}

# Command: introspect
run_introspect() {
    echo ""
    echo "=========================================="
    echo "Command: introspect"
    echo "=========================================="
    echo ""

    echo "--- List all tables ---"
    $PYTHON_CMD introspect $CONN_ARGS tables 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- List all views ---"
    $PYTHON_CMD introspect $CONN_ARGS views 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Get table details ---"
    $PYTHON_CMD introspect $CONN_ARGS table users 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Get column details ---"
    $PYTHON_CMD introspect $CONN_ARGS columns users 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Get indexes ---"
    $PYTHON_CMD introspect $CONN_ARGS indexes users 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Get foreign keys ---"
    $PYTHON_CMD introspect $CONN_ARGS foreign-keys users 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Get triggers ---"
    $PYTHON_CMD introspect $CONN_ARGS triggers users 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Get database info ---"
    $PYTHON_CMD introspect $CONN_ARGS database 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- JSON output ---"
    $PYTHON_CMD introspect $CONN_ARGS tables -o json 2>/dev/null || echo "(Requires running MySQL server)"
}

# Command: status
run_status() {
    echo ""
    echo "=========================================="
    echo "Command: status"
    echo "=========================================="
    echo ""

    echo "--- All status ---"
    $PYTHON_CMD status $CONN_ARGS all 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Config status ---"
    $PYTHON_CMD status $CONN_ARGS config 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Performance status ---"
    $PYTHON_CMD status $CONN_ARGS performance 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Storage status ---"
    $PYTHON_CMD status $CONN_ARGS storage 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Databases status ---"
    $PYTHON_CMD status $CONN_ARGS databases 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- Verbose output ---"
    $PYTHON_CMD status $CONN_ARGS all -v 2>/dev/null || echo "(Requires running MySQL server)"

    echo ""
    echo "--- JSON output ---"
    $PYTHON_CMD status $CONN_ARGS all -o json 2>/dev/null || echo "(Requires running MySQL server)"
}

# Command: named-expression
run_named_expression() {
    echo ""
    echo "=========================================="
    echo "Command: named-expression"
    echo "=========================================="
    echo ""

    echo "--- List named expressions (module may not exist) ---"
    $PYTHON_CMD named-expression --list rhosocial.activerecord.backend.impl.mysql.examples.named_expressions.order_expressions 2>/dev/null || echo "(No named expression examples found)"

    echo ""
    echo "--- List with dialect version ---"
    $PYTHON_CMD named-expression --list rhosocial.activerecord.backend.impl.mysql.examples.named_expressions.order_expressions --dialect-version 8.0.0 2>/dev/null || echo "(No named expression examples found)"

    echo ""
    echo "--- Describe expression ---"
    $PYTHON_CMD named-expression --describe rhosocial.activerecord.backend.impl.mysql.examples.named_expressions.order_expressions.get_order 2>/dev/null || echo "(No named expression examples found)"
}

# Command: named-procedure
run_named_procedure() {
    echo ""
    echo "=========================================="
    echo "Command: named-procedure"
    echo "=========================================="
    echo ""

    echo "--- List named procedures (module may not exist) ---"
    $PYTHON_CMD named-procedure --list rhosocial.activerecord.backend.impl.mysql.examples.named_procedures.order_workflow 2>/dev/null || echo "(No named procedure examples found)"

    echo ""
    echo "--- Describe procedure ---"
    $PYTHON_CMD named-procedure --describe rhosocial.activerecord.backend.impl.mysql.examples.named_procedures.order_workflow.OrderProcessingProcedure 2>/dev/null || echo "(No named procedure examples found)"

    echo ""
    echo "--- Dry run procedure ---"
    $PYTHON_CMD named-procedure rhosocial.activerecord.backend.impl.mysql.examples.named_procedures.order_workflow.OrderProcessingProcedure --dry-run 2>/dev/null || echo "(No named procedure examples found)"
}

# Command: named-procedure-graph
run_named_procedure_graph() {
    echo ""
    echo "=========================================="
    echo "Command: named-procedure-graph"
    echo "=========================================="
    echo ""

    echo "--- List procedure graphs (module may not exist) ---"
    $PYTHON_CMD named-procedure-graph --list rhosocial.activerecord.backend.impl.mysql.examples.named_procedure_graph 2>/dev/null || echo "(No named procedure graph examples found)"

    echo ""
    echo "--- Validate graph ---"
    $PYTHON_CMD named-procedure-graph rhosocial.activerecord.backend.impl.mysql.examples.named_procedure_graph.some_graph --validate 2>/dev/null || echo "(No named procedure graph examples found)"

    echo ""
    echo "--- Show wave decomposition ---"
    $PYTHON_CMD named-procedure-graph rhosocial.activerecord.backend.impl.mysql.examples.named_procedure_graph.some_graph --waves 2>/dev/null || echo "(No named procedure graph examples found)"
}

# Command: named-connection
run_named_connection() {
    echo ""
    echo "=========================================="
    echo "Command: named-connection"
    echo "=========================================="
    echo ""

    MODULE="rhosocial.activerecord.backend.impl.mysql.examples.named_connections"

    echo "--- List connections in module ---"
    $PYTHON_CMD named-connection --list "$MODULE"

    echo ""
    echo "--- Show connection ---"
    $PYTHON_CMD named-connection --show "$MODULE.local_dev" || true

    echo ""
    echo "--- Describe connection ---"
    $PYTHON_CMD named-connection --describe "$MODULE.production" || true
}

# Main
COMMAND="${1:-all}"

case "$COMMAND" in
    info)
        run_info
        ;;
    query)
        run_query
        ;;
    introspect)
        run_introspect
        ;;
    status)
        run_status
        ;;
    named-expression)
        run_named_expression
        ;;
    named-procedure)
        run_named_procedure
        ;;
    named-procedure-graph)
        run_named_procedure_graph
        ;;
    named-connection)
        run_named_connection
        ;;
    all)
        run_info
        run_query
        run_introspect
        run_status
        run_named_expression
        run_named_procedure
        run_named_procedure_graph
        run_named_connection
        echo ""
        echo "=========================================="
        echo "All examples completed!"
        echo "=========================================="
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Available commands: info, query, introspect, status, named-expression, named-procedure, named-procedure-graph, named-connection, all"
        exit 1
        ;;
esac

echo ""
echo "Done."
