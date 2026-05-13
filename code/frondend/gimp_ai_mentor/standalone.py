"""独立运行入口 (无 GIMP 时调试 UI)。

用法::

    python -m gimp_ai_mentor.standalone

会弹出 GTK 主窗口，所有 GIMP 调用走 Mock，所有 AI 接口走本地 Mock。
"""

from __future__ import annotations

import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # type: ignore[import-not-found]

from .config import write_log
from .ui import UIManager


def main() -> int:
    write_log("INFO", "Standalone", "独立模式启动")
    manager = UIManager()
    win = manager.create_panel(image=None, drawable=None)
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
