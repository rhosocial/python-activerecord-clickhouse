# JSON queries

ClickHouse does not use MySQL's arrow operators (`->`/`->>`) or the SQL-standard
`JSON_TABLE`. This backend renders JSON access as ClickHouse native functions.

## Basic functions

| Purpose | ClickHouse function | Notes |
|---------|--------------------|-------|
| get string | `JSONExtractString(json, path)` | path like `'$.name'` |
| get raw JSON | `JSONExtractRaw(json, path)` | returns sub-document |
| get typed value | `JSONExtract(json, path, type)` | e.g. `'UInt32'` |
| SQL-standard equivalent | `JSON_VALUE(json, path)` | standard function name |

```python
from rhosocial.activerecord.backend.expression.parts import FunctionCall, Column, Literal

# SELECT JSONExtractString(data, '$.name') AS name FROM documents
rows = (Document.query()
        .select(FunctionCall(dialect, "JSONExtractString",
                             Column(dialect, "data"),
                             Literal(dialect, "$.name")).as_("name"))
        .from_(TableExpression(dialect, "documents"))
        .all())
```

> 💡 *AI prompt: "What is the behavioral difference between `JSONExtractString` and `JSON_VALUE` in ClickHouse? When do you use which?"*

## Unsupported: JSON_TABLE

This backend **does not support** SQL-standard `JSON_TABLE`; calling
`format_json_table_expression` raises `UnsupportedFeatureError`. The alternative
is to use `arrayJoin` + `JSONExtract*` to expand a JSON array into rows:

```sql
SELECT JSONExtractString(elem, '$.sku') AS sku
FROM documents
ARRAY JOIN JSONExtractArrayRaw(documents.data, '$.items') AS elem
```

## JSON-type column vs String column storing JSON

ClickHouse has a native `JSON` type (recent versions). A `dict` or custom JSON
field on the model can map to the `JSON` type; you can also store JSON text in a
`String` column and parse it with `JSONExtract*`. Both are queried via
`JSONExtract*`; the difference is in storage-layer deduplication and indexing.

## Next steps

- [Arrays, Maps, Tuples](arrays_maps.md)
- [Field type mapping](../modeling/field_types.md)
