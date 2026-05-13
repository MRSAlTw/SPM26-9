"""本地 Mock 后端。

后端未就绪时，AIClient 会自动降级到本模块返回模拟数据，方便前端独立联调。
所有返回值结构与接口文档一致。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List


def _uuid() -> str:
    return str(uuid.uuid4())


class MockBackend:
    """所有方法对应一个接口路径。"""

    # ---------- SRS-3011 图像诊断分析接口 ----------
    def analyze_image(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        time.sleep(0.4)  # 模拟分析耗时
        return {
            "request_id": payload.get("request_id", _uuid()),
            "status": "success",
            "summary": "图像整体中间调偏暗，肤色略偏黄，背景层次感不足。",
            "problems": [
                {
                    "problem_id": "p1",
                    "type": "underexposure",
                    "target": "global",
                    "region": None,
                    "severity": "medium",
                    "description": "整体画面中间调偏暗",
                },
                {
                    "problem_id": "p2",
                    "type": "skin_tone_cast",
                    "target": "local",
                    "region": {"x1": 120, "y1": 80, "x2": 360, "y2": 420},
                    "severity": "low",
                    "description": "肤色略偏黄，可适当增加红润感",
                },
            ],
            "suggestions": [
                "轻微提亮中间调",
                "适度调整肤色区域色彩平衡",
                "增强背景对比度",
            ],
            "confidence": 0.91,
            # UI 雷达图所需指标 (扩展字段)
            "metrics": {
                "曝光": 75,
                "构图": 90,
                "动态范围": 60,
                "色彩": 85,
                "清晰度": 95,
            },
            "health_score": 84,
        }

    # ---------- SRS-3012 修图指导生成接口 ----------
    def generate_guide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        time.sleep(0.6)
        prompt = (payload.get("user_prompt") or "").strip()
        # 简单根据关键词调整步骤主题，让 Mock 更"像"
        guide_name = "智能修图方案" if not prompt else f"基于「{prompt[:12]}」的方案"
        return {
            "request_id": payload.get("request_id", _uuid()),
            "status": "success",
            "guide_name": guide_name,
            "steps": [
                {
                    "step_id": "step_01",
                    "order": 1,
                    "title": "复制活动图层作为预览层",
                    "instruction": "复制当前图层并命名为 AI Preview，用于非破坏性预览。",
                    "action_type": "layer_copy",
                    "target": "active_layer",
                    "pdb_operation": {
                        "name": "gimp-layer-copy",
                        "params": {"add_alpha": True},
                    },
                    "allow_skip": False,
                    "tool_name": "图层复制",
                    "color": "orange",
                },
                {
                    "step_id": "step_02",
                    "order": 2,
                    "title": "提亮中间调",
                    "instruction": "对预览层执行色阶调整，轻微提亮整体中间调。",
                    "action_type": "levels_adjust",
                    "target": "preview_layer",
                    "pdb_operation": {
                        "name": "gimp-drawable-levels",
                        "params": {"channel": "VALUE", "gamma": 1.12},
                    },
                    "allow_skip": True,
                    "tool_name": "色阶",
                    "color": "blue",
                },
                {
                    "step_id": "step_03",
                    "order": 3,
                    "title": "调整肤色色彩平衡",
                    "instruction": "在肤色区域适度增加红色和黄色倾向，使肤色更自然。",
                    "action_type": "color_balance",
                    "target": "selection",
                    "pdb_operation": {
                        "name": "gimp-drawable-color-balance",
                        "params": {
                            "transfer_mode": "MIDTONES",
                            "cyan_red": 0.08,
                            "magenta_green": -0.02,
                            "yellow_blue": -0.05,
                        },
                    },
                    "allow_skip": True,
                    "tool_name": "色彩平衡",
                    "color": "purple",
                },
                {
                    "step_id": "step_04",
                    "order": 4,
                    "title": "USM 锐化",
                    "instruction": "对预览层做轻度 USM 锐化，增强五官与发丝的立体感。",
                    "action_type": "unsharp_mask",
                    "target": "preview_layer",
                    "pdb_operation": {
                        "name": "plug-in-unsharp-mask",
                        "params": {"radius": 1.2, "amount": 0.4, "threshold": 0},
                    },
                    "allow_skip": True,
                    "tool_name": "USM锐化",
                    "color": "green",
                },
            ],
        }

    # ---------- SRS-3013 通知提醒接口 ----------
    def notify(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # 通知接口本身只回执
        return {"status": "success", "message": "通知推送成功"}

    # ---------- SRS-3014 状态更新接口 ----------
    def state_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "message": "状态同步成功"}

    # ---------- SRS-3015 用户指令交互接口 ----------
    def user_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cmd = payload.get("command_type", "")
        next_action_map = {
            "next_step": "load_next_step",
            "skip_step": "load_next_step",
            "apply": "commit_changes",
            "undo": "revert_changes",
            "analyze": "show_diagnosis",
        }
        return {
            "status": "success",
            "message": "命令执行成功",
            "next_action": next_action_map.get(cmd, "noop"),
        }
