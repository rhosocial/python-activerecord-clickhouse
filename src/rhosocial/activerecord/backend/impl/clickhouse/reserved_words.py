# src/rhosocial/activerecord/backend/impl/clickhouse/reserved_words.py
"""
ClickHouse reserved words list.

Source: ClickHouse documentation
"""

CLICKHOUSE_RESERVED_WORDS = frozenset({
    "add", "aggregate", "all", "alter", "and", "array", "as", "asc",
    "asof", "between", "both", "by", "case", "cast", "check", "collate",
    "column", "constraint", "create", "cross", "cube", "current_date",
    "current_timestamp", "database", "day", "decimal", "default", "delete",
    "desc", "describe", "distinct", "do", "drop", "else", "end", "engine",
    "except", "exists", "external", "false", "fetch", "final", "first",
    "float", "for", "foreign", "from", "full", "function", "global",
    "grant", "group", "having", "hour", "if", "ignore", "ilike", "in",
    "index", "inner", "insert", "int", "integer", "interval", "into",
    "is", "join", "key", "last", "leading", "left", "like", "limit",
    "local", "lock", "materialized", "merge", "min", "minute", "month",
    "natural", "no", "not", "null", "offset", "on", "open", "or", "order",
    "outer", "outfile", "over", "partition", "pop", "primary", "quarter",
    "range", "raw", "readonly", "recluster", "references", "regexp",
    "rename", "right", "rollup", "row", "sample", "select", "set",
    "settings", "show", "table", "tables", "temporary", "then", "timestamp",
    "to", "top", "totals", "trigger", "truncate", "true", "union", "unique",
    "update", "using", "values", "view", "week", "when", "where", "with",
    "year",
})
