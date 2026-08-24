# 能力特性

本节说明 ClickHouse 后端的关键运行时行为与能力边界。

- [客户端雪花 ID](snowflake_ids.md)：ClickHouse 无 AUTO_INCREMENT，id 客户端生成
- [变更（UPDATE/DELETE）](mutations.md)：`mutations_sync=1` 与 `affected_rows` 语义
- [不支持的功能](unsupported.md)：完整 fail-fast 清单与替代方案
