# Client-side Snowflake IDs

ClickHouse has no `AUTO_INCREMENT` or `SERIAL`; primary key values must be provided by the caller. This backend generates `Int64` primary keys client-side using the **snowflake algorithm**, backfilling the model and writing it during `save()`.

## How it works

`SnowflakeIDGenerator` (`id_generator.py`) splits the 64 bits into:

| Bit segment | Width | Meaning |
|------|------|------|
| timestamp | 41 bit | millisecond resolution, relative to a custom epoch |
| machine id | 10 bit | distinguishes different processes/nodes |
| sequence number | 12 bit | auto-increment within the same millisecond |

- **Time-sensitive**: waits until it catches up when the clock rolls back, avoiding duplicate ids;
- **In-process single-thread safe**: the generator instance maintains the sequence number; can generate 4096 ids within the same millisecond;
- **Batch generation**: during `bulk_insert`, `generate_id_sequence(count)` generates a batch of consecutive sequence numbers at once, avoiding per-row overhead.

## Flow in save()

```python
user = User(username="alice", email="...")
# user.id 此时是 None
user.save()
# 后端：
#   1. 检测 options.primary_key 不在 columns 中
#   2. generate_id_sequence(1) 生成雪花 id
#   3. 把 id 列拼到 INSERT 的 columns 前
#   4. 执行 INSERT
#   5. 回填 user.id
```

The `bulk_insert` / `insert` paths in `backend.py` both rely on the core library dev30's `BulkInsertOptions.primary_key` field to propagate the generated id into the insert options.

## Machine id configuration

In multi-node deployments, different processes must be assigned different machine ids to avoid id collisions. For single-node development, the default value is fine.

## Comparison with other backends

| Backend | Primary key generation |
|------|---------|
| SQLite/MySQL/PostgreSQL | server-side `AUTO_INCREMENT`/`SERIAL`, retrieved via `last_insert_rowid()` |
| ClickHouse (this backend) | **client-side snowflake `Int64`**, known before write |

This means:

1. You get `user.id` immediately after `save()`, no need to query the database again;
2. the id is trend-ascending (time in the high bits), which benefits `ORDER BY id` sorting and data locality;
3. the id is `Int64`, not a string UUID (if you need a UUID primary key, configure the model with the `uuid.UUID` type separately).

> 💡 *AI prompt: "How does the snowflake id handle clock rollback? Why does the ClickHouse backend choose client-side generation instead of server-side?"*

## Next steps

- [Mutations (UPDATE/DELETE)](mutations.md)
- [Relationship with the core library](../introduction/relationship.md)
