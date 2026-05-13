# -*- coding: utf-8 -*-
"""
将 AI 接口返回的「action_plan」JSON（中文 tool / menu_path 等），
及可选「diagnosis」六维评分（亮度/对比度/饱和度/锐度/高斯模糊/色温，见 _DIAGNOSIS_KEYS），

  { "summary", "steps_for_user", "ops" }

ops[].op 为英文白名单标识，与 pdb_runner 一致。

扩展约定：单步 dict 除示例字段外，可附加与 schema 对齐的字段名
（如 image_crop 的 offset_x）；若某步无法映射则跳过该步的 ops，仍保留用户步骤文案。
"""

from __future__ import unicode_literals

import re

try:
    basestring
except NameError:
    basestring = str

# AI 层「曲线」步骤常只给自然语言 value；无 points 时用温和 S 型供预览（可执行）。
_DEFAULT_CURVE_S_POINTS = [[0, 10], [96, 82], [160, 173], [255, 245]]

_NUM_TOKEN_RE = re.compile(r"[\d.]+")

# 与「修图六大维度」diagnosis 键一致（顺序用于展示；文案与 AI 层提示词对齐）
_DIAGNOSIS_KEYS = (
    ("brightness", u"亮度（照片的「电灯开关」）"),
    ("contrast", u"对比度（让照片「黑白分明」）"),
    ("saturation", u"饱和度（颜色的「浓淡控制器」）"),
    ("sharpness", u"锐度（细节的「放大镜」）"),
    ("gaussian_blur", u"高斯模糊"),
    ("color_temp", u"色温（照片的「冷暖开关」）"),
)


