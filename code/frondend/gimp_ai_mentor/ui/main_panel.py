"""主控制面板 (右侧侧边栏)。

实现接口契约：
- ``bind_diagnosis_data(diagnosis_dict)``      (SRS-3002 2.1)
- ``update_step_list(steps)``                   (SRS-3002 2.2)
- ``update_step_status(step_id, status)``       (SRS-3002 2.2)
- ``show_toast_message(msg, msg_type)``         (SRS-3004 4.2)
- ``get_prompt_text() -> str``                  (SRS-3004 4.1)

布局对照原型 HTML 右侧 ``#ai-panel`` 区域：
- 顶部 header
- 「AI 智能修图」按钮
- 诊断报告卡片 (含雷达图 + 健康度 + 摘要)
- 自然语言输入框
- 步骤列表
- 底部 AI 状态栏
"""

from __future__ import annotations

from typing import Any, Dict, List

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # type: ignore[import-not-found]

from ..config import write_log
from ..constants import TOAST_INFO
from .components import RadarChart, StepRow, ToastManager


class MainPanel(Gtk.Box):
    """主面板。"""

    def __init__(self, controller) -> None:  # controller: CoreController
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(360, 600)
        self.get_style_context().add_class("ai-panel-bg")
        self.controller = controller
        self._step_rows: Dict[str, StepRow] = {}

        # ===== Header =====
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.get_style_context().add_class("panel-header")
        title = Gtk.Label(label="✦  AI 智能修图助手", xalign=0.0)
        title.set_hexpand(True)
        header.pack_start(title, expand=True, fill=True, padding=0)
        # settings 按钮 (占位)
        settings_btn = Gtk.Button(label="⚙")
        settings_btn.get_style_context().add_class("btn-ghost")
        settings_btn.set_tooltip_text("设置")
        header.pack_start(settings_btn, expand=False, fill=False, padding=0)
        self.pack_start(header, expand=False, fill=True, padding=0)

        # ===== Toast 容器 (在 header 下方) =====
        self.toast_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.toast_box.set_margin_left(8)
        self.toast_box.set_margin_right(8)
        self.toast_box.set_margin_top(4)
        self.pack_start(self.toast_box, expand=False, fill=True, padding=0)
        self.toast = ToastManager(self.toast_box)

        # ===== 滚动内容区 =====
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_left(12)
        content.set_margin_right(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        # --- AI 智能修图按钮 ---
        self.run_btn = Gtk.Button(label="🔍  AI 智能修图")
        self.run_btn.get_style_context().add_class("btn-primary")
        self.run_btn.connect("clicked", self._on_run_clicked)
        content.pack_start(self.run_btn, expand=False, fill=True, padding=0)

        # --- 诊断报告卡片 ---
        self.diag_card = self._build_diagnosis_card()
        self.diag_card.set_no_show_all(True)  # 默认隐藏
        content.pack_start(self.diag_card, expand=False, fill=True, padding=0)

        # --- 自然语言输入框 ---
        prompt_label = Gtk.Label(label="AI 指令中心", xalign=0.0)
        prompt_label.get_style_context().add_class("section-label")
        content.pack_start(prompt_label, expand=False, fill=True, padding=0)

        self.prompt_buffer = Gtk.TextBuffer()
        self.prompt_view = Gtk.TextView(buffer=self.prompt_buffer)
        self.prompt_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.prompt_view.get_style_context().add_class("input-area")
        self.prompt_view.set_size_request(-1, 80)
        prompt_frame = Gtk.Frame()
        prompt_frame.set_shadow_type(Gtk.ShadowType.NONE)
        prompt_frame.add(self.prompt_view)
        content.pack_start(prompt_frame, expand=False, fill=True, padding=0)

        # 占位提示
        self.prompt_buffer.set_text("")
        self._install_placeholder()

        send_btn = Gtk.Button(label="生成修图步骤  ➤")
        send_btn.get_style_context().add_class("btn-primary")
        send_btn.connect("clicked", self._on_send_clicked)
        content.pack_start(send_btn, expand=False, fill=True, padding=0)

        # --- 步骤列表 ---
        steps_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        steps_label = Gtk.Label(label="智能建议步骤", xalign=0.0)
        steps_label.get_style_context().add_class("section-label")
        steps_label.set_hexpand(True)
        self.step_count_label = Gtk.Label(label="0 步可用", xalign=1.0)
        self.step_count_label.get_style_context().add_class("section-label")
        steps_header.pack_start(steps_label, expand=True, fill=True, padding=0)
        steps_header.pack_start(self.step_count_label, expand=False, fill=False, padding=0)
        content.pack_start(steps_header, expand=False, fill=True, padding=0)

        self.steps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.pack_start(self.steps_box, expand=False, fill=True, padding=0)

        # 空状态
        self.empty_hint = Gtk.Label(label="输入修图需求，AI 将生成具体步骤")
        self.empty_hint.get_style_context().add_class("empty-hint")
        self.empty_hint.set_margin_top(20)
        self.empty_hint.set_margin_bottom(20)
        content.pack_start(self.empty_hint, expand=False, fill=True, padding=0)

        scroller.add(content)
        self.pack_start(scroller, expand=True, fill=True, padding=0)

        # ===== 底部状态栏 =====
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.get_style_context().add_class("footer-bar")
        self.status_dot = Gtk.Label(label="●")
        self.status_dot.set_markup("<span foreground='#22c55e'>●</span>")
        self.status_label = Gtk.Label(label="AI 服务在线", xalign=0.0)
        footer.pack_start(self.status_dot, expand=False, fill=False, padding=0)
        footer.pack_start(self.status_label, expand=True, fill=True, padding=0)
        self.pack_start(footer, expand=False, fill=True, padding=0)

    # ===== 诊断卡片 =====
    def _build_diagnosis_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("diagnosis-card")

        title = Gtk.Label(label="诊断报告", xalign=0.0)
        title.get_style_context().add_class("section-label")
        card.pack_start(title, expand=False, fill=True, padding=0)

        self.radar = RadarChart()
        card.pack_start(self.radar, expand=False, fill=True, padding=0)

        # 健康度
        score_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        score_row.pack_start(
            Gtk.Label(label="整体健康度:", xalign=0.0),
            expand=True, fill=True, padding=0,
        )
        self.score_label = Gtk.Label(label="--", xalign=1.0)
        self.score_label.get_style_context().add_class("score-badge")
        score_row.pack_start(self.score_label, expand=False, fill=False, padding=0)
        card.pack_start(score_row, expand=False, fill=True, padding=0)

        # 摘要
        self.summary_label = Gtk.Label(label="", xalign=0.0)
        self.summary_label.set_line_wrap(True)
        self.summary_label.set_max_width_chars(40)
        self.summary_label.get_style_context().add_class("diagnosis-summary")
        card.pack_start(self.summary_label, expand=False, fill=True, padding=0)

        return card

    # ===== Placeholder =====
    def _install_placeholder(self) -> None:
        """简易 placeholder：聚焦时清空灰色字。"""
        placeholder = "例如：把天空变成黄昏，增强肤色质感，移除左下角的杂物..."
        self.prompt_buffer.set_text(placeholder)
        self._has_placeholder = True

        def on_focus_in(_w, _e):
            if self._has_placeholder:
                self.prompt_buffer.set_text("")
                self._has_placeholder = False
            return False

        def on_focus_out(_w, _e):
            text = self._raw_prompt_text()
            if not text.strip():
                self.prompt_buffer.set_text(placeholder)
                self._has_placeholder = True
            return False

        self.prompt_view.connect("focus-in-event", on_focus_in)
        self.prompt_view.connect("focus-out-event", on_focus_out)

    def _raw_prompt_text(self) -> str:
        start = self.prompt_buffer.get_start_iter()
        end = self.prompt_buffer.get_end_iter()
        return self.prompt_buffer.get_text(start, end, False)

    # ===== UI 内部接口 (SRS-3004) =====
    def get_prompt_text(self) -> str:
        if self._has_placeholder:
            return ""
        return self._raw_prompt_text().strip()

    def show_toast_message(self, msg: str, msg_type: str = TOAST_INFO) -> None:
        self.toast.show(msg, msg_type)

    # ===== 数据绑定接口 (SRS-3002) =====
    def bind_diagnosis_data(self, diagnosis: Dict[str, Any]) -> None:
        GLib.idle_add(self._bind_diagnosis_in_main, diagnosis)

    def _bind_diagnosis_in_main(self, diagnosis: Dict[str, Any]) -> bool:
        # 摘要 (兼容 SDD 简单结构 / Mock 详细结构)
        summary = diagnosis.get("summary") or diagnosis.get("description") or ""
        # 兼容 SRS-3002 简化结构
        if not summary and diagnosis.get("problem_type"):
            summary = (
                f"{diagnosis.get('problem_type', '')} "
                f"({diagnosis.get('region', '')}, {diagnosis.get('severity', '')})"
            )
        self.summary_label.set_text(summary or "（无诊断摘要）")

        # 健康度
        score = diagnosis.get("health_score")
        if score is None and diagnosis.get("confidence") is not None:
            score = int(round(diagnosis["confidence"] * 100))
        if score is not None:
            self.score_label.set_text(f"{int(score)}%")

        # 雷达图指标
        metrics = diagnosis.get("metrics")
        if isinstance(metrics, dict) and metrics:
            self.radar.set_metrics({k: float(v) for k, v in metrics.items()})

        self.diag_card.set_no_show_all(False)
        self.diag_card.show_all()
        return False

    def update_step_list(self, steps: List[Dict[str, Any]]) -> None:
        GLib.idle_add(self._update_step_list_in_main, steps)

    def _update_step_list_in_main(self, steps: List[Dict[str, Any]]) -> bool:
        # 清空旧行
        for child in self.steps_box.get_children():
            self.steps_box.remove(child)
        self._step_rows.clear()

        if not steps:
            self.empty_hint.show()
            self.step_count_label.set_text("0 步可用")
            return False

        self.empty_hint.hide()
        for idx, step in enumerate(steps):
            row = StepRow(idx, step, self._on_step_action)
            self.steps_box.pack_start(row, expand=False, fill=True, padding=0)
            self._step_rows[step["step_id"]] = row
        self.steps_box.show_all()
        self.step_count_label.set_text(f"{len(steps)} 步可用")
        return False

    def update_step_status(self, step_id: str, status: str) -> None:
        GLib.idle_add(self._update_step_status_in_main, step_id, status)

    def _update_step_status_in_main(self, step_id: str, status: str) -> bool:
        row = self._step_rows.get(step_id)
        if row is not None:
            row.set_status(status)
        return False

    # ===== 用户操作 → Core 回调 (SRS-3003) =====
    def _on_run_clicked(self, _btn: Gtk.Button) -> None:
        prompt = self.get_prompt_text()
        write_log("INFO", "UI", f"点击 AI 智能修图，prompt={prompt!r}")
        self.run_btn.set_sensitive(False)

        def _restore() -> bool:
            self.run_btn.set_sensitive(True)
            return False

        GLib.timeout_add(1500, _restore)
        result = self.controller.on_submit_generate(prompt)
        if not result.get("success"):
            self.show_toast_message(result.get("msg", "提交失败"), "error")

    def _on_send_clicked(self, _btn: Gtk.Button) -> None:
        prompt = self.get_prompt_text()
        if not prompt:
            self.show_toast_message("请先输入修图需求", "warning")
            return
        self.controller.on_submit_generate(prompt)

    def _on_step_action(self, step_id: str, action: str) -> None:
        self.controller.on_step_action(step_id, action)
