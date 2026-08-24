# rhosocial-activerecord ClickHouse Backend Documentation

> 🤖 **AI Learning Assistant**: Key concepts in this documentation are marked with 💡 AI prompt markers. When you encounter a concept you don't understand, you can ask the AI assistant directly.
>
> **Example:** "Why does the ClickHouse backend degrade transactions to a no-op? How does it differ from the SQLite/MySQL backends?"
>
> 📖 **See also**: [AI-Assisted Development Guide](https://github.com/rhosocial/python-activerecord/tree/docs/docs/en_US/introduction/ai_assistance.md)

The ClickHouse backend is the ClickHouse database backend implementation for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It uses
the `clickhouse-connect` (HTTP interface) driver to bring the ActiveRecord pattern
into ClickHouse's columnar, OLAP world, while being **honest about ClickHouse's
semantic boundaries** — capabilities ClickHouse does not support (transactions,
foreign keys / unique constraints, triggers, UPSERT, FOR UPDATE, FULLTEXT,
JSON_TABLE, spatial/vector types, stored routines, MySQL admin commands, etc.)
fail fast with `UnsupportedFeatureError` rather than being silently emulated.

## Table of Contents

1. **[Introduction](introduction/README.md)**
    * **[Overview](introduction/README.md)**: Why choose the ClickHouse backend
    * **[Relationship with the core library](introduction/relationship.md)**: How the backend integrates into rhosocial-activerecord
    * **[Supported versions](introduction/supported_versions.md)**: ClickHouse 25.8/26.3/26.7, Python 3.10–3.14
    * **[Capability boundaries & fail-fast](introduction/capability_boundaries.md)**: What is supported, what is not, and why we don't emulate

2. **[Installation](installation/README.md)**
    * **[Installation guide](installation/installation.md)**: pip install and environment requirements
    * **[Connection configuration](installation/configuration.md)**: host/port/database/username/password

3. **[Getting Started](getting_started/README.md)**
    * **[Quick start](getting_started/quick_start.md)**: Minimal runnable example
    * **[First CRUD application](getting_started/first_crud.md)**: Create table, insert, query, update, delete

4. **[Modeling](modeling/README.md)**
    * **[Field type mapping](modeling/field_types.md)**: Python types ↔ ClickHouse column types (Int/UInt/Float/Decimal/String/Date/DateTime64/Bool/UUID/IPv4/6/Enum/Array/Map/Tuple/Nullable/LowCardinality/JSON)
    * **[Nullable & optional fields](modeling/nullable.md)**: Optional model fields map to `Nullable(T)`

5. **[Querying](querying/README.md)**
    * **[JSON queries](querying/json.md)**: The `JSONExtract*` function family
    * **[Arrays, Maps, Tuples](querying/arrays_maps.md)**: Querying columnar composite types

6. **[DDL](ddl/README.md)**
    * **[Table engines & sorting key](ddl/table_engine.md)**: `ENGINE`, `ORDER BY`, `PARTITION BY`, `TTL`
    * **[Skip indexes](ddl/skip_indexes.md)**: `INDEX ... USING` skip indexes

7. **[Capabilities](capabilities/README.md)**
    * **[Client-side snowflake IDs](capabilities/snowflake_ids.md)**: ClickHouse has no AUTO_INCREMENT; IDs are generated client-side
    * **[Mutations (UPDATE/DELETE)](capabilities/mutations.md)**: `enable_block_number_column`/`enable_block_offset_column` settings & `affected_rows` semantics
    * **[Unsupported features](capabilities/unsupported.md)**: Complete fail-fast list with alternatives

8. **[Command Line (CLI)](cli/README.md)**
    * **[CLI usage](cli/README.md)**: `python -m rhosocial.activerecord.backend.impl.clickhouse`

9. **[Testing](testing/README.md)**
    * **[Test configuration](testing/README.md)**: Scenario config & CI matrix

---

> ⚠️ **Dependency note**: This backend depends on the core library
> `rhosocial-activerecord>=1.0.0.dev30` (`primary_key` propagation through bulk
> insert/update options, the `AutoIncrementSupport` protocol). Until the core
> library `1.0.0.dev30` is officially published to PyPI, this backend cannot be
> installed independently via `pip install` — install from source together with
> the core library.