def _s(x):
    if x is None:
        return u""
    if isinstance(x, basestring):
        return x.strip()
    try:
        uconv = unicode  # Python 2
    except NameError:
        uconv = str  # Python 3
    return uconv(x).strip()


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _i(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def _extract_floats_from_text(text):
    """从中文说明里抽出数字片段（含小数）。"""
    if not text:
        return []
    out = []
    for t in _NUM_TOKEN_RE.findall(text):
        if t.count(".") > 1:
            continue
        try:
            out.append(float(t))
        except ValueError:
            continue
    return out


def _pick_gamma_candidate(nums):
    for x in nums:
        if 0.05 <= x <= 10.0:
            return x
    return None


def _normalize_string_value_for_tool(step, tool_c):
    """
    将 AI 层 action 里常见的「自然语言 + 数字」value 转为核心层 numeric value + unit，
    或补充曲线 points。不改变已存在的合法 numeric value / 已有 unit+points。
    """
    out = dict(step)
    val_raw = out.get("value")
    if not isinstance(val_raw, basestring):
        return out
    val_s = _s(val_raw)
    act_s = _s(out.get("action"))
    menu_s = _s(out.get("menu_path"))
    blob = u" ".join([val_s, act_s, menu_s])
    nums = _extract_floats_from_text(blob)
    unit_existing = _norm_unit(out.get("unit"))

    if tool_c == u"曲线":
        if not out.get("points"):
            out["points"] = [list(p) for p in _DEFAULT_CURVE_S_POINTS]
        return out

    if tool_c == u"色阶":
        if unit_existing:
            try:
                out["value"] = float(val_raw) if val_s else out.get("value")
            except (TypeError, ValueError):
                out["value"] = _pick_gamma_candidate(nums) or 1.0
            return out
        if u"中间调" in blob or u"伽马" in blob or "gamma" in blob.lower():
            g = _pick_gamma_candidate(nums)
            if g is not None:
                out["value"] = g
                out["unit"] = "gamma"
            return out
        if u"黑场" in blob or "low_input" in blob.lower():
            if nums:
                out["value"] = int(max(0, min(255, round(nums[0]))))
                out["unit"] = "low_input"
            return out
        if u"白场" in blob or "high_input" in blob.lower():
            if nums:
                out["value"] = int(max(0, min(255, round(nums[0]))))
                out["unit"] = "high_input"
            return out
        if u"输出" in blob and u"黑" in blob:
            if nums:
                out["value"] = int(max(0, min(255, round(nums[0]))))
                out["unit"] = "low_output"
            return out
        if u"输出" in blob and u"白" in blob:
            if nums:
                out["value"] = int(max(0, min(255, round(nums[0]))))
                out["unit"] = "high_output"
            return out
        g = _pick_gamma_candidate(nums)
        if g is not None and 0.2 <= g <= 5.0:
            out["value"] = g
            out["unit"] = "gamma"
        return out

    if tool_c == u"高斯模糊":
        if nums:
            out["value"] = max(0.1, min(200.0, nums[0]))
        if not out.get("unit"):
            out["unit"] = "pixels"
        return out

    if tool_c == u"亮度对比度":
        v = int(round(nums[0])) if nums else 0
        v = max(-100, min(100, v))
        out["value"] = v
        if not out.get("unit"):
            if u"亮度" in blob or "brightness" in blob.lower():
                out["unit"] = "brightness"
            elif u"对比度" in blob or "contrast" in blob.lower():
                out["unit"] = "contrast"
            else:
                out["unit"] = "contrast"
        return out

    if tool_c == u"色相饱和度":
        v = nums[0] if nums else 0.0
        v = max(-100.0, min(100.0, float(v)))
        out["value"] = v
        if not out.get("unit"):
            if u"饱和" in blob or "saturation" in blob.lower():
                out["unit"] = "saturation"
            elif u"色相" in blob or "hue" in blob.lower():
                out["unit"] = "hue"
            elif u"明度" in blob or u"亮度" in blob:
                out["unit"] = "lightness"
            else:
                out["unit"] = "saturation"
        return out

    if tool_c == u"usm":
        if nums:
            if u"半径" in blob or u"像素" in blob or "pixel" in blob.lower():
                out["value"] = max(0.1, min(120.0, nums[0]))
                out["unit"] = "radius"
            elif u"数量" in blob or u"强度" in blob or "amount" in blob.lower():
                out["value"] = max(0.0, min(10.0, nums[0]))
                out["unit"] = "amount"
            elif u"阈值" in blob or "threshold" in blob.lower():
                out["value"] = max(0, min(255, int(round(nums[0]))))
                out["unit"] = "threshold"
            else:
                out["value"] = max(0.1, min(120.0, nums[0]))
                out["unit"] = "radius"
        return out

    if tool_c == u"色温":
        if nums:
            out["value"] = max(-100.0, min(100.0, nums[0]))
        return out

    return out


def normalize_action_plan_step(step):
    """单步：曲线补 points；字符串 value 按工具推断 unit / 数值。"""
    if not isinstance(step, dict):
        return step
    tool_c = _canonical_tool_name(step.get("tool"))
    out = dict(step)
    if tool_c == u"曲线" and not out.get("points"):
        out["points"] = [list(p) for p in _DEFAULT_CURVE_S_POINTS]
    val = out.get("value")
    if isinstance(val, basestring) and _s(val):
        out = _normalize_string_value_for_tool(out, tool_c)
    return out


def _format_diagnosis_lines(diagnosis):
    if not isinstance(diagnosis, dict):
        return []
    lines = [u"【修图六大维度诊断】"]
    for key, label in _DIAGNOSIS_KEYS:
        block = diagnosis.get(key)
        if not isinstance(block, dict):
            continue
        score = block.get("score")
        comment = _s(block.get("comment"))
        if score is None and not comment:
            continue
        if score is not None:
            lines.append(u"%s（%s 分）：%s" % (label, score, comment or u"—"))
        else:
            lines.append(u"%s：%s" % (label, comment or u"—"))
    return lines


def diagnosis_only_to_plan(api_data):
    """
    仅含 diagnosis、无可用 action_plan 时：生成可校验 plan（ops 为空，步骤来自诊断文案）。
    """
    diagnosis = api_data.get("diagnosis")
    lines = _format_diagnosis_lines(diagnosis)
    steps = []
    if isinstance(diagnosis, dict):
        for key, label in _DIAGNOSIS_KEYS:
            block = diagnosis.get(key)
            if not isinstance(block, dict):
                continue
            comment = _s(block.get("comment"))
            score = block.get("score")
            if not comment and score is None:
                continue
            if score is not None:
                steps.append(u"%s（%s 分）：%s" % (label, score, comment or u""))
            else:
                steps.append(u"%s：%s" % (label, comment or u""))
    summary = u"\n".join(lines) if lines else u"（模型未返回可执行步骤，仅诊断信息）"
    if not steps:
        steps = [u"请根据上述诊断在原图上手动调整；或让模型补充 action_plan（含 unit/value）。"]
    return {
        "summary": summary,
        "steps_for_user": steps,
        "ops": [],
    }


def _format_user_line(step):
    n = _i(step.get("step"), 0)
    menu = _s(step.get("menu_path"))
    act = _s(step.get("action"))
    rsn = _s(step.get("reason"))
    parts = []
    if n:
        parts.append(u"步骤%d" % n)
    if menu:
        parts.append(menu)
    if act:
        parts.append(act)
    if rsn:
        parts.append(u"（%s）" % rsn)
    return u"：".join(parts) if parts else u"（空步骤）"


def _norm_unit(u):
    return _s(u).lower().replace(u" ", u"")


def _step_levels(step):
    u = _norm_unit(step.get("unit"))
    val = step.get("value", 1.0)
    args = {
        "channel": _s(step.get("channel")) or "value",
        "low_input": _i(step.get("low_input"), 0),
        "high_input": _i(step.get("high_input"), 255),
        "low_output": _i(step.get("low_output"), 0),
        "high_output": _i(step.get("high_output"), 255),
        "gamma": _f(step.get("gamma"), 1.0),
    }
    if u in ("gamma", u"伽马", u"中间调", u"g"):
        args["gamma"] = max(0.01, min(10.0, _f(val, 1.0)))
    elif u in ("low_input", "输入黑场", "黑场"):
        args["low_input"] = max(0, min(255, _i(val, 0)))
    elif u in ("high_input", "输入白场", "白场"):
        args["high_input"] = max(0, min(255, _i(val, 255)))
    elif u in ("low_output", "输出黑场"):
        args["low_output"] = max(0, min(255, _i(val, 0)))
    elif u in ("high_output", "输出白场"):
        args["high_output"] = max(0, min(255, _i(val, 255)))
    else:
        args["gamma"] = max(0.01, min(10.0, _f(val, 1.0)))
    if args["channel"] not in ("value", "red", "green", "blue", "alpha"):
        args["channel"] = "value"
    return [{"op": "levels", "args": args}]


def _step_gaussian_blur(step):
    r = max(0.1, min(200.0, _f(step.get("value"), 1.0)))
    method = _i(step.get("method"), 0)
    if method not in (0, 1):
        method = 0
    return [{"op": "gaussian_blur", "args": {"horizontal": r, "vertical": r, "method": method}}]


def _step_brightness_contrast(step):
    u = _norm_unit(step.get("unit"))
    v = _i(step.get("value"), 0)
    v = max(-100, min(100, v))
    b, c = 0, 0
    if u in ("brightness", u"亮度", u"b"):
        b = v
    elif u in ("contrast", u"对比度", u"c"):
        c = v
    else:
        c = v
    return [{"op": "brightness_contrast", "args": {"brightness": b, "contrast": c}}]


def _step_hue_saturation(step):
    u = _norm_unit(step.get("unit"))
    v = _f(step.get("value"), 0.0)
    args = {
        "hue_range": _s(step.get("hue_range")) or "all",
        "hue": _f(step.get("hue"), 0.0),
        "lightness": _f(step.get("lightness"), 0.0),
        "saturation": _f(step.get("saturation"), 0.0),
    }
    if u in ("saturation", u"饱和度", u"s"):
        args["saturation"] = max(-100.0, min(100.0, v))
    elif u in ("hue", u"色相", u"h"):
        args["hue"] = max(-180.0, min(180.0, v))
    elif u in ("lightness", u"明度", u"亮度2", u"l"):
        args["lightness"] = max(-100.0, min(100.0, v))
    else:
        args["saturation"] = max(-100.0, min(100.0, v))
    return [{"op": "hue_saturation", "args": args}]


def _step_unsharp_mask(step):
    u = _norm_unit(step.get("unit"))
    val = _f(step.get("value"), 1.0)
    radius = max(0.1, min(120.0, _f(step.get("radius"), 1.2)))
    amount = max(0.0, min(10.0, _f(step.get("amount"), 0.5)))
    threshold = max(0, min(255, _i(step.get("threshold"), 0)))
    if u in ("radius", u"半径", u"pixels", u"pixel", u"px"):
        radius = max(0.1, min(120.0, val))
    elif u in ("amount", u"数量", u"强度", u"a"):
        amount = max(0.0, min(10.0, val))
    elif u in ("threshold", u"阈值", u"t"):
        threshold = max(0, min(255, int(val)))
    act = _s(step.get("action"))
    if u in ("pixels", u"pixel", u"px") or u"半径" in act:
        radius = max(0.1, min(120.0, val))
    return [
        {
            "op": "unsharp_mask",
            "args": {
                "radius": radius,
                "amount": amount,
                "threshold": threshold,
            },
        }
    ]


def _step_desaturate(step):
    mode = _s(step.get("mode")) or "lightness"
    if mode not in ("lightness", "luminosity", "average"):
        mode = "lightness"
    return [{"op": "desaturate", "args": {"mode": mode}}]


def _step_color_temperature(step):
    w = max(-100.0, min(100.0, _f(step.get("value"), _f(step.get("warmth"), 0.0))))
    return [{"op": "color_temperature", "args": {"warmth": w}}]


def _step_white_balance_auto(step):
    return [{"op": "white_balance_auto", "args": {}}]


def _step_image_crop(step):
    w = _i(step.get("width"), _i(step.get("value"), 0))
    h = _i(step.get("height"), w)
    ox = _i(step.get("offset_x"), 0)
    oy = _i(step.get("offset_y"), 0)
    if w <= 0 or h <= 0:
        return []
    return [{"op": "image_crop", "args": {"width": w, "height": h, "offset_x": ox, "offset_y": oy}}]


def _step_image_scale(step):
    w = _i(step.get("width"), _i(step.get("value"), 0))
    h = _i(step.get("height"), w)
    if w <= 0 or h <= 0:
        return []
    ip = _s(step.get("interpolation")) or "cubic"
    if ip not in ("none", "linear", "cubic", "lohalo", "nohalo"):
        ip = "cubic"
    return [{"op": "image_scale", "args": {"width": w, "height": h, "interpolation": ip}}]


def _step_selection_rectangle(step):
    x = _i(step.get("x"), _i(step.get("offset_x"), 0))
    y = _i(step.get("y"), _i(step.get("offset_y"), 0))
    w = _i(step.get("width"), 0)
    h = _i(step.get("height"), 0)
    if w <= 0 or h <= 0:
        return []
    return [
        {
            "op": "selection_replace_rectangle",
            "args": {"x": x, "y": y, "width": w, "height": h},
        }
    ]


def _step_edit_fill(step):
    ft = _s(step.get("fill_type")) or "foreground"
    if ft not in ("foreground", "background", "pattern"):
        ft = "foreground"
    return [{"op": "edit_fill", "args": {"fill_type": ft}}]


def _step_layer_mask_add(step):
    init = _s(step.get("init")) or "white"
    if init not in (
        "white",
        "black",
        "alpha",
        "alpha_copy",
        "selection",
        "grayscale_copy",
        "channel",
    ):
        init = "white"
    return [{"op": "layer_mask_add", "args": {"init": init}}]


def _step_color_balance(step):
    preserve = bool(step.get("preserve_luminosity", True))
    args = {"preserve_luminosity": preserve}
    for zone in ("shadows", "midtones", "highlights"):
        if zone not in step:
            continue
        zd = step[zone]
        if not isinstance(zd, dict):
            continue
        args[zone] = {
            "cyan_red": _f(zd.get("cyan_red"), 0.0),
            "magenta_green": _f(zd.get("magenta_green"), 0.0),
            "yellow_blue": _f(zd.get("yellow_blue"), 0.0),
        }
    if len(args) > 1:
        return [{"op": "color_balance", "args": args}]
    args["midtones"] = {
        "cyan_red": _f(step.get("cyan_red"), 0.0),
        "magenta_green": _f(step.get("magenta_green"), 0.0),
        "yellow_blue": _f(step.get("yellow_blue"), 0.0),
    }
    return [{"op": "color_balance", "args": args}]


def _step_curves_spline(step):
    pts = step.get("points")
    if not isinstance(pts, list) or len(pts) < 3:
        return []
    ch = _s(step.get("channel")) or "value"
    if ch not in ("value", "red", "green", "blue", "alpha"):
        ch = "value"
    return [{"op": "curves_spline", "args": {"channel": ch, "points": pts}}]


_TOOL_CANONICAL = {
    u"色阶": u"色阶",
    u"levels": u"色阶",
    u"高斯模糊": u"高斯模糊",
    u"gaussian_blur": u"高斯模糊",
    u"高斯": u"高斯模糊",
    u"亮度": u"亮度对比度",
    u"对比度": u"亮度对比度",
    u"亮度对比度": u"亮度对比度",
    u"亮度-对比度": u"亮度对比度",
    u"brightness": u"亮度对比度",
    u"色相": u"色相饱和度",
    u"饱和度": u"色相饱和度",
    u"色相饱和度": u"色相饱和度",
    u"色相/饱和度": u"色相饱和度",
    u"色彩平衡": u"色彩平衡",
    u"曲线": u"曲线",
    u"curves": u"曲线",
    u"锐化": u"usm",
    u"usm": u"usm",
    u"钝化蒙版": u"usm",
    u"非锐化掩模": u"usm",
    u"unsharp": u"usm",
    u"去色": u"去色",
    u"黑白": u"去色",
    u"灰度": u"去色",
    u"desaturate": u"去色",
    u"色温": u"色温",
    u"白平衡": u"白平衡",
    u"裁剪": u"裁剪",
    u"图像裁剪": u"裁剪",
    u"缩放": u"缩放",
    u"图像缩放": u"缩放",
    u"选区": u"矩形选区",
    u"矩形选区": u"矩形选区",
    u"填充": u"填充",
    u"区域填充": u"填充",
    u"图层蒙版": u"图层蒙版",
    u"蒙版": u"图层蒙版",
}


def _canonical_tool_name(tool_raw):
    t = _s(tool_raw)
    if not t:
        return u""
    return _TOOL_CANONICAL.get(t, t)


def _step_to_ops(step):
    if not isinstance(step, dict):
        return []
    canon = _canonical_tool_name(step.get("tool"))
    if canon == u"色阶":
        return _step_levels(step)
    if canon == u"高斯模糊":
        return _step_gaussian_blur(step)
    if canon == u"亮度对比度":
        return _step_brightness_contrast(step)
    if canon == u"色相饱和度":
        return _step_hue_saturation(step)
    if canon == u"色彩平衡":
        return _step_color_balance(step)
    if canon == u"曲线":
        return _step_curves_spline(step)
    if canon == u"usm":
        return _step_unsharp_mask(step)
    if canon == u"去色":
        return _step_desaturate(step)
    if canon == u"色温":
        return _step_color_temperature(step)
    if canon == u"白平衡":
        return _step_white_balance_auto(step)
    if canon == u"裁剪":
        return _step_image_crop(step)
    if canon == u"缩放":
        return _step_image_scale(step)
    if canon == u"矩形选区":
        return _step_selection_rectangle(step)
    if canon == u"填充":
        return _step_edit_fill(step)
    if canon == u"图层蒙版":
        return _step_layer_mask_add(step)
    return []


def action_plan_to_plan(api_data):
    """
    api_data: 含 action_plan 数组的 dict。
    可同含 AI 层 diagnosis（六维评分）；字符串型 value 会先规范化为核心层数值 + unit。
    返回内部 plan dict（尚未经 schema.validate_plan）。
    """
    steps = api_data.get("action_plan")
    if not isinstance(steps, list):
        raise ValueError("action_plan 必须是数组")
    ordered = sorted(
        [s for s in steps if isinstance(s, dict)],
        key=lambda s: _i(s.get("step"), 9999),
    )
    steps_for_user = [_format_user_line(s) for s in ordered]
    ops = []
    skipped_tools = []
    for s in ordered:
        sn = normalize_action_plan_step(s)
        chunk = _step_to_ops(sn)
        if not chunk:
            tn = _s(s.get("tool"))
            if tn:
                skipped_tools.append(tn)
        ops.extend(chunk)
    summary_parts = []
    dx_lines = _format_diagnosis_lines(api_data.get("diagnosis"))
    if dx_lines:
        summary_parts.extend(dx_lines)
        summary_parts.append(u"")
    summary_parts.append(
        u"根据接口返回的 action_plan 共 %d 步，已生成 %d 条预览指令。"
        % (len(ordered), len(ops))
    )
    if skipped_tools:
        summary_parts.append(
            u"以下工具名未能映射为自动预览（仍保留在操作步骤中）："
            + u"、".join(skipped_tools)
        )
    return {
        "summary": u"\n".join(summary_parts),
        "steps_for_user": steps_for_user if steps_for_user else [u"（无步骤）"],
        "ops": ops,
    }
