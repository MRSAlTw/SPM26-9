# -*- coding: utf-8 -*-
"""
大模型编排入口（GIMP 侧调用 request_preview_plan）。

- 真正「接你们后端」的函数在：mentorlib/ai_client.py → fetch_raw_response
- 中文 + JSON 混排解析在：mentorlib/structured_plan.py
- 白名单与字段校验在：mentorlib/schema.py
- PDB 执行在：mentorlib/pdb_runner.py
- 未配置云端密钥时走离线演示（NotImplementedError → 内置示例方案），见 mentorlib/ai_client.py。

若 AI 层当前只返回中文、没有 JSON：
  B. 或：后端两次调用——第一次只拿中文给用户；第二次专用小提示词只输出 JSON ops。
  C. 或：暂时 ops=[]，仅展示中文、预览窗口不做效果（需在 parse 失败分支自行改 preview 行为）。
"""

from __future__ import unicode_literals

from mentorlib import schema
from mentorlib import structured_plan


def _mock_plan():
    """无后端或未解析到 JSON 时的联调数据。"""
    plan = {
        "summary": (
            "【示例方案】占位数据：轻微压高光、提一点饱和度并锐化；"
            "色温项为 color_balance 近似。请对照新开的预览窗口阅读下列步骤。"
        ),
        "steps_for_user": [
            "颜色 → 色阶：将高光滑块略向左收，压一点过曝高光。",
            "颜色 → 色相-饱和度：小幅提高全图饱和度。",
            "颜色 → 色彩平衡：按需在阴影/中间调/高光加青或加红微调。",
            "滤镜 → 增强 → 钝化蒙版(USM)：小半径、适中数量。",
            "若需色温感：用色彩平衡或曲线代替单一「色温」滑条，便于理解通道关系。",
        ],
        "ops": [
            {
                "op": "levels",
                "args": {
                    "channel": "value",
                    "low_input": 5,
                    "high_input": 245,
                    "low_output": 0,
                    "high_output": 255,
                    "gamma": 1.0,
                },
            },
            {
                "op": "hue_saturation",
                "args": {
                    "hue_range": "all",
                    "hue": 0.0,
                    "lightness": 0.0,
                    "saturation": 8.0,
                },
            },
            {
                "op": "unsharp_mask",
                "args": {"radius": 1.2, "amount": 0.35, "threshold": 3},
            },
            {
                "op": "color_temperature",
                "args": {"warmth": 6.0},
            },
        ],
    }
    return schema.validate_plan(plan)


def request_preview_plan(image, drawable):
    """
    image, drawable: GIMP 对象（导出缩略图、读尺寸等在 ai_client 里用）。

    返回已通过 schema.validate_plan 的 dict。
    """
    try:
        from mentorlib import ai_client

        raw = ai_client.fetch_raw_response(image, drawable)
        return structured_plan.parse_and_validate_plan(raw)
    except NotImplementedError as e:
        try:
            from gimpfu import pdb

            hint = (e.args and e.args[0]) or (
                u"当前为离线演示模式（内置示例方案）。"
            )
            pdb.gimp_message(hint)
        except Exception:
            pass
        return _mock_plan()
    except (ValueError, TypeError, KeyError) as e:
        # JSON 缺失或 schema 不通过：仍返回占位，避免预览整条链路挂死；
        # 上线后可改为 gimp_message 提示用户检查模型输出格式。
        try:
            from gimpfu import pdb

            pdb.gimp_message(
                "AI 返回未能解析为有效方案 JSON，已使用内置示例方案。"
                "请让模型追加 ```json``` 块或实现两阶段接口。详情：\n%s" % e
            )
        except Exception:
            pass
        return _mock_plan()
