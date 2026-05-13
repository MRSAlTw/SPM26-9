# GIMP AI Mentor — 前端 GUI

依据《GIMP AI Mentor 软件设计说明书 (SDD) v1》第 4 章接口定义，以及 `gimp_ai_修图插件_界面原型.html` 的视觉风格，使用 **Python 3 + PyGObject (GTK 3)** 实现的修图助手前端面板。

支持两种运行形态：

1. **GIMP 3 插件** — 部署到 GIMP 插件目录，从 `滤镜 → AI → AI 修图助手...` 启动。
2. **独立运行** — `python -m gimp_ai_mentor.standalone`，无 GIMP 也能调试 UI（GIMP 调用 + AI 接口全部走本地 Mock）。

---

## 项目结构

```
gimp_ai_mentor/
├── __init__.py
├── constants.py            # 接口枚举常量 (步骤状态、Toast 级别、命令类型等)
├── config.py               # SRS-3024  配置 + 日志 (5MB 轮转)
├── api/
│   ├── client.py           # SRS-3011/3012/3013/3014/3015  HTTP 客户端
│   └── mock.py             # 本地 Mock 兜底 (后端未就绪时自动接管)
├── gimp_adapter/
│   ├── _env.py             # 探测 GIMP Python 环境是否可用
│   ├── image_reader.py     # SRS-3021  图像读取 (Base64 + 元数据)
│   ├── state_listener.py   # SRS-3022  GIMP 状态监听 (200ms 轮询兜底)
│   └── pdb_runner.py       #          执行步骤里的 pdb_operation
├── core/
│   └── controller.py       # SRS-3003  on_submit_generate / on_step_action
├── ui/
│   ├── theme.py            # 深色主题 CSS (颜色与原型 HTML 一致)
│   ├── components.py       # ToastManager / StepRow / RadarChart
│   ├── main_panel.py       # 主面板 (实现 SRS-3002 / 3003 / 3004)
│   └── ui_manager.py       # SRS-3001  面板生命周期
├── plugin.py               # GIMP 3 插件入口
├── standalone.py           # 独立运行入口
└── README.md               # 本文件
```

---

## 接口实现对照表

| 文档章节 | 编号 | 实现位置 |
|----------|------|----------|
| 4.1.1 面板生命周期 | SRS-3001 | `ui/ui_manager.py` `UIManager.create_panel / destroy_panel` |
| 4.1.2 数据绑定 | SRS-3002 | `ui/main_panel.py` `bind_diagnosis_data / update_step_list / update_step_status` |
| 4.1.3 用户回调 | SRS-3003 | `core/controller.py` `on_submit_generate / on_step_action` |
| 4.1.4 业务处理 | SRS-3004 | `ui/main_panel.py` `get_prompt_text / show_toast_message` |
| 4.2.1 图像诊断 | SRS-3011 | `api/client.py` `analyze_image` |
| 4.2.2 修图指导 | SRS-3012 | `api/client.py` `generate_guide` |
| 4.2.3 通知提醒 | SRS-3013 | `api/client.py` `notify` |
| 4.2.4 状态更新 | SRS-3014 | `api/client.py` `state_update` |
| 4.2.5 用户指令 | SRS-3015 | `api/client.py` `user_command` |
| 4.3.1 图像读取 | SRS-3021 | `gimp_adapter/image_reader.py` |
| 4.3.2 状态监听 | SRS-3022 | `gimp_adapter/state_listener.py` |
| 4.3.3 云端 AI | SRS-3023 | `api/client.py` `_post` (HTTP 调用 + 错误码映射) |
| 4.3.4 配置/日志 | SRS-3024 | `config.py` `load_config / save_config / write_log` |

---

## 一、独立运行 (推荐先跑通)

### 1. 安装 PyGObject + GTK 3

