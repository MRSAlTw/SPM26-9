# -*- coding: utf-8 -*-
"""
小组 AI 层：阿里云 DashScope 多模态（通义千问 VL）→ 核心逻辑层。

开源与密钥
----------
- 仓库**不包含**任何第三方 API 密钥；克隆即可使用**离线演示**（内置示例修图方案，预览仍可用）。
- 需要云端分析时，由**最终用户**在本机自行配置密钥（勿写入源码、勿提交 Git）：
  - 环境变量 ``DASHSCOPE_API_KEY`` 或 ``DASHSCOPE_APIKEY``；
  - 或环境变量 ``DASHSCOPE_API_KEY_FILE`` 指向本机文本文件（首行非 ``#`` 行为密钥）。

无密钥时 ``fetch_raw_response`` 抛出 ``NotImplementedError``，由 llm_stub 捕获并回退示例方案。

可选环境变量：``DASHSCOPE_BASE_URL``、``DASHSCOPE_MODEL``（默认 ``qwen-vl-max-latest``）、
``DASHSCOPE_MAX_TOKENS``、``DASHSCOPE_TEMPERATURE``（默认 ``0.1``）、
``DASHSCOPE_SSL_VERIFY=0``（仅调试禁用证书校验）。

模型输出：纯 JSON 或文末 `` ```json ... ``` `` 均可（见 ``structured_plan.extract_json_plan_from_text``）。
提示词与小组 AI 层脚本（DashScope 多模态 + diagnosis/action_plan）对齐，见 ``_build_multimodal_prompt``。
"""

from __future__ import unicode_literals

import base64
import json
import os
import ssl
import tempfile

try:
    basestring
except NameError:
    basestring = str

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError

_DEFAULT_BASE = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)


def _env(name, default=None):
    v = os.environ.get(name)
    if v is None or not str(v).strip():
        return default
    return v.strip()


def _read_key_file(path):
    """读取本机密钥文件：第一行非空且非 # 开头视为密钥。"""
    path = os.path.expanduser(os.path.expandvars(path))
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def _resolve_api_key():
    """从环境变量或用户指定的本机文件解析密钥；无则返回 None（离线演示）。"""
    k = _env("DASHSCOPE_API_KEY") or _env("DASHSCOPE_APIKEY")
    if k:
        return k
    key_file = _env("DASHSCOPE_API_KEY_FILE")
    if key_file:
        return _read_key_file(key_file)
    return None


def _build_multimodal_prompt():
    """
    与小组 AI 层「白盒化」契约一致，并满足核心层 structured_plan 解析（diagnosis + action_plan）。
    """
    from mentorlib import structured_plan

    # 与小组 ai_client 脚本一致的评分维度与 action_plan 字段说明（第五维为核心层约定的 gaussian_blur）
    system_block = u"""
你是一位精通 GIMP 的修图专家。请结合上传的图片进行分析，并输出可被程序解析的结构化数据。

请从以下 6 个维度进行评分（1–10 分）并给出简短评价（与 diagnosis 键名严格对应）：
1. 亮度（brightness）：照片的「电灯开关」
2. 对比度（contrast）：让照片「黑白分明」
3. 饱和度（saturation）：颜色的「浓淡控制器」
4. 锐度（sharpness）：细节的「放大镜」
5. 高斯模糊（gaussian_blur）
6. 色温（color_temp）：照片的「冷暖开关」

然后给出 3–5 个具体的 GIMP 操作步骤。每一步须包含：
- step：序号（整数）
- tool：工具中文名（如 色阶、曲线、高斯模糊）
- menu_path：菜单路径，例如「颜色 -> 色阶」
- action：具体动作描述
- value：建议数值或文字说明（可与核心层 unit 数值格式一致，也可用中文短句）
- reason：这样做的原因（白盒化说明）

diagnosis 与 action_plan 的键名须与下列示例一致（diagnosis 使用英文键名）。
""".strip()

    json_example = u"""
{
  "diagnosis": {
    "brightness": {"score": 4, "comment": "整体偏暗，直方图左偏"},
    "contrast": {"score": 5, "comment": "画面发灰，黑白对比不足"},
    "saturation": {"score": 6, "comment": "色彩略显平淡"},
    "sharpness": {"score": 7, "comment": "主体尚可，边缘略软"},
    "gaussian_blur": {"score": 3, "comment": "过渡略硬或局部需柔化"},
    "color_temp": {"score": 5, "comment": "略微偏冷"}
  },
  "action_plan": [
    {
      "step": 1,
      "tool": "色阶",
      "menu_path": "颜色 -> 色阶",
      "action": "调整输入色阶",
      "value": "中间调滑块调至 1.20",
      "reason": "提亮中间调，修正曝光不足"
    },
    {
      "step": 2,
      "tool": "曲线",
      "menu_path": "颜色 -> 曲线",
      "action": "绘制 S 型曲线",
      "value": "高光点上提，暗部点下压",
      "reason": "增加通透感，提升对比度"
    }
  ]
}
""".strip()

    parts = [
        system_block,
        u"",
        u"请严格按照下列 JSON 结构返回（可照示例字段填空）：",
        json_example,
        u"",
        u"【解析兼容】",
        u"- 若回复中仅有 JSON、无其它文字，可直接输出该 JSON 对象。",
        u"- 若有中文说明，请在最后单独追加一段 JSON，并用 Markdown 代码围栏包裹，例如：",
        u"```json",
        u"{ ... }",
        u"```",
        u"",
        structured_plan.prompt_ai_layer_full_spec_zh(),
        u"",
        structured_plan.prompt_action_plan_format_zh(),
    ]
    return u"\n".join(parts)


