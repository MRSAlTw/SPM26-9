"""GIMP 运行环境探测。

在导入 GIMP Python API (``gi.repository.Gimp``) 失败时退化为独立模式，
这样同一份代码既能作为 GIMP 插件，又能在普通 Python 环境里调试 UI。
"""

from __future__ import annotations

GIMP_AVAILABLE = False

try:
    import gi  # type: ignore[import-not-found]
    gi.require_version("Gimp", "3.0")
    from gi.repository import Gimp  # type: ignore[import-not-found]  # noqa: F401
    GIMP_AVAILABLE = True
except Exception:  # noqa: BLE001 - 任何导入异常都视为独立模式
    GIMP_AVAILABLE = False
