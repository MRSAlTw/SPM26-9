"""可复用的 GTK 小组件：步骤行、Toast、雷达图绘制。"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # type: ignore[import-not-found]

from ..constants import (
    ACTION_EXECUTE,
    ACTION_IGNORE,
    STEP_ACTIVE,
    STEP_COMPLETED,
    STEP_IGNORED,
    STEP_PENDING,
    TOAST_ERROR,
    TOAST_INFO,
    TOAST_SUCCESS,
    TOAST_WARNING,
)


# ===== Toast =====
def _toast_class(level: str) -> str:
    return {
        TOAST_INFO: "toast-info",
        TOAST_SUCCESS: "toast-success",
        TOAST_WARNING: "toast-warning",
        TOAST_ERROR: "toast-error",
    }.get(level, "toast-info")


class ToastManager:
    """简易 Toast：在传入容器顶部插入条状提示，3 秒后自动淡出。"""

    def __init__(self, parent_box: Gtk.Box) -> None:
        self.parent = parent_box

    def show(self, msg: str, level: str = TOAST_INFO) -> None:
        # 必须切回主线程
        GLib.idle_add(self._show_in_main, msg, level)

    def _show_in_main(self, msg: str, level: str) -> bool:
        toast = Gtk.Label(label=msg)
        toast.set_xalign(0.0)
        toast.set_line_wrap(True)
        toast.get_style_context().add_class("toast")
        toast.get_style_context().add_class(_toast_class(level))

        self.parent.pack_start(toast, expand=False, fill=True, padding=4)
        toast.show()

        # 3 秒后移除
        def _remove() -> bool:
            if toast.get_parent() is not None:
                self.parent.remove(toast)
            return False

        GLib.timeout_add(3000, _remove)
        return False  # idle_add 一次性


# ===== 步骤行 =====
class StepRow(Gtk.Box):
    """单个步骤行。"""

    def __init__(
        self,
        index: int,
        step: Dict[str, Any],
        on_action: Callable[[str, str], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.step = step
        self.step_id: str = step["step_id"]
        self.on_action = on_action
        self._status = STEP_PENDING

        self.get_style_context().add_class("step-row")
        self.get_style_context().add_class("step-pending")

        # 序号
        self.number_label = Gtk.Label(label=f"{index + 1:02d}")
        self.number_label.get_style_context().add_class("step-number")
        self.pack_start(self.number_label, expand=False, fill=False, padding=0)

        # 文案
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=step.get("title", ""), xalign=0.0)
        title.get_style_context().add_class("step-title")
        title.set_ellipsize(Pango.EllipsizeMode.END)
        desc = Gtk.Label(
            label=step.get("instruction") or step.get("desc") or "",
            xalign=0.0,
        )
        desc.get_style_context().add_class("step-desc")
        desc.set_ellipsize(Pango.EllipsizeMode.END)
        desc.set_line_wrap(True)
        desc.set_max_width_chars(40)
        text_box.pack_start(title, expand=False, fill=True, padding=0)
        text_box.pack_start(desc, expand=False, fill=True, padding=0)
        self.pack_start(text_box, expand=True, fill=True, padding=0)

        # 状态图标
        self.status_label = Gtk.Label(label="")
        self.pack_start(self.status_label, expand=False, fill=False, padding=0)

        # 执行按钮
        exec_btn = Gtk.Button(label="执行")
        exec_btn.get_style_context().add_class("btn-primary")
        exec_btn.connect("clicked", lambda *_: self.on_action(self.step_id, ACTION_EXECUTE))
        self.pack_start(exec_btn, expand=False, fill=False, padding=0)

        # 忽略按钮（allow_skip=False 时禁用）
        skip_btn = Gtk.Button(label="忽略")
        skip_btn.get_style_context().add_class("btn-ghost")
        if not step.get("allow_skip", True):
            skip_btn.set_sensitive(False)
            skip_btn.set_tooltip_text("该步骤为必要操作，不可跳过")
        skip_btn.connect("clicked", lambda *_: self.on_action(self.step_id, ACTION_IGNORE))
        self.pack_start(skip_btn, expand=False, fill=False, padding=0)

    def set_status(self, status: str) -> None:
        ctx = self.get_style_context()
        # 清除旧 status class
        for cls in ("step-pending", "step-active", "step-completed", "step-ignored"):
            ctx.remove_class(cls)
        ctx.add_class({
            STEP_PENDING: "step-pending",
            STEP_ACTIVE: "step-active",
            STEP_COMPLETED: "step-completed",
            STEP_IGNORED: "step-ignored",
        }.get(status, "step-pending"))
        self._status = status

        # 状态图标
        icon = {
            STEP_PENDING: "",
            STEP_ACTIVE: "⏳",
            STEP_COMPLETED: "✓",
            STEP_IGNORED: "⊘",
        }.get(status, "")
        self.status_label.set_text(icon)


# ===== 雷达图 (Cairo) =====
class RadarChart(Gtk.DrawingArea):
    """简易雷达图：5 个维度。"""

    def __init__(self) -> None:
        super().__init__()
        self.set_size_request(-1, 160)
        self.metrics: Dict[str, float] = {
            "曝光": 0,
            "构图": 0,
            "动态范围": 0,
            "色彩": 0,
            "清晰度": 0,
        }
        self.connect("draw", self._on_draw)

    def set_metrics(self, metrics: Dict[str, float]) -> None:
        if metrics:
            self.metrics = metrics
        self.queue_draw()

    def _on_draw(self, _widget: Gtk.Widget, cr) -> bool:
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        cx, cy = w / 2, h / 2
        radius = max(min(cx, cy) - 24, 20)

        names = list(self.metrics.keys())
        values = list(self.metrics.values())
        n = len(names)
        if n < 3:
            return False
        step_angle = 2 * math.pi / n

        # 背景网格
        cr.set_source_rgba(1, 1, 1, 0.1)
        cr.set_line_width(1)
        for level in range(1, 5):
            r = radius * level / 4
            cr.move_to(cx + r * math.cos(-math.pi / 2), cy + r * math.sin(-math.pi / 2))
            for i in range(1, n + 1):
                a = i * step_angle - math.pi / 2
                cr.line_to(cx + r * math.cos(a), cy + r * math.sin(a))
            cr.close_path()
            cr.stroke()

        # 轴线
        for i in range(n):
            a = i * step_angle - math.pi / 2
            cr.move_to(cx, cy)
            cr.line_to(cx + radius * math.cos(a), cy + radius * math.sin(a))
            cr.stroke()

        # 标签
        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.set_font_size(10)
        for i, name in enumerate(names):
            a = i * step_angle - math.pi / 2
            x = cx + (radius + 14) * math.cos(a)
            y = cy + (radius + 14) * math.sin(a)
            extents = cr.text_extents(name)
            cr.move_to(x - extents.width / 2, y + extents.height / 2)
            cr.show_text(name)

        # 数据多边形
        cr.set_source_rgba(1.0, 0.616, 0.0, 0.3)
        for i in range(n):
            a = i * step_angle - math.pi / 2
            r = radius * max(0, min(100, values[i])) / 100
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.close_path()
        cr.fill_preserve()
        cr.set_source_rgb(1.0, 0.616, 0.0)
        cr.set_line_width(2)
        cr.stroke()

        # 数据点
        cr.set_source_rgb(1.0, 0.616, 0.0)
        for i in range(n):
            a = i * step_angle - math.pi / 2
            r = radius * max(0, min(100, values[i])) / 100
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            cr.arc(x, y, 3.5, 0, 2 * math.pi)
            cr.fill()

        return False
