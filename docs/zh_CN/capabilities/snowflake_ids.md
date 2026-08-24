# 客户端雪花 ID

ClickHouse 没有 `AUTO_INCREMENT` 或 `SERIAL`，主键值需要由调用方提供。本后端在客户端用**雪花算法**生成 `Int64` 主键，在 `save()` 时回填到模型并写入。

## 工作原理

`SnowflakeIDGenerator`（`id_generator.py`）把 64 位拆为：

| 位段 | 宽度 | 含义 |
|------|------|------|
| 时间戳 | 41 bit | 毫秒级，相对自定义 epoch |
| 机器 id | 10 bit | 区分不同进程/节点 |
| 序列号 | 12 bit | 同毫秒内自增 |

- **时间敏感**：时钟回拨时会等待到追平，避免重复 id；
- **进程内单线程安全**：生成器实例维护序列号，同毫秒内可生成 4096 个 id；
- **批量生成**：`bulk_insert` 时用 `generate_id_sequence(count)` 一次性生成一批连续序列号，避免逐条开销。

## 在 save() 中的流程

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

`backend.py` 的 `bulk_insert` / `insert` 路径均依赖核心库 dev30 的 `BulkInsertOptions.primary_key` 字段把生成的 id 传播进插入选项。

## 机器 id 配置

多节点部署时需为不同进程分配不同机器 id，避免 id 冲突。单节点开发场景用默认值即可。

## 与其他后端对比

| 后端 | 主键生成 |
|------|---------|
| SQLite/MySQL/PostgreSQL | 服务端 `AUTO_INCREMENT`/`SERIAL`，`last_insert_rowid()` 回取 |
| ClickHouse（本后端）| **客户端雪花 `Int64`**，写入前即已知 |

这意味着：

1. 你在 `save()` 后立即拿到 `user.id`，无需再查库；
2. id 是趋势递增的（时间高位），利于 `ORDER BY id` 排序与数据局部性；
3. id 是 `Int64`，不是字符串 UUID（如需 UUID 主键，模型用 `uuid.UUID` 类型另配）。

> 💡 *AI 提示词："雪花 id 的时钟回拨如何处理？为什么 ClickHouse 后端选择客户端生成而非服务端？"*

## 下一步

- [变更（UPDATE/DELETE）](mutations.md)
- [与核心库的关系](../introduction/relationship.md)
