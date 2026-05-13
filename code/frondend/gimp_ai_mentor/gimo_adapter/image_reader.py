"""图像读取接口 (SRS-3021)。

将 GIMP 当前活动图像导出为 Base64 + 元数据。
独立模式下返回内置占位图，便于 UI 联调。
"""

from __future__ import annotations

import base64
import os
import tempfile
from typing import Any, Dict, Optional

from ..config import write_log
from ..constants import ERR_MEMORY_INSUFFICIENT, ERR_NO_ACTIVE_IMAGE, MAX_IMAGE_SIZE_BYTES
from ._env import GIMP_AVAILABLE


def _placeholder_payload() -> Dict[str, Any]:
    """独立模式下返回的占位数据 (1x1 透明 PNG)。"""
    # 1x1 透明 PNG 的 base64
    tiny_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lE"
        "QVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
    )
    return {
        "success": True,
        "image_base64": "data:image/png;base64," + tiny_png,
        "metadata": {
            "width": 1920,
            "height": 1080,
            "color_mode": "RGB",
            "has_selection": False,
        },
    }


def get_image_for_analysis(image: Any = None, drawable: Any = None) -> Dict[str, Any]:
    """SRS-3021。

    :param image: ``Gimp.Image`` 实例；独立模式可传 None
    :param drawable: ``Gimp.Drawable``；可为 None
    :return: 见接口文档示例
    """
    if not GIMP_AVAILABLE or image is None:
        write_log("DEBUG", "ImageReader", "独立模式 / 无 GIMP 图像 -> 返回占位数据")
        return _placeholder_payload()

    # ===== GIMP 模式：导出活动图层为 PNG，再 Base64 =====
    try:
        # 此处仅给出最小可行实现，便于真实 GIMP 环境里继续演进。
        from gi.repository import Gimp, Gio  # type: ignore[import-not-found]

        width = image.get_width()
        height = image.get_height()
        has_sel = not Gimp.Selection.is_empty(image)

        # 临时文件路径
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, f"gimp_ai_mentor_export_{os.getpid()}.png")

        # 导出 PNG
        file = Gio.File.new_for_path(tmp_path)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, [drawable] if drawable else [], file)

        # 检查文件大小，避免一次性内存膨胀
        size = os.path.getsize(tmp_path)
        if size > MAX_IMAGE_SIZE_BYTES:
            write_log("WARNING", "ImageReader", f"图像超出 20MB 上限 ({size} bytes)，仅返回元数据")
            os.remove(tmp_path)
            return {
                "success": False,
                "image_base64": None,
                "metadata": {"width": width, "height": height, "has_selection": has_sel},
                "error": ERR_MEMORY_INSUFFICIENT,
            }

        with open(tmp_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        os.remove(tmp_path)

        return {
            "success": True,
            "image_base64": "data:image/png;base64," + b64,
            "metadata": {
                "width": width,
                "height": height,
                "color_mode": "RGB",
                "has_selection": has_sel,
            },
        }
    except Exception as e:  # noqa: BLE001
        write_log("ERROR", "ImageReader", f"GIMP 图像导出失败: {e}")
        return {
            "success": False,
            "image_base64": None,
            "metadata": None,
            "error": ERR_NO_ACTIVE_IMAGE,
        }
