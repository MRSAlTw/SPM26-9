# -*- coding: utf-8 -*-
"""
编辑方案数据结构校验（不依赖 gimpfu，可在普通 Python 中单元测试）。
大模型输出 JSON 后应经 validate_plan；此处为结构与数值范围校验。

GIMP 2.10（用户所称 2.1.0）PDB 对应关系见 mentorlib/pdb_runner.py 注释。
"""

from __future__ import unicode_literals

try:
    basestring  # Python 2
except NameError:
    basestring = str  # Python 3

ALLOWED_OPS = frozenset(
    (
        "brightness_contrast",
        "levels",
        "curves_spline",
        "hue_saturation",
        "color_balance",
        "gaussian_blur",
        "unsharp_mask",
        "desaturate",
        "color_temperature",
        "white_balance_auto",
        "image_crop",
        "image_scale",
        "selection_replace_rectangle",
        "edit_fill",
        "layer_mask_add",
    )
)

_HIST_CHANNELS = frozenset(("value", "red", "green", "blue", "alpha"))
_HUE_RANGES = frozenset(
    ("all", "red", "yellow", "green", "cyan", "blue", "magenta")
)
_DESAT_MODES = frozenset(("lightness", "luminosity", "average"))
_SCALE_INTERP = frozenset(("none", "linear", "cubic", "lohalo", "nohalo"))
_FILL_TYPES = frozenset(("foreground", "background", "pattern"))
_MASK_INIT = frozenset(
    (
        "white",
        "black",
        "alpha",
        "alpha_copy",
        "selection",
        "grayscale_copy",
        "channel",
    )
)


def validate_plan(plan):
    """
    plan: dict，需包含：
      - summary: str，给用户看的方案摘要
      - steps_for_user: list of str，建议用户在自己原图上操作的步骤
      - ops: list of { "op": str, "args": dict }，仅在预览副本上执行
    """
    if not isinstance(plan, dict):
        raise ValueError("plan 必须是 dict")

    summary = plan.get("summary")
    if not isinstance(summary, basestring) or not summary.strip():
        raise ValueError("plan.summary 必须是非空字符串")

    steps = plan.get("steps_for_user")
    if not isinstance(steps, list) or not steps:
        raise ValueError("plan.steps_for_user 必须是非空 list")
    for i, s in enumerate(steps):
        if not isinstance(s, basestring) or not s.strip():
            raise ValueError("plan.steps_for_user[%d] 必须是非空字符串" % i)

    ops = plan.get("ops")
    if ops is None:
        plan["ops"] = []
        ops = plan["ops"]
    if not isinstance(ops, list):
        raise ValueError("plan.ops 必须是 list")

    for i, item in enumerate(ops):
        if not isinstance(item, dict):
            raise ValueError("plan.ops[%d] 必须是 dict" % i)
        op = item.get("op")
        if op not in ALLOWED_OPS:
            raise ValueError("plan.ops[%d].op 不在白名单: %r" % (i, op))
        args = item.get("args")
        if args is None:
            item["args"] = {}
            args = item["args"]
        if not isinstance(args, dict):
            raise ValueError("plan.ops[%d].args 必须是 dict" % i)
        _validate_op_args(op, args, i)

    return plan


def _clamp_int(v, lo, hi, path):
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise ValueError("%s 必须是整数" % path)
    if v < lo or v > hi:
        raise ValueError("%s 超出 [%d,%d]" % (path, lo, hi))
    return v


def _clamp_float(v, lo, hi, path):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s 必须是数字" % path)
    if v < lo or v > hi:
        raise ValueError("%s 超出 [%.4g,%.4g]" % (path, lo, hi))
    return v


def _require_hist_channel(args, index):
    ch = args.get("channel", "value")
    if ch not in _HIST_CHANNELS:
        raise ValueError(
            "plan.ops[%d].channel 必须是 %r 之一"
            % (index, sorted(_HIST_CHANNELS))
        )
    return ch


