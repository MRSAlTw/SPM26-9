#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 修图助手 — 入口脚本（GIMP 加载本文件）。

核心逻辑在包 mentorlib/（避免与本目录下多个 .py 一同被当作独立插件扫描）。
"""
from __future__ import unicode_literals

import os
import sys

_plug_dir = os.path.dirname(os.path.abspath(__file__))
if _plug_dir not in sys.path:
    sys.path.insert(0, _plug_dir)

from gimpfu import *

from mentorlib.preview import run_preview_in_new_window_safe


def ai_mentor_main(image, drawable):
    """生成预览副本并打开独立图像窗口，同时弹出文字版修图方案。"""
    run_preview_in_new_window_safe(image, drawable)


register(
    "python-fu-ai-mentor-preview",
    "AI Mentor",
    "修图引导：方案 + 预览副本（新窗口），不直接修改当前图像。",
    "Team成都",
    "Team成都",
    "2026",
    "AI修图助手（预览方案）...",
    "*",
    [
        (PF_IMAGE, "image", "输入图像", None),
        (PF_DRAWABLE, "drawable", "输入图层", None),
    ],
    [],
    ai_mentor_main,
    menu="<Image>/Filters",
)

main()
