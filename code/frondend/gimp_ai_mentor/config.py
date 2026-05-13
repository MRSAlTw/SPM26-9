"""配置与日志接口 (SRS-3024)。

实现：
- load_config() / save_config(): 读写 ~/.gimp-2.10/plug-ins/ai-mentor/config.json
- write_log(): 写日志，单文件 5MB 轮转，保留 3 个备份
- 文件读写失败时的容错策略 (返回默认配置 / 静默忽略)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict

# ===== 路径常量 =====
_PLUGIN_DIR_NAME = ".gimp-2.10/plug-ins/ai-mentor"
CONFIG_DIR: Path = Path.home() / _PLUGIN_DIR_NAME
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
LOG_FILE: Path = CONFIG_DIR / "gimp-ai-mentor.log"

# ===== 默认配置 =====
DEFAULT_CONFIG: Dict[str, Any] = {
    "api_key": "",
    "api_base_url": "http://127.0.0.1:8000",
    "model": "gimp-mentor-v1",
    "ui_theme": "dark",
    "language": "zh_CN",
    "use_mock": True,  # 后端未就绪时自动降级到 Mock
    "request_timeout_sec": 30,
}


# ===== 日志 =====
_logger: logging.Logger | None = None


def _ensure_dir() -> None:
    """确保配置目录存在，失败时静默忽略，避免阻塞插件启动。"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        # 权限不足 / 只读文件系统 -> 后续 I/O 会自然失败并被各自处理
        pass


def _get_logger() -> logging.Logger:
    """获取（懒加载）日志器，失败时回退到 stderr。"""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("gimp_ai_mentor")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # 避免重复添加 handler
    if logger.handlers:
        _logger = logger
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler (5MB 轮转，3 个备份；写入失败则降级到 stderr)
    _ensure_dir()
    try:
        file_handler = RotatingFileHandler(
            filename=str(LOG_FILE),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        # 写日志失败：静默 + 仅 stderr
        pass

    # stderr handler (调试用)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    _logger = logger
    return logger


def write_log(level: str, module: str, message: str) -> None:
    """写日志 (SRS-3024)。

    :param level: "DEBUG" / "INFO" / "WARNING" / "ERROR"
    :param module: 模块名，如 "AI" / "Core" / "UI"
    :param message: 日志正文
    """
    try:
        logger = _get_logger()
        lv = getattr(logging, level.upper(), logging.INFO)
        logger.log(lv, "[%s] %s", module, message)
    except Exception:  # noqa: BLE001 - 日志失败必须静默
        pass


# ===== 配置 =====
def load_config() -> Dict[str, Any]:
    """读取配置文件 (SRS-3024)。

    若文件不存在 / 权限不足 / 解析失败：返回默认配置，并尝试自动创建一份。
    """
    _ensure_dir()
    if not CONFIG_FILE.exists():
        # 自动创建默认配置
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # 与默认配置合并，保证字段齐全
        merged = dict(DEFAULT_CONFIG)
        if isinstance(data, dict):
            merged.update(data)
        return merged
    except (OSError, PermissionError) as e:
        write_log("WARNING", "Config", f"读取配置文件失败，已回退默认配置: {e}")
        return dict(DEFAULT_CONFIG)
    except json.JSONDecodeError as e:
        write_log("WARNING", "Config", f"配置文件 JSON 解析失败，已回退默认配置: {e}")
        return dict(DEFAULT_CONFIG)


def save_config(config: Dict[str, Any]) -> bool:
    """写入配置文件 (SRS-3024)。

    :return: True 表示成功，False 表示失败
    """
    _ensure_dir()
    try:
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except (OSError, PermissionError) as e:
        write_log("ERROR", "Config", f"保存配置失败: {e}")
        return False
