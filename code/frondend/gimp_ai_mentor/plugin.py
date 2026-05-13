"""GIMP 3.x 插件入口。

部署方式::

    # macOS / Linux
    cp -r gimp_ai_mentor ~/.config/GIMP/3.0/plug-ins/ai-mentor
    chmod +x ~/.config/GIMP/3.0/plug-ins/ai-mentor/plugin.py

启动 GIMP 后，菜单：Filters → AI → AI 修图助手...
"""

from __future__ import annotations

import sys

try:
    import gi  # type: ignore[import-not-found]
    gi.require_version("Gimp", "3.0")
    gi.require_version("GimpUi", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gimp, GimpUi, Gtk, GLib, GObject  # type: ignore[import-not-found]
except (ImportError, ValueError):
    # GIMP 不存在时，本文件被普通 Python 解释器加载也能避免炸掉。
    Gimp = None  # type: ignore[assignment]


if Gimp is not None:
    from .ui import UIManager  # noqa: E402

    class GimpAIMentor(Gimp.PlugIn):  # pragma: no cover
        """GIMP 3 PlugIn 注册类。"""

        def do_query_procedures(self):
            return ["plug-in-ai-mentor-open"]

        def do_create_procedure(self, name):
            procedure = Gimp.ImageProcedure.new(
                self,
                name,
                Gimp.PDBProcType.PLUGIN,
                self._run,
                None,
            )
            procedure.set_image_types("*")
            procedure.set_menu_label("AI 修图助手...")
            procedure.add_menu_path("<Image>/Filters/AI/")
            procedure.set_documentation(
                "AI 智能修图助手",
                "调用 AI 分析图像并生成修图步骤",
                name,
            )
            procedure.set_attribution("GIMP AI Mentor", "GIMP AI Mentor", "2026")
            return procedure

        def _run(self, procedure, run_mode, image, drawables, config, run_data):
            GimpUi.init("plug-in-ai-mentor-open")
            drawable = drawables[0] if drawables else None

            manager = UIManager()
            window = manager.create_panel(image=image, drawable=drawable)
            # 保持主循环直到窗口关闭
            window.connect("destroy", lambda *_: Gtk.main_quit())
            Gtk.main()
            manager.destroy_panel()

            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    Gimp.main(GimpAIMentor.__gtype__, sys.argv)