def _validate_op_args(op, args, index):
    pfx = "plan.ops[%d]" % index

    if op == "brightness_contrast":
        for key in ("brightness", "contrast"):
            if key not in args:
                raise ValueError("%s brightness_contrast 缺少 %s" % (pfx, key))
            _clamp_int(args[key], -100, 100, "%s.%s" % (pfx, key))

    elif op == "levels":
        _require_hist_channel(args, index)
        _clamp_int(args.get("low_input", 0), 0, 255, "%s.low_input" % pfx)
        _clamp_int(args.get("high_input", 255), 0, 255, "%s.high_input" % pfx)
        _clamp_int(args.get("low_output", 0), 0, 255, "%s.low_output" % pfx)
        _clamp_int(args.get("high_output", 255), 0, 255, "%s.high_output" % pfx)
        _clamp_float(args.get("gamma", 1.0), 0.1, 10.0, "%s.gamma" % pfx)
        if args["low_input"] >= args["high_input"]:
            raise ValueError("%s 需满足 low_input < high_input" % pfx)

    elif op == "curves_spline":
        _require_hist_channel(args, index)
        pts = args.get("points")
        if not isinstance(pts, list) or len(pts) < 3:
            raise ValueError("%s curves_spline.points 至少 3 个 [x,y] 控制点" % pfx)
        if len(pts) > 18:
            raise ValueError("%s curves_spline.points 至多 18 个控制点" % pfx)
        for j, pair in enumerate(pts):
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
            ):
                raise ValueError("%s curves_spline.points[%d] 须为 [x,y]" % (pfx, j))
            _clamp_int(pair[0], 0, 255, "%s.points[%d][0]" % (pfx, j))
            _clamp_int(pair[1], 0, 255, "%s.points[%d][1]" % (pfx, j))

    elif op == "hue_saturation":
        hr = args.get("hue_range", "all")
        if hr not in _HUE_RANGES:
            raise ValueError(
                "%s hue_saturation.hue_range 须为 %r 之一"
                % (pfx, sorted(_HUE_RANGES))
            )
        _clamp_float(args.get("hue", 0.0), -180.0, 180.0, "%s.hue" % pfx)
        _clamp_float(args.get("lightness", 0.0), -100.0, 100.0, "%s.lightness" % pfx)
        _clamp_float(args.get("saturation", 0.0), -100.0, 100.0, "%s.saturation" % pfx)

    elif op == "color_balance":
        if "preserve_luminosity" not in args:
            raise ValueError("%s color_balance 缺少 preserve_luminosity" % pfx)
        if not isinstance(args["preserve_luminosity"], bool):
            raise ValueError("%s color_balance.preserve_luminosity 须为 bool" % pfx)
        zones = ("shadows", "midtones", "highlights")
        found = False
        for z in zones:
            if z not in args:
                continue
            found = True
            zd = args[z]
            if not isinstance(zd, dict):
                raise ValueError("%s color_balance.%s 须为 dict" % (pfx, z))
            for comp in ("cyan_red", "magenta_green", "yellow_blue"):
                if comp not in zd:
                    raise ValueError(
                        "%s color_balance.%s 缺少 %s" % (pfx, z, comp)
                    )
                _clamp_float(zd[comp], -100.0, 100.0, "%s.%s.%s" % (pfx, z, comp))
        if not found:
            raise ValueError(
                "%s color_balance 至少提供 shadows / midtones / highlights 之一"
                % pfx
            )

    elif op == "gaussian_blur":
        h = args.get("horizontal", 1.0)
        v = args.get("vertical", h)
        try:
            h = float(h)
            v = float(v)
        except (TypeError, ValueError):
            raise ValueError("%s gaussian_blur 半径必须是数字" % pfx)
        if h <= 0 or v <= 0:
            raise ValueError("%s gaussian_blur 半径必须 > 0" % pfx)
        if h > 200 or v > 200:
            raise ValueError("%s gaussian_blur 半径过大（>200）" % pfx)
        method = int(args.get("method", 0))
        if method not in (0, 1):
            raise ValueError("%s gaussian_blur.method 只能是 0 或 1" % pfx)

    elif op == "unsharp_mask":
        _clamp_float(args.get("radius", 1.0), 0.1, 120.0, "%s.radius" % pfx)
        _clamp_float(args.get("amount", 0.5), 0.0, 10.0, "%s.amount" % pfx)
        _clamp_int(args.get("threshold", 0), 0, 255, "%s.threshold" % pfx)

    elif op == "desaturate":
        m = args.get("mode", "lightness")
        if m not in _DESAT_MODES:
            raise ValueError(
                "%s desaturate.mode 须为 %r 之一" % (pfx, sorted(_DESAT_MODES))
            )

    elif op == "color_temperature":
        # 无稳定 PDB 时用 color_balance 近似，见 pdb_runner
        _clamp_float(args.get("warmth", 0.0), -100.0, 100.0, "%s.warmth" % pfx)

    elif op == "white_balance_auto":
        # 无参数；实际为 HSV 拉伸或色阶自动（见 pdb_runner）
        pass

    elif op == "image_crop":
        _clamp_int(args.get("width", 1), 1, 100000, "%s.width" % pfx)
        _clamp_int(args.get("height", 1), 1, 100000, "%s.height" % pfx)
        _clamp_int(args.get("offset_x", 0), 0, 100000, "%s.offset_x" % pfx)
        _clamp_int(args.get("offset_y", 0), 0, 100000, "%s.offset_y" % pfx)

    elif op == "image_scale":
        _clamp_int(args.get("width", 1), 1, 100000, "%s.width" % pfx)
        _clamp_int(args.get("height", 1), 1, 100000, "%s.height" % pfx)
        ip = args.get("interpolation", "cubic")
        if ip not in _SCALE_INTERP:
            raise ValueError(
                "%s image_scale.interpolation 须为 %r 之一"
                % (pfx, sorted(_SCALE_INTERP))
            )

    elif op == "selection_replace_rectangle":
        _clamp_int(args.get("x", 0), 0, 100000, "%s.x" % pfx)
        _clamp_int(args.get("y", 0), 0, 100000, "%s.y" % pfx)
        _clamp_int(args.get("width", 1), 1, 100000, "%s.width" % pfx)
        _clamp_int(args.get("height", 1), 1, 100000, "%s.height" % pfx)

    elif op == "edit_fill":
        ft = args.get("fill_type", "foreground")
        if ft not in _FILL_TYPES:
            raise ValueError(
                "%s edit_fill.fill_type 须为 %r 之一" % (pfx, sorted(_FILL_TYPES))
            )

    elif op == "layer_mask_add":
        mi = args.get("init", "white")
        if mi not in _MASK_INIT:
            raise ValueError(
                "%s layer_mask_add.init 须为 %r 之一" % (pfx, sorted(_MASK_INIT))
            )

    else:
        raise ValueError("%s 未知 op: %r" % (pfx, op))
