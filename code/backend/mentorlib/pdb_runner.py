# -*- coding: utf-8 -*-
"""
白名单 PDB 调度：与 schema.py 中的 op 一一对应，映射到 GIMP 2.10 原生 PDB。

枚举值使用与 libgimp 2.10 一致的整数，避免不同发行版 gimpfu 常量命名差异导致 ImportError。

色温 / 白平衡：
- color_temperature：以 gimp_color_balance（中调）近似冷暖（warmth -100..100）。
- white_balance_auto：优先 plug_in_autostretch_hsv，失败则 gimp_levels_stretch。

图层蒙版：layer_mask_add = create_mask + add_mask；已有蒙版时先 MASK_DISCARD 移除。
"""

from __future__ import unicode_literals

import array

from gimpfu import *


# GimpHistogramChannel
_HIST_CHANNEL_MAP = {"value": 0, "red": 1, "green": 2, "blue": 3, "alpha": 4}

# GimpHueRange
_HUE_RANGE_MAP = {
    "all": 0,
    "red": 1,
    "yellow": 2,
    "green": 3,
    "cyan": 4,
    "blue": 5,
    "magenta": 6,
}

# GimpDesaturateMode
_DESAT_MODE_MAP = {"lightness": 0, "luminosity": 1, "average": 2}

# GimpInterpolationType（GIMP 2.10）
_INTERP_MAP = {"none": 0, "linear": 1, "cubic": 2, "lohalo": 3, "nohalo": 4}

# GimpFillType（gimp_edit_fill）
_FILL_MAP = {"foreground": 0, "background": 1, "pattern": 2}

# GimpAddMaskType
_MASK_INIT_MAP = {
    "white": 0,
    "black": 1,
    "alpha": 2,
    "alpha_copy": 3,
    "selection": 4,
    "grayscale_copy": 5,
    "channel": 6,
}

# GimpTransferMode（color_balance）
_TRANSFER_INT = {"shadows": 0, "midtones": 1, "highlights": 2}

# GimpMaskApplyMode：丢弃旧蒙版
_MASK_DISCARD = 1

# GimpChannelOps
_CHANNEL_OP_REPLACE = 0


def _layer_from_drawable(drawable):
    if not pdb.gimp_drawable_is_layer(drawable):
        raise ValueError("该操作需要图层类型的 drawable（当前不是图层）")
    return drawable


def _curves_bytes(points_pairs):
    flat = []
    for x, y in points_pairs:
        flat.append(int(x) & 0xFF)
        flat.append(int(y) & 0xFF)
    buf = array.array("B", flat)
    if hasattr(buf, "tobytes"):
        return buf.tobytes()
    return buf.tostring()


