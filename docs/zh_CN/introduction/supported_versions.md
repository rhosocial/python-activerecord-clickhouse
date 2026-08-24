# 支持版本

## ClickHouse 版本

本后端在 CI 矩阵中验证的 ClickHouse 发布线如下。原则上覆盖当前处于维护期的 LTS 与稳定线：

| ClickHouse 版本 | 支持状态 | 说明 |
|----------------|---------|------|
| 25.8.x (LTS) | ✅ CI 验证 | 维护期 LTS |
| 26.3.x (LTS) | ✅ CI 验证 | 维护期 LTS |
| 26.7.x | ✅ CI 验证 | 当前稳定线 |
| 更早版本 | ⚠️ 未测试 | 可能可用，但不保证；版本探测会按实际版本降级能力 |

> ⚠️ **注意**：文档与代码中**不再出现** `5.6`/`5.7`/`8.0`/`9.0`/`9.6` 这类 MySQL 版本号。它们是历史迁移遗留，已被清理。ClickHouse 的版本号是日历制（`YY.M.patch`），如 `26.7`。

方言与类型适配器会在连接时探测服务器实际版本，并据此调整能力开关（例如某些函数或设置项仅在新版本可用）。

## Python 版本

| Python 版本 | 支持状态 |
|------------|---------|
| 3.10 | ✅ CI 验证 |
| 3.11 | ✅ CI 验证 |
| 3.12 | ✅ CI 验证 |
| 3.13 | ✅ CI 验证 |
| 3.14 | ✅ CI 验证 |

Python 版本范围 `>=3.10,<3.15` 由 `clickhouse-connect` 的 `Requires-Python` 决定。本后端不做额外的 Python 版本限制。

## 核心库版本

| 依赖 | 约束 |
|------|------|
| `rhosocial-activerecord` | `>=1.0.0.dev30,<2.0.0` |
| `clickhouse-connect` | `>=1.7.0` |

`dev30` 是硬依赖（见 [与核心库的关系](relationship.md#依赖版本)）。在 `dev30` 正式发布到 PyPI 前，需从源码安装核心库。

## CI 矩阵

CI 在 `main` 分支的 push / PR 上跑下列矩阵（`.github/workflows/test.yml`）：

```
Python 3.10 × ClickHouse 25.8
Python 3.11 × ClickHouse 25.8
Python 3.12 × ClickHouse 26.3
Python 3.13 × ClickHouse 26.3
Python 3.14 × ClickHouse 26.7   ← 同时收集覆盖率
```

测试套件由 [python-activerecord-testsuite](https://github.com/rhosocial/python-activerecord-testsuite) 的共享 feature 测试（basic/events/interface/mixins/query/relation）与本后端自有的 ClickHouse 专属测试共同组成。不支持的能力会通过 `pytest.skip` 被合理跳过，而非失败。

## 下一步

- [能力边界与快速失败](capability_boundaries.md)
- [安装指南](../installation/installation.md)
