# 场景实战

本章节提供 ClickHouse 后端在真实业务场景中的完整应用示例，帮助开发者理解如何在实际项目中正确使用 rhosocial-activerecord。

## 场景列表

### [并行 Worker 处理](parallel_workers.md)

演示 ClickHouse 后端在多进程/异步并发场景下的正确用法：

- **多进程正确用法**：`configure()` 必须在子进程内调用
- **ClickHouse 异步优势**：原生网络 I/O 异步，与 SQLite 的线程池模拟完全不同
- **死锁处理**：InnoDB 自动检测死锁，生产环境推荐的重试机制
- **多线程陷阱**：ClickHouse 无 `check_same_thread` 保护，需特别注意

> 📖 **配套代码**：完整可运行的实验代码位于 `docs/examples/chapter_08_scenarios/parallel_workers/` 目录。

## 与核心库场景的关系

本章节是 [核心库场景文档](https://github.com/Rhosocial/python-activerecord/tree/main/docs/zh_CN/scenarios) 的 ClickHouse 特定补充，重点关注：

- ClickHouse 特有的并发行为（行级锁、死锁检测）
- 异步 I/O 的真正优势（网络延迟场景）
- 与 SQLite 的关键差异对比

核心库场景中介绍的通用 ActiveRecord 用法（如关联关系、查询构建）同样适用于 ClickHouse 后端。
