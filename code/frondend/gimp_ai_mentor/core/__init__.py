"""Core 业务编排层。

UI 不直接调用 API，由 ``CoreController`` 协调：图像读取 -> AI 接口 -> 状态变更 -> UI 回调。
"""

from .controller import CoreController

__all__ = ["CoreController"]