def _export_merged_image_jpeg_path(image, drawable):
    """
    复制图像、合并可见图层、转为 RGB（如需要）、导出为临时 JPEG 文件。
    返回绝对路径（调用方负责 os.unlink）。
    """
    from gimpfu import pdb

    try:
        from gimpfu import CLIP_TO_IMAGE, RGB
    except ImportError:
        CLIP_TO_IMAGE = 1
        RGB = 0

    try:
        from gimpfu import RUN_NONINTERACTIVE
    except ImportError:
        RUN_NONINTERACTIVE = 1

    tmp_img = pdb.gimp_image_duplicate(image)
    if tmp_img is None:
        raise RuntimeError("gimp_image_duplicate 失败")

    try:
        pdb.gimp_image_merge_visible_layers(tmp_img, CLIP_TO_IMAGE)
        export_drawable = pdb.gimp_image_get_active_drawable(tmp_img)
        if export_drawable is None:
            raise RuntimeError("合并后无可导出图层")

        if pdb.gimp_image_base_type(tmp_img) != RGB:
            pdb.gimp_image_convert_rgb(tmp_img)
            export_drawable = pdb.gimp_image_get_active_drawable(tmp_img)

        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        path = os.path.abspath(path)

        pdb.file_jpeg_save(
            RUN_NONINTERACTIVE,
            tmp_img,
            export_drawable,
            path,
            path,
            0.92,
            0.0,
            1,
            0,
            "",
            0,
            1,
            0,
            0,
        )
        if not os.path.isfile(path) or os.path.getsize(path) < 1:
            raise RuntimeError("JPEG 导出失败或文件为空：%s" % path)
        return path
    finally:
        pdb.gimp_image_delete(tmp_img)


def _dashscope_request(api_key, payload):
    base = _env("DASHSCOPE_BASE_URL", _DEFAULT_BASE)
    body = json.dumps(payload, ensure_ascii=False)
    if not isinstance(body, bytes):
        body = body.encode("utf-8")

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": "Bearer %s" % api_key,
        "X-DashScope-SSE": "disable",
    }
    req = Request(base, data=body, headers=headers)

    verify = _env("DASHSCOPE_SSL_VERIFY", "1") not in ("0", "false", "False", "no", "NO")
    if verify:
        return urlopen(req, timeout=120)
    ctx = ssl._create_unverified_context()
    return urlopen(req, context=ctx, timeout=120)


def _parse_dashscope_text(result):
    """从 DashScope multimodal-generation 响应中取出助手文本（兼容 content 多段）。"""
    try:
        choices = result["output"]["choices"]
        msg = choices[0]["message"]
        content = msg["content"]
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    return item["text"]
                if isinstance(item, basestring):
                    return item
        if isinstance(content, basestring):
            return content
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError("DashScope 响应结构异常，无法取出文本：%s；原始 keys：%r" % (e, list(result.keys())))
    raise ValueError("DashScope 响应中未找到可用的 message.content 文本")


def fetch_raw_response(image, drawable):
    """
    调用 DashScope 多模态接口，返回模型完整文本（UTF-8 / Unicode），供 parse_and_validate_plan 使用。

    image / drawable：GIMP 对象；实际发送的是「合并可见图层」后的 JPEG。
    """
    api_key = _resolve_api_key()
    if not api_key:
        raise NotImplementedError(
            u"【离线演示】未配置 DASHSCOPE_API_KEY（或 DASHSCOPE_API_KEY_FILE）。"
            u"已使用内置示例方案；配置密钥后可调用通义千问。详见插件说明（勿将密钥写入源码）。"
        )

    model = _env("DASHSCOPE_MODEL", "qwen-vl-max-latest")
    try:
        max_tokens = int(_env("DASHSCOPE_MAX_TOKENS", "2048"))
    except ValueError:
        max_tokens = 2048
    max_tokens = max(256, min(8192, max_tokens))
    try:
        temperature = float(_env("DASHSCOPE_TEMPERATURE", "0.1"))
    except ValueError:
        temperature = 0.1
    temperature = max(0.0, min(2.0, temperature))

    jpeg_path = None
    try:
        jpeg_path = _export_merged_image_jpeg_path(image, drawable)
        with open(jpeg_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("ascii")
    finally:
        if jpeg_path and os.path.isfile(jpeg_path):
            try:
                os.unlink(jpeg_path)
            except OSError:
                pass

    prompt_text = _build_multimodal_prompt()
    if not isinstance(prompt_text, basestring):
        prompt_text = str(prompt_text)

    # 与小组脚本一致：先 image 后 text；parameters 含 result_format（DashScope 多模态）
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": "data:image/jpeg;base64,%s" % img_b64},
                        {"text": prompt_text},
                    ],
                }
            ]
        },
        "parameters": {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "result_format": "message",
        },
    }

    try:
        resp = _dashscope_request(api_key, payload)
        raw_bytes = resp.read()
    except HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError("DashScope HTTP %s：%s" % (e.code, err_body or e.reason))
    except URLError as e:
        raise RuntimeError("网络请求失败：%s" % (e.reason,))

    if isinstance(raw_bytes, bytes):
        response_body = raw_bytes.decode("utf-8", errors="replace")
    else:
        response_body = raw_bytes

    try:
        result = json.loads(response_body)
    except ValueError as e:
        raise RuntimeError("接口返回非 JSON：%s" % e)

    if isinstance(result, dict) and result.get("code"):
        raise RuntimeError(
            "DashScope 业务错误：%s %s"
            % (result.get("code"), result.get("message", result.get("msg", "")))
        )

    text = _parse_dashscope_text(result)
    if not isinstance(text, basestring) or not text.strip():
        raise ValueError("模型返回文本为空")
    return text
