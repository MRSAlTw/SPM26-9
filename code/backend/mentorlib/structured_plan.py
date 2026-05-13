# -*- coding: utf-8 -*-
"""
把「小组 AI 返回的文本」转成 schema 可校验的 plan dict。

推荐协议（与「只返回中文建议」兼容）：
- 正文：自然语言修图建议（给用户看）；
- 文末：单独一块机器可读 JSON（用于预览与 pdb_runner），用 Markdown 围栏包起来。

若 AI 层暂时只能产中文、不能产 JSON，见 llm_stub 中的兜底策略（两阶段调用或 ops=[]）。
"""

from __future__ import unicode_literals

import json
import re

try:
    basestring
except NameError:
    basestring = str

from mentorlib import action_plan_adapter
from mentorlib import schema


def prompt_json_fence_instruction_zh():
    """
    可整段贴进你们大模型 system / user 提示词末尾，约束输出结构。
    ops[].op 必须为白名单英文标识符（与 GIMP 内部名一致，便于 pdb_runner 映射）。
    """
    ops_list = ", ".join(sorted(schema.ALLOWED_OPS))
    return (
        "除自然语言说明外，请在回复最后追加且仅追加一段 JSON，并用 Markdown 代码围栏包裹，"
        "格式为：\n"
        "```json\n"
        "{ ... }\n"
        "```\n"
        "JSON 顶层字段必须为：\n"
        '  "summary": string,        // 方案摘要（可用中文）\n'
        '  "steps_for_user": [string, ...],  // 建议用户在自己原图上操作的步骤（中文）\n'
        '  "ops": [ { "op": string, "args": { ... } }, ... ]   // 仅在预览副本上执行的指令\n'
        "其中 ops[].op 只能是以下英文标识之一：\n"
        + ops_list
        + "。\n"
        "args 的键名与 mentorlib/schema.py 校验规则一致；不要发明未在白名单中的 op。"
    )


def prompt_action_plan_format_zh():
    """
    若接口返回「action_plan」数组（中文 tool、menu_path 等），
    可使用本说明约束模型；解析由 action_plan_adapter.action_plan_to_plan 完成。
    """
    return (
        "也可返回仅含 action_plan 的 JSON，例如：\n"
        "{\n"
        '  "action_plan": [\n'
        "    {\n"
        '      "step": 1,\n'
        '      "tool": "色阶",\n'
        '      "menu_path": "颜色 -> 色阶",\n'
        '      "action": "调整输入色阶中间调",\n'
        '      "value": 1.35,\n'
        '      "unit": "gamma",\n'
        '      "reason": "提亮中间调"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "其中 tool 为中文工具名（与高斯模糊、色相饱和度等同义映射见 mentorlib/action_plan_adapter.py）。\n"
        "插件会自动生成 summary、steps_for_user，并转换为 ops 供预览。"
    )


def prompt_ai_layer_full_spec_zh():
    """
    贴给 AI 层：修图六大维度 diagnosis + action_plan（可与自然语言混排，JSON 仍须 fenced）。
    核心层会读取 diagnosis 写入摘要，并将 action_plan 转为内部 ops；
    AI 层允许 value 为说明字符串（如「中间调滑块调至1.20」），核心层会尽量推断 unit 与数值。
    """
    return (
        "修图六大维度（与 diagnosis 英文键一一对应，每项含 score 1–10 与 comment 短评）：\n"
        "1. brightness 亮度：照片的「电灯开关」\n"
        "2. contrast 对比度：让照片「黑白分明」\n"
        "3. saturation 饱和度：颜色的「浓淡控制器」\n"
        "4. sharpness 锐度：细节的「放大镜」\n"
        "5. gaussian_blur 高斯模糊\n"
        "6. color_temp 色温：照片的「冷暖开关」\n"
        "\n"
        "推荐 JSON 顶层同时包含 diagnosis 与 action_plan。\n"
        "diagnosis 六键须为：brightness, contrast, saturation, sharpness, "
        "gaussian_blur, color_temp。\n"
        "action_plan 每项含：step, tool, menu_path, action, value, reason；\n"
        "value 可为数字+unit（核心层首选），也可为中文说明字符串（核心层会从文案中提取数字并推断 unit）。\n"
        "曲线步骤若无 points，预览将使用内置温和 S 型曲线。\n"
        "完整解析入口：mentorlib.structured_plan.parse_and_validate_plan。"
    )


def extract_json_plan_from_text(text):
    """
    从混合文本中解析出 plan 的 JSON 对象（dict）。
    优先识别 ```json ... ```，其次整段为 JSON 的对象。
    """
    if text is None:
        raise ValueError("模型返回为空")
    if not isinstance(text, basestring):
        raise ValueError("模型返回须为字符串/Unicode")

    m = re.search(r"```json\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if m:
        chunk = m.group(1).strip()
        return json.loads(chunk)

    m = re.search(r"```\s*([\s\S]*?)```", text)
    if m:
        chunk = m.group(1).strip()
        if chunk.startswith("{"):
            return json.loads(chunk)

    ts = text.strip()
    if ts.startswith("{"):
        return json.loads(ts)

    raise ValueError(
        "未在模型输出中找到 JSON。"
        "请在回复末尾追加 fenced 代码块（三个反引号 + json 标记 + JSON 正文 + 三个反引号）；"
        "或让整段回复仅为合法 JSON 对象。"
        "提示词范本：mentorlib.structured_plan.prompt_json_fence_instruction_zh()"
    )


def parse_and_validate_plan(text):
    """
    extract_json_plan_from_text → 若为 action_plan 格式则先转换 → schema.validate_plan。
    """
    data = extract_json_plan_from_text(text)
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")

    has_standard = (
        isinstance(data.get("summary"), basestring)
        and data.get("summary", "").strip()
        and isinstance(data.get("steps_for_user"), list)
        and len(data.get("steps_for_user") or []) > 0
    )
    if has_standard:
        return schema.validate_plan(data)

    ap = data.get("action_plan")
    has_action_plan = isinstance(ap, list) and len(ap) > 0
    has_diagnosis = isinstance(data.get("diagnosis"), dict) and len(data.get("diagnosis") or {}) > 0

    if has_action_plan:
        internal = action_plan_adapter.action_plan_to_plan(data)
        return schema.validate_plan(internal)

    if has_diagnosis:
        internal = action_plan_adapter.diagnosis_only_to_plan(data)
        return schema.validate_plan(internal)

    raise ValueError(
        "JSON 需包含：非空 action_plan，或六维 diagnosis，或 summary + steps_for_user 标准方案。"
        "参见 mentorlib.structured_plan.prompt_action_plan_format_zh()、"
        "prompt_ai_layer_full_spec_zh()"
    )