def apply_op(image, drawable, op, args):
    if args is None:
        args = {}

    if op == "brightness_contrast":
        b = max(-100, min(100, int(args.get("brightness", 0))))
        c = max(-100, min(100, int(args.get("contrast", 0))))
        pdb.gimp_brightness_contrast(drawable, b, c)

    elif op == "levels":
        ch = _HIST_CHANNEL_MAP[args.get("channel", "value")]
        li = int(args.get("low_input", 0))
        hi = int(args.get("high_input", 255))
        lo = int(args.get("low_output", 0))
        ho = int(args.get("high_output", 255))
        # GIMP 2.10 pdb.gimp_levels 顺序为：low_input, high_input, gamma, low_output, high_output
        # （若把 low_output 放在 gamma 前，会把 0 当成 gamma 触发「超出范围」）
        gamma = max(0.01, min(10.0, float(args.get("gamma", 1.0))))
        pdb.gimp_levels(drawable, ch, li, hi, gamma, lo, ho)

    elif op == "curves_spline":
        ch = _HIST_CHANNEL_MAP[args.get("channel", "value")]
        raw = _curves_bytes(args["points"])
        pdb.gimp_curves_spline(drawable, ch, len(raw), raw)

    elif op == "hue_saturation":
        hr = _HUE_RANGE_MAP[args.get("hue_range", "all")]
        hue = float(args.get("hue", 0.0))
        light = float(args.get("lightness", 0.0))
        sat = float(args.get("saturation", 0.0))
        pdb.gimp_hue_saturation(drawable, hr, hue, light, sat)

    elif op == "color_balance":
        preserve = bool(args.get("preserve_luminosity", True))
        for zone in ("shadows", "midtones", "highlights"):
            if zone not in args:
                continue
            zd = args[zone]
            cr = float(zd["cyan_red"])
            mg = float(zd["magenta_green"])
            yb = float(zd["yellow_blue"])
            transfer = _TRANSFER_INT[zone]
            pdb.gimp_color_balance(drawable, transfer, preserve, cr, mg, yb)

    elif op == "gaussian_blur":
        h = max(0.1, min(200.0, float(args.get("horizontal", 1.0))))
        v = max(0.1, min(200.0, float(args.get("vertical", h))))
        method = int(args.get("method", 0))
        if method not in (0, 1):
            method = 0
        pdb.plug_in_gauss(image, drawable, h, v, method)

    elif op == "unsharp_mask":
        radius = max(0.1, min(120.0, float(args.get("radius", 1.0))))
        amount = max(0.0, min(10.0, float(args.get("amount", 0.5))))
        threshold = max(0, min(255, int(args.get("threshold", 0))))
        pdb.plug_in_unsharp_mask(image, drawable, radius, amount, threshold)

    elif op == "desaturate":
        mode = _DESAT_MODE_MAP[args.get("mode", "lightness")]
        pdb.gimp_desaturate_full(drawable, mode)

    elif op == "color_temperature":
        warmth = max(-100.0, min(100.0, float(args.get("warmth", 0.0))))
        cr = max(-100.0, min(100.0, warmth * 0.55))
        yb = max(-100.0, min(100.0, warmth * 0.40))
        mg = max(-100.0, min(100.0, -warmth * 0.12))
        pdb.gimp_color_balance(drawable, _TRANSFER_INT["midtones"], True, cr, mg, yb)

    elif op == "white_balance_auto":
        done = False
        if hasattr(pdb, "plug_in_autostretch_hsv"):
            try:
                pdb.plug_in_autostretch_hsv(image, drawable)
                done = True
            except Exception:
                done = False
        if not done:
            pdb.gimp_levels_stretch(drawable)

    elif op == "image_crop":
        w = int(args["width"])
        h = int(args["height"])
        ox = int(args.get("offset_x", 0))
        oy = int(args.get("offset_y", 0))
        pdb.gimp_image_crop(image, w, h, ox, oy)

    elif op == "image_scale":
        w = int(args["width"])
        h = int(args["height"])
        interp = _INTERP_MAP[args.get("interpolation", "cubic")]
        pdb.gimp_image_scale_full(image, w, h, interp)

    elif op == "selection_replace_rectangle":
        x = int(args["x"])
        y = int(args["y"])
        w = int(args["width"])
        h = int(args["height"])
        pdb.gimp_image_select_rectangle(
            image, _CHANNEL_OP_REPLACE, x, y, w, h
        )

    elif op == "edit_fill":
        ft = _FILL_MAP[args.get("fill_type", "foreground")]
        pdb.gimp_edit_fill(drawable, ft)

    elif op == "layer_mask_add":
        layer = _layer_from_drawable(drawable)
        mask_type = _MASK_INIT_MAP[args.get("init", "white")]
        old = pdb.gimp_layer_get_mask(layer)
        if old is not None and pdb.gimp_item_is_valid(old):
            pdb.gimp_layer_remove_mask(layer, _MASK_DISCARD)
        mask = pdb.gimp_layer_create_mask(layer, mask_type)
        pdb.gimp_layer_add_mask(layer, mask)

    else:
        raise ValueError("未知 op: %r" % (op,))


def apply_ops_sequence(image, drawable, ops):
    for spec in ops:
        op = spec.get("op")
        apply_op(image, drawable, op, spec.get("args"))
