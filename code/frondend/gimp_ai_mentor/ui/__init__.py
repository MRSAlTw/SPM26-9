"""UI 层 (GTK 3)。

- ``ui_manager``: 面板生命周期 (SRS-3001)
- ``main_panel``:  主控制面板 (实现 SRS-3002 / SRS-3003 / SRS-3004)
- ``components``:  通用小组件 (Toast / 步骤行 / 诊断卡)
- ``theme``:       全局深色主题 CSS
"""

from .ui_manager import UIManager

__all__ = ["UIManager"]
