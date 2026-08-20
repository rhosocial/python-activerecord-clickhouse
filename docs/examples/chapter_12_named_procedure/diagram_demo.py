# docs/examples/chapter_12_named_procedure/diagram_demo.py
"""
命名过程静态图和实例图演示脚本。

该脚本展示如何:
1. 生成静态图(无需数据库连接)
2. 执行过程后生成实例图
3. 将图嵌入文档
"""
from rhosocial.activerecord.backend.named_expression import (
    Procedure,
    ProcedureContext,
    ProcedureRunner,
    ParallelStep,
)


class OrderWorkflowProcedure(Procedure):
    """订单处理工作流 - 展示并行和条件分支。"""

    order_id: int
    user_id: int

    def run(self, ctx: ProcedureContext) -> None:
        ctx.log("开始订单处理")

        ctx.execute("examples.queries.order_queries.get_order", params={"order_id": self.order_id}, bind="order")

        ctx.execute("examples.queries.order_queries.check_inventory", params={"order_id": self.order_id}, bind="inv")

        ctx.parallel(
            ParallelStep("examples.queries.order_queries.reserve_inventory", params={"order_id": self.order_id}),
            ParallelStep("examples.queries.order_queries.send_notification", params={"user_id": self.user_id}),
            max_concurrency=2,
        )

        ctx.execute("examples.queries.order_queries.process_payment", params={"order_id": self.order_id, "amount": 100.0})

        ctx.log("订单处理完成")


class ShippingWorkflowProcedure(Procedure):
    """物流处理工作流 - 展示更复杂的流程。"""

    order_id: int
    shipping_method: str = "standard"

    def run(self, ctx: ProcedureContext) -> None:
        ctx.log("开始物流处理")

        ctx.execute("examples.queries.order_queries.get_order", params={"order_id": self.order_id}, bind="order")

        if self.shipping_method == "express":
            ctx.execute("examples.queries.order_queries.check_inventory", params={"order_id": self.order_id}, bind="inv")
            ctx.execute("examples.queries.order_queries.reserve_inventory", params={"order_id": self.order_id})
        else:
            ctx.log("使用标准物流")

        ctx.execute("examples.queries.order_queries.send_notification", params={"user_id": 1, "type": "shipping"})

        ctx.log("物流处理完成")


def demo_static_diagram():
    """演示静态图生成。"""
    print("=" * 60)
    print("静态流程图 - OrderWorkflowProcedure")
    print("=" * 60)
    print(OrderWorkflowProcedure.static_diagram("flowchart"))

    print("\n" + "=" * 60)
    print("静态序列图 - OrderWorkflowProcedure")
    print("=" * 60)
    print(OrderWorkflowProcedure.static_diagram("sequence"))

    print("\n" + "=" * 60)
    print("静态流程图 - ShippingWorkflowProcedure")
    print("=" * 60)
    print(ShippingWorkflowProcedure.static_diagram("flowchart"))

    print("\n" + "=" * 60)
    print("静态序列图 - ShippingWorkflowProcedure")
    print("=" * 60)
    print(ShippingWorkflowProcedure.static_diagram("sequence"))


def demo_instance_diagram():
    """演示实例图生成(需要模拟执行)。"""
    from unittest.mock import MagicMock

    mock_dialect = MagicMock()
    mock_backend = MagicMock()
    mock_backend.execute_callback.return_value = [{"id": 1, "status": "pending"}]
    mock_backend.dialect = mock_dialect
    mock_dialect.format.return_value = ("SELECT 1", ())

    runner = ProcedureRunner(OrderWorkflowProcedure, mock_backend)
    result = runner.run(mock_backend, order_id=1, user_id=1)

    print("=" * 60)
    print("实例流程图(成功)")
    print("=" * 60)
    print(result.diagram("flowchart"))

    print("\n" + "=" * 60)
    print("实例序列图(成功)")
    print("=" * 60)
    print(result.diagram("sequence"))


if __name__ == "__main__":
    demo_static_diagram()

    print("\n" + "=" * 60)
    print("实例图演示(需要真实数据库或模拟)")
    print("=" * 60)