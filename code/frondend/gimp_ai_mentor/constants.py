"""全局常量与枚举定义。

集中维护接口契约里出现的字符串枚举值，避免在业务层散落 magic string。
"""

from __future__ import annotations

# ===== 步骤状态 (SRS-3002 update_step_status) =====
STEP_PENDING = "pending"        # 待办 / 灰色
STEP_ACTIVE = "active"          # 执行中 / 高亮
STEP_COMPLETED = "completed"    # 已完成 / 打勾
STEP_IGNORED = "ignored"        # 已跳过

VALID_STEP_STATUS = {STEP_PENDING, STEP_ACTIVE, STEP_COMPLETED, STEP_IGNORED}

# ===== 步骤动作 (SRS-3003 on_step_action) =====
ACTION_EXECUTE = "execute"
ACTION_IGNORE = "ignore"

# ===== Toast 级别 (SRS-3004 / SRS-3013) =====
TOAST_INFO = "info"
TOAST_SUCCESS = "success"
TOAST_WARNING = "warning"
TOAST_ERROR = "error"

# ===== 用户命令类型 (SRS-3015) =====
CMD_ANALYZE = "analyze"
CMD_NEXT_STEP = "next_step"
CMD_SKIP_STEP = "skip_step"
CMD_APPLY = "apply"
CMD_UNDO = "undo"

# ===== AI 接口路径 (SRS-3011 / SRS-3012 / SRS-3013 / SRS-3014 / SRS-3015) =====
PATH_ANALYZE_IMAGE = "/internal/ai/analyze-image"
PATH_GENERATE_GUIDE = "/internal/ai/generate-guide"
PATH_NOTIFY = "/internal/ui/notify"
PATH_STATE_UPDATE = "/internal/ui/state-update"
PATH_USER_COMMAND = "/internal/core/user-command"

# ===== 云端 AI 接口 (SRS-3023) =====
PATH_CLOUD_ANALYZE = "/v1/analyze"

# ===== 错误码 =====
ERR_NO_ACTIVE_IMAGE = "NO_ACTIVE_IMAGE"
ERR_MEMORY_INSUFFICIENT = "MEMORY_INSUFFICIENT"
ERR_PDB_ERROR = "PDB_ERROR"
ERR_NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
ERR_AI_PARSE_FAILED = "AI_PARSE_FAILED"
ERR_INVALID_COMMAND_STATE = "INVALID_COMMAND_STATE"

# ===== 上限约束 (SRS-2011) =====
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
NETWORK_TIMEOUT_SEC = 30
