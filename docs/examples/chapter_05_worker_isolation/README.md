# Worker Isolation Experiment

本实验旨在验证 Worker 进程隔离相对于全局共享连接的有效性。

## 实验目的

1. **对比两种连接管理模式**：
   - 全局共享连接（错误模式）
   - Worker 进程内管理连接（正确模式）

2. **验证内容包括**：
   - 连接稳定性
   - 错误率
   - 性能表现
   - 长时间运行的耐久性

## 依赖模块

本实验使用 `rhosocial.activerecord.worker_pool` 核心模块进行进程隔离的任务执行：

```python
from rhosocial.activerecord.worker_pool import (
    WorkerPool,
    TaskDefinition,
    TaskResult,
    TaskMode,
    TaskPriority,
    register_handler,
)
```

> **注意**：`worker_pool` 模块已集成到 `rhosocial.activerecord` 核心包中，推荐在所有并行场景下使用。

## 文件结构

```
chapter_05_worker_isolation/
├── models.py                    # ActiveRecord 模型定义
├── config.py                    # 配置加载和数据库设置
├── exp1_shared_connection.py    # 实验1：共享连接（反模式）
├── exp2_isolated_connection.py  # 实验2：隔离连接（正确模式）
├── exp3_endurance_test.py       # 实验3：耐久性测试
└── README.md                    # 本文件
```

## 运行实验

### 实验1：共享连接（反模式）

```bash
cd python-activerecord-clickhouse/docs/examples/chapter_05_worker_isolation
python exp1_shared_connection.py
```
worker_isolation_experiment/
├── models.py                    # ActiveRecord 模型定义
├── config.py                    # 配置加载和数据库设置
├── exp1_shared_connection.py    # 实验1：共享连接（反模式）
├── exp2_isolated_connection.py  # 实验2：隔离连接（正确模式）
├── exp3_endurance_test.py       # 实验3：耐久性测试
└── README.md                    # 本文件
```

## 前置条件

1. **安装依赖**：
   ```bash
   pip install rhosocial-activerecord rhosocial-activerecord-clickhouse pyyaml
   ```

2. **配置数据库连接**：
   ```bash
   # 设置场景配置文件路径
   export CLICKHOUSE_SCENARIOS_CONFIG_PATH=/path/to/clickhouse_scenarios.yaml

   # 选择要使用的场景
   export CLICKHOUSE_SCENARIO=clickhouse_80
   ```

3. **确保 ClickHouse 数据库可访问**

## 运行实验

### 实验1：共享连接（反模式）

```bash
cd python-activerecord-clickhouse/docs/examples/worker_isolation_experiment
python exp1_shared_connection.py
```

**预期结果**：
- 可能出现连接错误
- 操作失败
- 数据不一致

### 实验2：隔离连接（正确模式）

```bash
python exp2_isolated_connection.py
```

**预期结果**：
- 所有操作成功完成
- 无连接相关错误
- 稳定的性能表现

### 实验3：耐久性测试

```bash
# 仅测试隔离模式
python exp3_endurance_test.py --pattern isolated --rounds 20

# 仅测试共享模式
python exp3_endurance_test.py --pattern shared --rounds 20

# 同时测试两种模式进行对比
python exp3_endurance_test.py --pattern both --rounds 20 --workers 8 --ops-per-round 200
```

**参数说明**：
- `--pattern`: 测试模式 (isolated/shared/both)
- `--workers`: Worker 进程数
- `--ops-per-round`: 每个 Worker 每轮的操作数
- `--rounds`: 测试轮数

## 结果解读

### 关键指标

| 指标 | 共享连接（反模式） | 隔离连接（正确模式） |
|------|-------------------|---------------------|
| **总错误数** | 高 | 低/零 |
| **连接问题数** | 高 | 零 |
| **成功率** | 不稳定 | 接近100% |
| **性能趋势** | 可能下降 | 稳定 |

### 常见错误类型

共享连接模式可能出现：

1. **Connection errors**：连接被关闭或重置
2. **Cursor errors**：游标状态混乱
3. **Timeout errors**：操作超时
4. **Lock/Deadlock errors**：锁竞争问题

## 实验原理

### 共享连接的问题

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Process                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            User.__backend__ (共享)                   │    │
│  │                    ↓                                 │    │
│  │           ClickHouse Connection                           │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
          ↓ fork()          ↓ fork()          ↓ fork()
    ┌───────────┐     ┌───────────┐     ┌───────────┐
    │ Worker 1  │     │ Worker 2  │     │ Worker 3  │
    │ 引用同一   │     │ 引用同一   │     │ 引用同一   │
    │ 连接对象   │     │ 连接对象   │     │ 连接对象   │
    └───────────┘     └───────────┘     └───────────┘
          ↓                 ↓                 ↓
    竞争同一连接 → 游标混乱、数据损坏、连接失效
```

### 隔离连接的正确性

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Process                             │
│                    (无共享连接)                              │
└─────────────────────────────────────────────────────────────┘
          ↓ fork()          ↓ fork()          ↓ fork()
    ┌───────────┐     ┌───────────┐     ┌───────────┐
    │ Worker 1  │     │ Worker 2  │     │ Worker 3  │
    │ Connect() │     │ Connect() │     │ Connect() │
    │     ↓     │     │     ↓     │     │     ↓     │
    │ ClickHouse 1   │     │ ClickHouse 2   │     │ ClickHouse 3   │
    │ (独立)    │     │ (独立)    │     │ (独立)    │
    └───────────┘     └───────────┘     └───────────┘
          ↓                 ↓                 ↓
    各自独立操作 → 无竞争、无冲突、稳定可靠
```

## 核心原则

1. **进程隔离**：Worker 必须是独立进程
2. **连接独立**：每个进程创建自己的连接
3. **生命周期管理**：进入时绑定，退出时释放
4. **事务边界**：每个任务一个事务

## 参考

- [Worker Pool 独立模块使用指南](../../../docs/zh_CN/scenarios/worker_pool.md)
- [并行 Worker 场景](../../../docs/zh_CN/scenarios/parallel_workers.md)
