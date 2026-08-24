# 安装指南

## 系统要求

| 组件 | 版本要求 |
|------|---------|
| Python | `>=3.10,<3.15`（由 `clickhouse-connect` 的 `Requires-Python` 决定）|
| ClickHouse 服务端 | 25.8 LTS / 26.3 LTS / 26.7（维护期发布线，更早版本未测试）|
| 核心库 `rhosocial-activerecord` | `>=1.0.0.dev30,<2.0.0`（硬依赖）|
| 驱动 `clickhouse-connect` | `>=1.7.0` |

## 从源码安装（当前 dev 阶段必经）

在核心库 `dev30` 发布到 PyPI 前，需从源码同时安装核心库与本后端。

### 1. 克隆仓库

```bash
git clone https://github.com/rhosocial/python-activerecord.git
git clone https://github.com/rhosocial/python-activerecord-clickhouse.git
```

### 2. 创建虚拟环境

```bash
cd python-activerecord-clickhouse
python3.14 -m venv .venv3.14-ubuntu26.04   # 按你的 Python 版本命名
source .venv3.14-ubuntu26.04/bin/activate
```

### 3. 安装核心库（editable）

```bash
pip install -e ../python-activerecord
```

> 如果你需要跑测试套件，还需安装 testsuite：
> ```bash
> git clone https://github.com/rhosocial/python-activerecord-testsuite.git
> pip install -e ../python-activerecord-testsuite
> ```

### 4. 安装本后端（editable，含开发依赖）

```bash
pip install -e ".[dev]"
# 或仅运行时依赖：
pip install -e .
```

### 5. 验证安装

```bash
python -c "from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend; print('ok')"
```

## 从 PyPI 安装（待 dev30 发布后）

一旦核心库 `1.0.0.dev30` 发布到 PyPI，可直接：

```bash
pip install rhosocial-activerecord-clickhouse
```

这会自动拉取核心库与 `clickhouse-connect`。

## 启动本地 ClickHouse（可选，用于测试）

最简单的方式是官方 Docker 镜像：

```bash
docker run -d --name clickhouse \
  -p 8123:8123 -p 9000:9000 \
  -e CLICKHOUSE_USER=root \
  -e CLICKHOUSE_PASSWORD=password \
  -e CLICKHOUSE_DB=test_db \
  clickhouse/clickhouse-server:26.7
```

> 端口 **8123** 是 ClickHouse 的 HTTP 接口（本后端使用），**9000** 是原生协议（本后端不使用）。

## 下一步

- [连接配置](configuration.md)
- [快速开始](../getting_started/quick_start.md)
