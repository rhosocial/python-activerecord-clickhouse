# JSON 查询

ClickHouse 不使用 MySQL 的箭头运算符（`->`/`->>`）或 SQL 标准的 `JSON_TABLE`。本后端把 JSON 访问渲染为 ClickHouse 原生函数族。

## 基本函数

| 用途 | ClickHouse 函数 | 说明 |
|------|----------------|------|
| 取字符串 | `JSONExtractString(json, path)` | 路径如 `'$.name'` |
| 取原始 JSON | `JSONExtractRaw(json, path)` | 返回子文档 |
| 取类型化值 | `JSONExtract(json, path, type)` | 如 `'UInt32'` |
| SQL 标准等价 | `JSON_VALUE(json, path)` | 标准函数名 |

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

> 💡 *AI 提示词："`JSONExtractString` 和 `JSON_VALUE` 在 ClickHouse 里有什么行为差异？什么时候用哪个？"*

## 不支持：JSON_TABLE

本后端**不支持** SQL 标准的 `JSON_TABLE`，调用 `format_json_table_expression` 会抛 `UnsupportedFeatureError`。替代方案是用 `arrayJoin` + `JSONExtract*` 把 JSON 数组展开为行：

```sql
SELECT JSONExtractString(elem, '$.sku') AS sku
FROM documents
ARRAY JOIN JSONExtractArrayRaw(documents.data, '$.items') AS elem
```

## JSON 类型列 vs String 列存 JSON

ClickHouse 有原生 `JSON` 类型（新版本）。模型上 `dict` 或自定义 JSON 字段可映射到 `JSON` 类型；也可用 `String` 列存 JSON 文本再用 `JSONExtract*` 解析。两者都由 `JSONExtract*` 查询，区别在存储层去重与索引能力。

## 下一步

- [数组、Map、Tuple](arrays_maps.md)
- [字段类型映射](../modeling/field_types.md)
