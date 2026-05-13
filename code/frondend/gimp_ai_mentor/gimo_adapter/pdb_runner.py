"""PDB 操作执行器。

将步骤里的 ``pdb_operation`` 翻译成对 Gimp PDB 的调用。
独立模式下仅记录日志并返回成功。
"""

from __future__ import annotations

from typing import Any, Dict

from ..config import write_log
from ._env import GIMP_AVAILABLE


def run_pdb_operation(image: Any, drawable: Any, operation: Dict[str, Any]) -> bool:
    """执行单个 PDB 操作。

    :param image: ``Gimp.Image`` 或 None
    :param drawable: ``Gimp.Drawable`` 或 None
    :param operation: ``{"name": "gimp-drawable-levels", "params": {...}}``
    :return: True 表示成功，False 表示失败
    """
    op_name = operation.get("name", "")
    params = operation.get("params", {})

    if not GIMP_AVAILABLE or image is None:
        write_log("INFO", "PDB", f"[MOCK] 执行 {op_name} params={params}")
        return True

    try:  # pragma: no cover - 仅 GIMP 环境
        from gi.repository import Gimp  # type: ignore[import-not-found]

        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure(op_name)
        if proc is None:
            write_log("WARNING", "PDB", f"未识别的 PDB 操作: {op_name}，已跳过")
            return False

        # 这里只做最小骨架，实际参数对齐应基于 proc.get_arguments() 严格匹配
        cfg = proc.create_config()
        cfg.set_property("image", image)
        if drawable is not None:
            cfg.set_property("drawable", drawable)
        for k, v in params.items():
            try:
                cfg.set_property(k.replace("_", "-"), v)
            except Exception as e:  # noqa: BLE001
                write_log("WARNING", "PDB", f"参数 {k}={v} 设置失败: {e}")

        result = proc.run(cfg)
        ok = result is not None and result.index(0) == Gimp.PDBStatusType.SUCCESS
        write_log("INFO", "PDB", f"执行 {op_name} -> success={ok}")
        return ok
    except Exception as e:  # noqa: BLE001
        write_log("ERROR", "PDB", f"执行 {op_name} 失败: {e}")
        return False
