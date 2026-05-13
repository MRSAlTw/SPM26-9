"""核心控制器。

职责：
- 编排 SRS-3001~3004 (UI ↔ Core) 与 SRS-3011~3015 (Core ↔ AI / UI) 的交互
- 所有耗时调用放到后台线程，避免阻塞 GTK 主循环
- 通过回调把结果送回 UI (UI 自身负责 GLib.idle_add 切回主线程)

UI 端通过 ``register_view`` 注入实现了以下方法的 view 对象::

    bind_diagnosis_data(diagnosis_dict: dict) -> None
    update_step_list(steps: list) -> None
    update_step_status(step_id: str, status: str) -> None
    show_toast_message(msg: str, msg_type: str) -> None
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Protocol

from ..api import AIClient, APIError
from ..config import write_log
from ..constants import (
    ACTION_EXECUTE,
    ACTION_IGNORE,
    CMD_ANALYZE,
    CMD_NEXT_STEP,
    CMD_SKIP_STEP,
    STEP_ACTIVE,
    STEP_COMPLETED,
    STEP_IGNORED,
    STEP_PENDING,
    TOAST_ERROR,
    TOAST_INFO,
    TOAST_SUCCESS,
    TOAST_WARNING,
)
from ..gimp_adapter import (
    get_image_for_analysis,
    register_state_listener,
    run_pdb_operation,
    unregister_state_listener,
)


class UIView(Protocol):  # pragma: no cover - 仅类型说明
    def bind_diagnosis_data(self, diagnosis: Dict[str, Any]) -> None: ...
    def update_step_list(self, steps: List[Dict[str, Any]]) -> None: ...
    def update_step_status(self, step_id: str, status: str) -> None: ...
    def show_toast_message(self, msg: str, msg_type: str) -> None: ...


class CoreController:
    """业务总线。线程安全：耗时操作均在后台线程内完成。"""

    def __init__(
        self,
        client: Optional[AIClient] = None,
        image: Any = None,
        drawable: Any = None,
    ) -> None:
        self.client = client or AIClient()
        self.image = image
        self.drawable = drawable
        self.view: Optional[UIView] = None

        # 内部状态
        self._diagnosis: Optional[Dict[str, Any]] = None
        self._steps: List[Dict[str, Any]] = []
        self._step_status: Dict[str, str] = {}
        self._listener_id: Optional[int] = None

    # ===== 生命周期 =====
    def register_view(self, view: UIView) -> None:
        """注入 UI 视图；同时启动 GIMP 状态监听 (SRS-3022)。"""
        self.view = view
        try:
            self._listener_id = register_state_listener(self._on_gimp_state_changed)
        except Exception as e:  # noqa: BLE001
            write_log("WARNING", "Core", f"状态监听注册失败: {e}")

    def shutdown(self) -> None:
        """销毁前清理资源 (SRS-3001 1.2)。"""
        if self._listener_id is not None:
            try:
                unregister_state_listener(self._listener_id)
            except Exception:  # noqa: BLE001
                pass
        write_log("INFO", "Core", "CoreController 已关闭")

    # ===== UI 入口：用户操作回调 (SRS-3003) =====
    def on_submit_generate(self, user_prompt: str) -> Dict[str, Any]:
        """用户点击「智能分析 / 智能修图」。

        返回值符合 SRS-3003 约定，UI 立即拿到 ``{"success": True, "msg": "..."}``。
        实际工作放到后台线程，结果通过 view 回调返回。
        """
        prompt = (user_prompt or "").strip()
        write_log("INFO", "Core", f"on_submit_generate prompt={prompt!r}")
        threading.Thread(
            target=self._do_analyze_and_generate,
            args=(prompt,),
            name="ai-pipeline",
            daemon=True,
        ).start()
        return {"success": True, "msg": "AI 处理中..."}

    def on_step_action(self, step_id: str, action: str) -> bool:
        """用户对步骤的「执行」/「忽略」操作 (SRS-3003 3.2)。"""
        write_log("INFO", "Core", f"on_step_action step={step_id} action={action}")
        if action not in (ACTION_EXECUTE, ACTION_IGNORE):
            self._toast(f"未知动作: {action}", TOAST_WARNING)
            return False

        step = self._find_step(step_id)
        if step is None:
            self._toast(f"步骤不存在: {step_id}", TOAST_ERROR)
            return False

        if action == ACTION_IGNORE:
            self._set_status(step_id, STEP_IGNORED)
            self._send_user_command(CMD_SKIP_STEP, step_id)
            return True

        # execute: 异步执行
        self._set_status(step_id, STEP_ACTIVE)
        threading.Thread(
            target=self._do_execute_step,
            args=(step,),
            name=f"pdb-{step_id}",
            daemon=True,
        ).start()
        return True

    # ===== 后台流水线 =====
    def _do_analyze_and_generate(self, prompt: str) -> None:
        """完整流水线：取图 -> 诊断 -> 生成步骤。"""
        try:
            # 1) 取图 (SRS-3021)
            img_payload = get_image_for_analysis(self.image, self.drawable)
            if not img_payload.get("success"):
                self._toast("无法读取当前图像，请先打开一张图片", TOAST_ERROR)
                return

            # 2) 诊断 (SRS-3011)
            self._toast("AI 正在分析图像...", TOAST_INFO)
            ana_req = {
                "image_base64": img_payload["image_base64"],
                "image_width": img_payload.get("metadata", {}).get("width"),
                "image_height": img_payload.get("metadata", {}).get("height"),
            }
            diagnosis = self.client.analyze_image(ana_req)
            if diagnosis.get("status") != "success":
                self._toast(
                    diagnosis.get("error_message", "图像分析失败"),
                    TOAST_ERROR,
                )
                return

            self._diagnosis = diagnosis
            self._send_user_command(CMD_ANALYZE, None)
            if self.view is not None:
                self.view.bind_diagnosis_data(diagnosis)

            # 3) 生成步骤 (SRS-3012)
            self._toast("正在生成修图方案...", TOAST_INFO)
            guide_req = {
                "image_base64": img_payload["image_base64"],
                "user_prompt": prompt,
                "analysis_result": diagnosis,
                "has_selection": img_payload.get("metadata", {}).get("has_selection", False),
                "preview_mode": True,
            }
            guide = self.client.generate_guide(guide_req)
            if guide.get("status") != "success":
                self._toast(
                    guide.get("error_message", "方案生成失败"),
                    TOAST_ERROR,
                )
                return

            self._steps = list(guide.get("steps") or [])
            self._step_status = {s["step_id"]: STEP_PENDING for s in self._steps}
            if self.view is not None:
                self.view.update_step_list(self._steps)
            self._toast(f"方案已生成: {guide.get('guide_name', '')}", TOAST_SUCCESS)

        except APIError as e:
            write_log("ERROR", "Core", f"流水线失败: {e}")
            self._toast(e.message, TOAST_ERROR)
        except Exception as e:  # noqa: BLE001
            write_log("ERROR", "Core", f"流水线未知异常: {e}")
            self._toast(f"内部错误: {e}", TOAST_ERROR)

    def _do_execute_step(self, step: Dict[str, Any]) -> None:
        """执行单步 PDB 操作并回写状态。"""
        sid = step["step_id"]
        op = step.get("pdb_operation") or {}
        try:
            ok = run_pdb_operation(self.image, self.drawable, op)
            if ok:
                self._set_status(sid, STEP_COMPLETED)
                self._send_user_command(CMD_NEXT_STEP, sid)
                self._toast(f"已完成: {step.get('title', sid)}", TOAST_SUCCESS)
            else:
                self._set_status(sid, STEP_PENDING)
                self._toast(f"步骤执行失败: {step.get('title', sid)}", TOAST_ERROR)
        except Exception as e:  # noqa: BLE001
            write_log("ERROR", "Core", f"PDB 执行失败 step={sid}: {e}")
            self._set_status(sid, STEP_PENDING)
            self._toast(f"执行异常: {e}", TOAST_ERROR)

    # ===== 内部辅助 =====
    def _find_step(self, step_id: str) -> Optional[Dict[str, Any]]:
        return next((s for s in self._steps if s.get("step_id") == step_id), None)

    def _set_status(self, step_id: str, status: str) -> None:
        self._step_status[step_id] = status
        if self.view is not None:
            try:
                self.view.update_step_status(step_id, status)
            except Exception as e:  # noqa: BLE001
                write_log("WARNING", "Core", f"update_step_status 回调异常: {e}")

    def _toast(self, msg: str, level: str) -> None:
        if self.view is None:
            write_log("INFO", "Core", f"[Toast/{level}] {msg}")
            return
        try:
            self.view.show_toast_message(msg, level)
        except Exception as e:  # noqa: BLE001
            write_log("WARNING", "Core", f"show_toast_message 异常: {e}")

    def _send_user_command(self, command_type: str, current_step_id: Optional[str]) -> None:
        """SRS-3015 用户指令交互接口。失败仅记录日志，不影响主流程。"""
        try:
            self.client.user_command({
                "command_id": str(uuid.uuid4()),
                "command_type": command_type,
                "current_step_id": current_step_id,
            })
        except APIError as e:
            write_log("WARNING", "Core", f"user_command 失败 ({command_type}): {e.message}")
        except Exception as e:  # noqa: BLE001
            write_log("WARNING", "Core", f"user_command 未知异常: {e}")

    def _on_gimp_state_changed(self, state: Dict[str, Any]) -> None:
        """GIMP 状态变化回调 (SRS-3022)。透传给 SRS-3014。"""
        try:
            self.client.state_update({
                "event_id": str(uuid.uuid4()),
                "event_type": "state_snapshot",
                "active_layer": {"name": state.get("active_layer_name")} if state.get("active_layer_name") else None,
                "selection": {"has_selection": state.get("has_selection", False)},
                "tool": {"current_tool": state.get("current_tool")} if state.get("current_tool") else None,
            })
        except Exception:  # noqa: BLE001
            # 静默：状态同步失败不应打扰用户
            pass
