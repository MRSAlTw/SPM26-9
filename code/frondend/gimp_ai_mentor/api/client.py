"""HTTP API 客户端 (SDD 4.2 / SRS-3023)。

特性：
- 仅依赖标准库 ``urllib``，避免引入 requests，方便嵌入 GIMP 的 Python 解释器。
- 任意 HTTP 错误 (网络超时 / 4xx / 5xx / JSON 解析失败) 抛 ``APIError``，由上层决定是否降级到 Mock。
- 通过 ``use_mock`` 配置整体切换到本地 Mock，方便 UI 独立调试。
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Optional

from ..config import load_config, write_log
from ..constants import (
    NETWORK_TIMEOUT_SEC,
    PATH_ANALYZE_IMAGE,
    PATH_GENERATE_GUIDE,
    PATH_NOTIFY,
    PATH_STATE_UPDATE,
    PATH_USER_COMMAND,
)
from .mock import MockBackend


class APIError(Exception):
    """API 调用失败。``code`` 用于 UI 决定 Toast 文案与重试策略。"""

    def __init__(self, code: str, message: str, http_status: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"APIError(code={self.code!r}, http={self.http_status}, msg={self.message!r})"


class AIClient:
    """统一的 AI 接口客户端。

    用法::

        client = AIClient()
        result = client.analyze_image({"image_base64": "...", ...})
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_sec: Optional[int] = None,
        use_mock: Optional[bool] = None,
    ) -> None:
        cfg = load_config()
        self.base_url = (base_url or cfg.get("api_base_url", "")).rstrip("/")
        self.api_key = api_key if api_key is not None else cfg.get("api_key", "")
        self.timeout = timeout_sec or cfg.get("request_timeout_sec", NETWORK_TIMEOUT_SEC)
        self.use_mock = bool(cfg.get("use_mock", False) if use_mock is None else use_mock)
        self._mock = MockBackend()

    # ===== 公共接口 (SDD 4.2.1 ~ 4.2.5) =====
    def analyze_image(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """SRS-3011 图像诊断分析接口。"""
        return self._post(PATH_ANALYZE_IMAGE, payload, mock_fn=self._mock.analyze_image)

    def generate_guide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """SRS-3012 修图指导生成接口。"""
        return self._post(PATH_GENERATE_GUIDE, payload, mock_fn=self._mock.generate_guide)

    def notify(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """SRS-3013 通知提醒接口。"""
        return self._post(PATH_NOTIFY, payload, mock_fn=self._mock.notify)

    def state_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """SRS-3014 状态更新接口。"""
        return self._post(PATH_STATE_UPDATE, payload, mock_fn=self._mock.state_update)

    def user_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """SRS-3015 用户指令交互接口。"""
        return self._post(PATH_USER_COMMAND, payload, mock_fn=self._mock.user_command)

    # ===== 内部实现 =====
    def _post(self, path: str, payload: Dict[str, Any], mock_fn) -> Dict[str, Any]:
        """统一的 POST 调用入口。

        逻辑：
        1. 若 use_mock=True 或未配置 base_url -> 直接走本地 Mock。
        2. 否则发起真实 HTTP，失败时记录日志并抛 APIError；调用方可据此选择重试 / 降级。
        """
        # 自动注入 request_id，便于云端排错
        if "request_id" not in payload:
            payload = {"request_id": str(uuid.uuid4()), **payload}

        if self.use_mock or not self.base_url:
            write_log("DEBUG", "API", f"[MOCK] {path} payload_keys={list(payload.keys())}")
            return mock_fn(payload)

        url = self.base_url + path
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": payload.get("request_id", ""),
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        write_log("INFO", "API", f"POST {url}")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                write_log("ERROR", "API", f"响应 JSON 解析失败: {e}; raw[:200]={raw[:200]!r}")
                raise APIError("AI_PARSE_FAILED", "AI 返回数据异常") from e

        except socket.timeout as e:
            write_log("ERROR", "API", f"网络超时: {url}")
            raise APIError("NETWORK_TIMEOUT", "网络请求超时，请检查网络后重试") from e
        except urllib.error.HTTPError as e:
            write_log("ERROR", "API", f"HTTP {e.code} {url}: {e.reason}")
            raise APIError(
                code=f"HTTP_{e.code}",
                message=f"服务端返回 {e.code}: {e.reason}",
                http_status=e.code,
            ) from e
        except urllib.error.URLError as e:
            write_log("ERROR", "API", f"网络异常: {e.reason}")
            raise APIError("NETWORK_ERROR", f"网络异常: {e.reason}") from e