| 系统 | 命令 |
|------|------|
| **macOS** | `brew install pygobject3 gtk+3` |
| **Ubuntu/Debian** | `sudo apt install python3-gi gir1.2-gtk-3.0` |
| **Fedora** | `sudo dnf install python3-gobject gtk3` |
| **Windows** | 推荐用 [MSYS2](https://www.msys2.org/) 安装 `mingw-w64-x86_64-python-gobject mingw-w64-x86_64-gtk3` |

### 2. 启动

```bash
cd /path/to/SPM-26-9
python3 -m gimp_ai_mentor.standalone
```

效果：
- 弹出深色风格主面板
- 点击「AI 智能修图」 → 自动取占位图 → 调用 Mock 接口 → 显示诊断卡 (含雷达图) + 4 个步骤
- 每个步骤可点「执行」/「忽略」，状态会按 `pending → active → completed/ignored` 流转
- 顶部条状 Toast 提示进度

> 此模式下 `~/.gimp-2.10/plug-ins/ai-mentor/config.json` 默认 `use_mock=true`，所有 HTTP 调用走本地 Mock。

---

## 二、作为 GIMP 3 插件运行

### 1. 部署

```bash
# Linux / macOS：根据 GIMP 实际版本目录调整路径
mkdir -p ~/.config/GIMP/3.0/plug-ins/ai-mentor
cp -r gimp_ai_mentor ~/.config/GIMP/3.0/plug-ins/ai-mentor/
chmod +x ~/.config/GIMP/3.0/plug-ins/ai-mentor/gimp_ai_mentor/plugin.py
```

> GIMP 3 的插件入口是 `plugin.py`；`gimp_ai_mentor/` 包须随之放在同目录。

### 2. 启动

打开 GIMP 3 → 任意打开一张图 → 菜单 `Filters → AI → AI 修图助手...`，主面板弹出。

> **GIMP 2.10**：底层 PDB API 不同（`gimpfu`），本仓库面向 GIMP 3 (libgimp+gi)。如需移植到 2.10，主要改动集中在 `plugin.py`。

---

## 三、对接真实后端

后端就绪后，编辑配置：

```bash
# 文件位置
~/.gimp-2.10/plug-ins/ai-mentor/config.json
```

```json
{
  "api_base_url": "https://your-backend.example.com",
  "api_key": "<bearer token>",
  "use_mock": false,
  "request_timeout_sec": 30
}
```

`AIClient` 会用 `Authorization: Bearer <api_key>` 与 `X-Request-ID: <uuid>` 头发起 POST：

```
POST /internal/ai/analyze-image
POST /internal/ai/generate-guide
POST /internal/ui/notify
POST /internal/ui/state-update
POST /internal/core/user-command
```

请求/响应体严格遵循接口文档示例。

### 错误处理 (SRS-3023)

| 场景 | 行为 |
|------|------|
| 网络超时 (>30s) | 抛 `APIError(code="NETWORK_TIMEOUT")`，UI 显示红色 Toast |
| HTTP 4xx/5xx | 抛 `APIError(code="HTTP_xxx")`，记录原始 reason |
| JSON 解析失败 | 抛 `APIError(code="AI_PARSE_FAILED")`，原始响应记入日志 |
| `use_mock=true` 或未配 `base_url` | 直接走本地 Mock |

---

## 四、UI 与原型的对照

| 原型 HTML 元素 | 实现位置 |
|----------------|----------|
| 右侧 `#ai-panel` 容器 | `MainPanel` (380×700) |
| `#ai-panel` 头部「AI 智能修图助手」 | `MainPanel` `panel-header` |
| 「AI 智能修图」按钮 | `run_btn` |
| `#diagnosis-container` 诊断卡 | `_build_diagnosis_card()` |
| 雷达图 `#radar-chart` | `RadarChart` (Cairo 自绘) |
| 健康度 `#health-score` | `score_label` |
| 摘要文本 | `summary_label` (.diagnosis-summary) |
| `#ai-input` 自然语言输入框 | `prompt_view` (带 placeholder) |
| 步骤列表 `#steps-container` | `steps_box` + `StepRow` |
| 空状态 `#steps-empty` | `empty_hint` |
| 底部「AI 服务在线」状态 | `footer-bar` |
| Toast (原型缺失，按 SRS-3004 补齐) | `ToastManager` |

> 原型里的「灵感库」「灵感卡片」「保存方案弹窗」「工具直达弹窗」「画布右键菜单」等不属于接口契约范围，这一版本聚焦于 **接口定义文档** 要求的核心交互；后续若需要可在 `ui/` 下增加 `inspiration_dialog.py` 等模块独立扩展。

---

## 五、运行时日志

- 配置文件：`~/.gimp-2.10/plug-ins/ai-mentor/config.json`
- 日志文件：`~/.gimp-2.10/plug-ins/ai-mentor/gimp-ai-mentor.log` (5MB 轮转，最多 3 备份)
- 同时输出到 stderr，方便 GIMP `--verbose` 模式下排错。

---

## 六、已知限制 / TODO

1. `pdb_runner.py` 仅给出最小骨架，真实参数对齐应基于 `proc.get_arguments()` 严格匹配类型转换。
2. 原型里的「灵感库」(`#inspiration-modal`) 与「工具直达」弹窗 (`#tool-modal`) 暂未实现，可在后续迭代中补齐。
3. 当前主题采用纯 CSS，复杂样式 (如 `letter-spacing`) GTK 不支持，已退化为合理近似。
