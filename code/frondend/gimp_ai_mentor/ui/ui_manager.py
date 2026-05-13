"""面板生命周期管理 (SRS-3001)。

提供 ``UIManager.create_panel(image, drawable) -> Gtk.Window``
和 ``UIManager.destroy_panel() -> bool``。
"""

from __future__ import annotations

from typing import Any, Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # type: ignore[import-not-found]

from ..config import write_log
from ..core import CoreController
from .main_panel import MainPanel
from .theme import apply_theme


class UIManager:
    """单例式管理面板生命周期。"""

    def __init__(self) -> None:
        self._window: Optional[Gtk.Window] = None
        self._panel: Optional[MainPanel] = None
        self._controller: Optional[CoreController] = None

    def create_panel(self, image: Any = None, drawable: Any = None) -> Gtk.Window:
        """SRS-3001 1.1。

        :raises Exception: 初始化失败时抛出。
        """
        if self._window is not None:
            self._window.present()
            return self._window

        try:
            apply_theme()

            self._controller = CoreController(image=image, drawable=drawable)
            self._panel = MainPanel(controller=self._controller)
            self._controller.register_view(self._panel)

            window = Gtk.Window(title="GIMP AI Mentor")
            window.set_default_size(380, 700)
            window.set_keep_above(True)  # 浮在 GIMP 窗口上方更顺手
            window.add(self._panel)
            window.connect("destroy", self._on_destroy)

            window.show_all()
            self._window = window
            write_log("INFO", "UI", "插件主面板已创建")
            return window
        except Exception as e:
            write_log("ERROR", "UI", f"create_panel 失败: {e}")
            raise

    def destroy_panel(self) -> bool:
        """SRS-3001 1.2。"""
        if self._window is None:
            return True
        try:
            # 先通知 Core 清理临时图层 (撤销状态机由 Core 决定具体动作)
            if self._controller is not None:
                self._controller.shutdown()
            self._window.destroy()
            self._window = None
            self._panel = None
            self._controller = None
            write_log("INFO", "UI", "插件主面板已销毁")
            return True
        except Exception as e:
            write_log("ERROR", "UI", f"destroy_panel 失败: {e}")
            return False

    def _on_destroy(self, _w) -> None:
        """窗口被用户直接关闭时的回调。"""
        if self._controller is not None:
            try:
                self._controller.shutdown()
            except Exception:  # noqa: BLE001
                pass
        self._window = None
        self._panel = None
        self._controller = None
