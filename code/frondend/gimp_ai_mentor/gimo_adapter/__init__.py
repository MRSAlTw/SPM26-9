"""GIMP 适配层 (SRS-3021 / SRS-3022)。

- ``image_reader``: 从 GIMP 图像导出 Base64 + 元数据
- ``state_listener``: 注册/注销 GIMP 状态监听器
- ``pdb_runner``: 执行 PDB 操作 (步骤里的 ``pdb_operation``)

当 GIMP 模块不可用 (例如独立调试) 时，自动降级为返回示例数据的 Mock 实现。
"""

from .image_reader import get_image_for_analysis
from .pdb_runner import run_pdb_operation
from .state_listener import register_state_listener, unregister_state_listener

__all__ = [
    "get_image_for_analysis",
    "run_pdb_operation",
    "register_state_listener",
    "unregister_state_listener",
]
