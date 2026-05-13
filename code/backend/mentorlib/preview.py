# -*- coding: utf-8 -*-
"""
核心流程：获取方案 → 复制整幅图像 → 在副本上应用白名单 PDB → 新建独立预览窗口。

不修改用户当前图像；用户满意后按方案在原图上自行操作。
"""

from __future__ import unicode_literals

from gimpfu import *

from mentorlib import llm_stub as llm
from mentorlib import pdb_runner as runner
from mentorlib import schema


def _format_message(plan):
    lines = []
    lines.append("========== 修图方案（请对照预览窗口阅读）==========")
    lines.append("")
    lines.append(plan.get("summary", "").strip())
    lines.append("")
    lines.append("---------- 建议您在原图上的操作顺序 ----------")
    for i, step in enumerate(plan.get("steps_for_user", []), 1):
        lines.append("%d. %s" % (i, step.strip()))
    lines.append("")
    lines.append("预览已在新图像窗口中打开；关闭该窗口即可丢弃预览副本。")
    return "\n".join(lines)


def run_preview_in_new_window(image, drawable):
    """
    1) 向（未来的）大模型请求方案；2) 复制 image；3) 在副本上执行 ops；
    4) gimp_display_new 打开单独预览窗口；5) gimp_message 展示文字方案。

    返回 (preview_image, display_id, plan_dict)
    """
    plan = llm.request_preview_plan(image, drawable)
    schema.validate_plan(plan)

    preview_image = pdb.gimp_image_duplicate(image)
    if preview_image is None:
        raise RuntimeError("无法复制图像（gimp_image_duplicate 失败）")

    preview_drawable = pdb.gimp_image_get_active_drawable(preview_image)
    if preview_drawable is None:
        raise RuntimeError("预览图像没有活动图层，无法应用效果")

    pdb.gimp_image_undo_group_start(preview_image)
    try:
        runner.apply_ops_sequence(
            preview_image, preview_drawable, plan.get("ops", [])
        )
    finally:
        pdb.gimp_image_undo_group_end(preview_image)

    display_id = pdb.gimp_display_new(preview_image)
    pdb.gimp_message(_format_message(plan))

    return preview_image, display_id, plan


def run_preview_in_new_window_safe(image, drawable):
    """包装异常为 gimp_message，供菜单入口调用（不再向外抛错，避免重复报错）。"""
    try:
        return run_preview_in_new_window(image, drawable)
    except Exception as e:
        pdb.gimp_message("AI 修图助手（预览）出错：\n%s" % e)
        return None
