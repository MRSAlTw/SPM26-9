"""状态监听接口 (SRS-3022)。

异步事件驱动 + 200ms 轮询兜底；独立模式下永不触发回调，仅返回有效 listener_id。
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict

from ..config import write_log
from ._env import GIMP_AVAILABLE

_StateCallback = Callable[[Dict], None]

# 简单的内存注册表
_listeners: Dict[int, _StateCallback] = {}
_next_id = 1
_poll_thread: threading.Thread | None = None
_poll_stop = threading.Event()


def _start_polling_if_needed() -> None:
    """启动后台轮询线程 (独立模式下不启动)。"""
    global _poll_thread
    if not GIMP_AVAILABLE:
        return
    if _poll_thread is not None and _poll_thread.is_alive():
        return

    def _loop() -> None:  # pragma: no cover - GIMP 环境才会执行
        while not _poll_stop.is_set():
            try:
                from gi.repository import Gimp  # type: ignore[import-not-found]

                images = Gimp.get_images()
                state = {
                    "active_image_id": images[0].get_id() if images else None,
                    "polling_mode": True,
                    "timestamp": time.time(),
                }
                for cb in list(_listeners.values()):
                    try:
                        cb(state)
                    except Exception as e:  # noqa: BLE001
                        write_log("WARNING", "StateListener", f"回调异常: {e}")
            except Exception as e:  # noqa: BLE001
                write_log("ERROR", "StateListener", f"轮询失败: {e}")
            _poll_stop.wait(0.2)

    _poll_stop.clear()
    _poll_thread = threading.Thread(target=_loop, name="gimp-ai-state-poll", daemon=True)
    _poll_thread.start()


def register_state_listener(callback: _StateCallback) -> int:
    """注册状态监听器，返回 listener_id。"""
    global _next_id
    lid = _next_id
    _next_id += 1
    _listeners[lid] = callback
    write_log("DEBUG", "StateListener", f"注册监听器 id={lid} (总数 {len(_listeners)})")
    _start_polling_if_needed()
    return lid


def unregister_state_listener(listener_id: int) -> None:
    """注销监听器；若全部注销则停止轮询线程。"""
    _listeners.pop(listener_id, None)
    write_log("DEBUG", "StateListener", f"注销监听器 id={listener_id} (剩余 {len(_listeners)})")
    if not _listeners:
        _poll_stop.set()
