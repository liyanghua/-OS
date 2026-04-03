"""千问 VL 视觉分析模块 — 用多模态模型从笔记图片中提取视觉信号。

依赖: pip install dashscope
环境变量: DASHSCOPE_API_KEY

当 API key 不存在或调用失败时静默跳过，不阻塞 pipeline。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from apps.intel_hub.schemas.content_frame import NoteContentFrame

logger = logging.getLogger(__name__)

_DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
_MODEL = "qwen-vl-max"

_SYSTEM_PROMPT = """你是一个电商视觉分析专家。请分析给定的小红书笔记图片，提取以下维度的视觉信号。

必须返回严格的 JSON 格式（不要加任何解释文字），字段如下：

{
  "visual_style_signals": ["风格标签，如：奶油风、ins风、北欧风、法式、复古风、原木风、日系"],
  "visual_scene_signals": ["场景标签，如：餐桌、书桌、茶几、出租屋、拍照布景、宿舍"],
  "visual_composition_types": ["构图类型，如：俯拍、平拍、局部特写、全景、对比图"],
  "visual_color_palette": ["色彩特征，如：低饱和、暖白、木色、高对比、柔和"],
  "visual_texture_signals": ["材质/质感，如：棉麻质感、PVC光泽、皮革纹理、蕾丝、柔软"],
  "visual_expression_patterns": ["表达模式，如：氛围图、功能说明图、前后对比、产品特写、场景搭配"]
}

每个字段返回 0-5 个标签。只返回 JSON，不要任何其他文字。"""


def is_vision_available() -> bool:
    """检查千问 VL 是否可用（API key 存在且 SDK 可导入）。"""
    if not _DASHSCOPE_API_KEY:
        return False
    try:
        import dashscope  # noqa: F401
        return True
    except ImportError:
        return False


def analyze_note_images(
    frame: NoteContentFrame,
    *,
    max_images: int = 2,
) -> dict[str, list[str]]:
    """用千问 VL 分析笔记图片，返回视觉信号字段 dict。

    Args:
        frame: 已解析的笔记内容帧
        max_images: 最多分析几张图（控制 API 成本）

    Returns:
        包含 visual_*_signals 字段的 dict，失败时返回空 dict
    """
    if not is_vision_available():
        return {}

    image_urls = frame.image_list[:max_images]
    if not image_urls:
        return {}

    try:
        return _call_qwen_vl(image_urls, frame.title_text)
    except Exception:
        logger.warning("visual_analyzer: failed for note %s, skipping", frame.note_id, exc_info=True)
        return {}


def _call_qwen_vl(image_urls: list[str], title_hint: str) -> dict[str, list[str]]:
    """调用千问 VL API 分析图片。"""
    import dashscope
    from dashscope import MultiModalConversation

    dashscope.api_key = _DASHSCOPE_API_KEY

    content: list[dict[str, Any]] = []
    for url in image_urls:
        content.append({"image": url})
    content.append({
        "text": f"笔记标题: {title_hint}\n\n请分析以上图片的视觉信号。"
    })

    messages = [
        {"role": "system", "content": [{"text": _SYSTEM_PROMPT}]},
        {"role": "user", "content": content},
    ]

    response = MultiModalConversation.call(
        model=_MODEL,
        messages=messages,
    )

    if response.status_code != 200:
        logger.warning(
            "visual_analyzer: API returned status %d: %s",
            response.status_code,
            response.message,
        )
        return {}

    raw_text = ""
    try:
        raw_text = response.output.choices[0].message.content[0]["text"]
    except (IndexError, KeyError, TypeError):
        logger.warning("visual_analyzer: unexpected response structure")
        return {}

    return _parse_vision_response(raw_text)


def _parse_vision_response(raw_text: str) -> dict[str, list[str]]:
    """从千问 VL 返回的文本中解析 JSON。"""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("visual_analyzer: failed to parse JSON from response: %s", text[:200])
        return {}

    valid_keys = {
        "visual_style_signals",
        "visual_scene_signals",
        "visual_composition_types",
        "visual_color_palette",
        "visual_texture_signals",
        "visual_expression_patterns",
    }

    result: dict[str, list[str]] = {}
    for key in valid_keys:
        value = data.get(key, [])
        if isinstance(value, list):
            result[key] = [str(v) for v in value if v]
        elif isinstance(value, str):
            result[key] = [value] if value else []
    return result
