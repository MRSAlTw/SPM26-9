import os
import json
import base64
import requests
from json_repair import loads as repair_loads  # 引入专业的 JSON 修复加载器
from typing import Dict, Any, Optional
class GimpAIClient:
    def __init__(self, api_key: str, model_name: str = "qwen-vl-max-latest"):
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

        if not self.api_key:
            raise ValueError("API Key 不能为空")

    def get_suggestion(self, image_base64: str) -> Optional[Dict[Any, Any]]:
        # 1. 准备图片数据
        try:
            image_data_uri = f"data:image/png;base64,{image_base64}"
        except Exception as e:
            print(f"❌ 图片数据处理失败: {e}")
            return None

        # 2. 构建“白盒化”提示词
        system_prompt = """
    你是一位精通 GIMP 的修图专家。请分析这张图片，并返回标准的 JSON 格式数据。
    
    请从以下 6 个维度进行评分（1-10分）并给出简短评价：
    1. 亮度
    2. 对比度
    3. 饱和度
    4. 锐度
    5. 亮暗部 (动态范围)
    6. 色温

    然后，请给出 3-5 个具体的 GIMP 操作步骤。步骤必须包含：
    - menu_path: 菜单路径，例如 "颜色 -> 色阶"
    - action: 具体动作，例如 "移动中间调滑块"
    - value: 建议数值或位置，例如 "1.20" 或 "向右移动 10%"
    - reason: 为什么要这样做（白盒化原理）
    
    不要返回 Markdown 标记（如 ```json），直接返回 JSON 字符串。
    """

        # 3. 构建 JSON 示例 (Few-Shot)，让 AI 照着写
        json_example = """
    {
      "diagnosis": {
        "brightness": {"score": 4, "comment": "整体偏暗，直方图左偏"},
        "contrast": {"score": 5, "comment": "画面发灰，黑白对比不足"},
        "saturation": {"score": 6, "comment": "色彩略显平淡"},
        "sharpness": {"score": 7, "comment": "主体尚可，边缘略软"},
        "highlights_shadows": {"score": 3, "comment": "暗部死黑，细节丢失"},
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
    """

        user_prompt = f"{system_prompt}\n\n请严格按照以下 JSON 结构返回：\n{json_example}"

        # 4. 准备请求头和数据
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": image_data_uri},
                            {"text": user_prompt}
                        ]
                    }
                ]
            },
            "parameters": {
                "result_format": "message",
                "temperature": 0.1
            }
        }

        # 4. 发送请求并处理返回
        try:
            response = requests.post(self.url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                # 提取 output 里的 choices
                choices = result.get('output', {}).get('choices', [])

                if choices and len(choices) > 0:
                    first_choice = choices
                    json_str = ""

                    # 兼容多种返回结构：
                    # 情况1：标准结构 {'message': {'content': [{'text': '...'}]}}
                    if isinstance(first_choice, dict) and 'message' in first_choice:
                        message_content = first_choice['message'].get('content', [])
                        if isinstance(message_content, list) and len(message_content) > 0:
                            json_str = message_content.get('text', '')

                    # 情况2：直接返回列表 ['文本内容'] 或 [{'text': '...'}]
                    elif isinstance(first_choice, list):
                        item = first_choice
                        if isinstance(item, dict):
                            json_str = item.get('text', '')
                        else:
                            json_str = str(item)

                    # 情况3：直接是字符串
                    elif isinstance(first_choice, str):
                        json_str = first_choice

                    # 清洗数据
                    # 清洗数据（去除 markdown 标记）
                    if json_str:
                        clean_json_str = json_str.replace("```json", "").replace("```", "").strip()

                        # 使用专业的 json-repair 库进行解析，自动修复逗号、引号等各种格式错误
                        try:
                            data = repair_loads(clean_json_str)
                            return data
                        except Exception as e:
                            print(f"❌ 即使使用了修复库，JSON依然无法解析: {e}")
                            print(f"原始内容片段: {clean_json_str[:200]}")
                            return None

            else:
                print(f"❌ API 请求失败 (状态码: {response.status_code}): {response.text}")
                return None

        except Exception as e:
            print(f"❌ 网络或解析错误: {e}")
            return None

        # 兜底返回
    def _get_fallback_result(self) -> Dict:
        """
        兜底方案：当 AI 服务不可用时，返回一个默认的安全结果
        """
        return {
        "error": "AI服务暂时不可用",
        "diagnosis": {
            "brightness": {"score": 5, "comment": "AI服务降级，使用默认评估"},
            "contrast": {"score": 5, "comment": "AI服务降级，使用默认评估"},
            "saturation": {"score": 5, "comment": "AI服务降级，使用默认评估"},
            "sharpness": {"score": 5, "comment": "AI服务降级，使用默认评估"},
            "highlights_shadows": {"score": 5, "comment": "AI服务降级，使用默认评估"},
            "color_temp": {"score": 5, "comment": "AI服务降级，使用默认评估"}
        },
        "action_plan": [
            {
                "step": 1,
                "tool": "通用建议",
                "menu_path": "帮助 -> 查看日志",
                "action": "检查网络连接",
                "value": "重试",
                "reason": "AI 服务暂时无法响应，请稍后重试。"
            }
        ]
    }

# --- 本地调试入口 (仅在直接运行此文件时生效) ---
if __name__ == "__main__":
    # 请在这里填入你的 Key 进行本地调试
    API_KEY = "sk-e97eee460b9840bd8645f84557199a1e"
    # 测试图片路径 (请替换为本地一张真实图片的路径)
    test_image_path = r"C:\Users\86185\Desktop\【哲风壁纸】夏天森林-大树仰拍.png"

    if not os.path.exists(test_image_path):
        print(f"请准备一张测试图片 {test_image_path}")
    else:
        try:
            with open(test_image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            client = GimpAIClient(api_key=API_KEY)
            result = client.get_suggestion(image_base64=img_b64)

            if result:
                print("✅ 调用成功！返回结果：")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("❌ 调用失败，返回空值")

        except Exception as e:
            print(f"❌ 调试发生异常: {e}")