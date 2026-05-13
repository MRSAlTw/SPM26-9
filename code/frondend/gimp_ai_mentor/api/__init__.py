"""API 客户端层。

封装 SDD 4.2 节定义的 5 个 HTTP 接口，并提供本地 Mock 兜底。
"""

from .client import AIClient, APIError
from .mock import MockBackend

__all__ = ["AIClient", "APIError", "MockBackend"]
