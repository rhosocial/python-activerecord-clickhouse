# Chapter 12: Named Procedure Examples

本目录包含 ClickHouse 后端的命名过程示例代码。

## 目录结构

```
chapter_12_named_procedure/
├── queries/              # 命名查询模块
│   ├── __init__.py
│   └── order_queries.py  # 订单相关查询
├── order_workflow.py     # 订单处理工作流
├── diagram_demo.py      # 静态图/实例图演示
└── README.md            # 本文件
```

## 示例列表

### 1. OrderProcessingProcedure (order_workflow.py)

完整订单处理工作流，展示：
- 条件分支(库存检查)
- 并行执行(库存预留 + 通知发送)
- 条件回滚(支付失败时释放库存)
- 静态图/实例图生成

### 2. OrderWorkflowProcedure (diagram_demo.py)

简化订单流程，用于图表演示。

### 3. ShippingWorkflowProcedure (diagram_demo.py)

物流处理工作流，展示条件分支。

## 使用方法

### 生成静态图

```python
from order_workflow import OrderProcessingProcedure

# 生成流程图
print(OrderProcessingProcedure.static_diagram("flowchart"))

# 生成序列图
print(OrderProcessingProcedure.static_diagram("sequence"))
```

### 执行并生成实例图

```python
from order_workflow import OrderProcessingProcedure
from rhosocial.activerecord.backend.impl.clickhouse import ClickHouseBackend

backend = ClickHouseBackend(config)
dialect = backend.get_dialect()

runner = ProcedureRunner(OrderProcessingProcedure, backend)
result = runner.run(backend, order_id=1, user_id=1, amount=100.0)

# 生成实例图
print(result.diagram("flowchart"))
print(result.diagram("sequence"))
```

### 使用 CLI

```bash
# Dry-run 模式(生成静态图)
python -m rhosocial.activerecord.backend.impl.clickhouse \\
    procedure execute examples.order_workflow.OrderProcessingProcedure \\
    --order-id 1 --user-id 1 --dry-run

# 列出所有过程
python -m rhosocial.activerecord.backend.impl.clickhouse \\
    procedure list examples.order_workflow
```

## 依赖

- python-activerecord (核心包)
- python-activerecord-clickhouse (ClickHouse 后端)

## 文档

- [中文文档](../../../zh_CN/backend/named_expression.md)
- [English Documentation](../../../en_US/backend/named_expression.md)