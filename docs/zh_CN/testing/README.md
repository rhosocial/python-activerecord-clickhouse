# 测试

本节说明如何本地与 CI 运行 ClickHouse 后端测试。

## 测试套件组成

测试由两部分组成：

1. **共享 testsuite**：[python-activerecord-testsuite](https://github.com/rhosocial/python-activerecord-testsuite) 的 feature 测试（basic/events/interface/mixins/query/relation），本后端在 `tests/rhosocial/activerecord_clickhouse_test/feature/` 下以桥接文件接入。
2. **本后端自有测试**：`tests/rhosocial/activerecord_clickhouse_test/feature/backend/`（dialect/mixin/protocol 契约、DDL 覆盖、fail-fast 契约等）。

## 本地运行

需要一个可连的 ClickHouse 实例（见 [安装指南](../installation/installation.md#启动本地-clickhouse可选用于测试)）。

```bash
export PYTHONPATH=src:tests
.venv3.14-ubuntu26.04/bin/python -m pytest tests/rhosocial -p no:logging -p no:cacheprovider
```

> `PYTHONPATH=tests` 必需——它让 pytest 找到 `tests/providers/registry.py`（提供 `TESTSUITE_PROVIDER_REGISTRY` 指向的 provider 实现）。

## 场景配置

测试默认从 `tests/config/clickhouse_scenarios.yaml` 读取连接场景，可用 `CLICKHOUSE_SCENARIOS_CONFIG_PATH` 覆盖：

```bash
export CLICKHOUSE_SCENARIOS_CONFIG_PATH=/path/to/scenarios.yaml
```

场景文件格式：

```yaml
scenarios:
  clickhouse_http:
    host: 127.0.0.1
    port: 8123
    database: test_db
    username: root
    password: password
    autocommit: true
```

## 不支持功能的跳过

ClickHouse 不支持的能力（事务、UPSERT、外键等）在 testsuite 中通过 `pytest.skip` 合理跳过，不会失败。测试输出会显示 `SKIPPED [N] ... ClickHouse does not support ...`。

## CI 矩阵

CI 在 `main` 的 push/PR 上跑（`.github/workflows/test.yml`）：

```
Python 3.10 × ClickHouse 25.8
Python 3.11 × ClickHouse 25.8
Python 3.12 × ClickHouse 26.3
Python 3.13 × ClickHouse 26.3
Python 3.14 × ClickHouse 26.7   ← 同时收集覆盖率
```

CI 会从源码 checkout 核心库与 testsuite 的 `feature/parallel-testing` 分支并以 editable 安装，因此**无需** PyPI 上有 dev30 也能跑测试。

## 代码风格检查

```bash
.venv3.14-ubuntu26.04/bin/ruff check src/
```

CI 当前不 gate `ruff`，但 `src/` 应保持零错误（`tests/` 的 pre-existing lint 不在清理范围）。

## 下一步

- [支持版本](../introduction/supported_versions.md)
- [CLI 用法](../cli/README.md)
