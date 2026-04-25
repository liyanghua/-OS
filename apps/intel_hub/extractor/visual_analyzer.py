"""千问 VL 视觉分析模块 —— 类目感知版。

依赖: pip install dashscope
环境变量: DASHSCOPE_API_KEY

功能：
- 接收 CategoryLens，动态拼装类目感知的 system prompt
- 为每张图片返回结构化视觉信号（风格/场景/人物状态/信任信号/内容形式 ...）
- 按 lens.visual_prompt_hints.sample_strategy 选图
- 当 API key 缺失或调用失败时静默降级，不阻塞 pipeline
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from apps.intel_hub.domain.category_lens import CategoryLens
from apps.intel_hub.schemas.content_frame import NoteContentFrame

logger = logging.getLogger(__name__)

_DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
_MODEL = "qwen-vl-max"

_VALID_KEYS = {
    "visual_style_signals",
    "visual_scene_signals",
    "visual_composition_types",
    "visual_color_palette",
    "visual_texture_signals",
    "visual_expression_patterns",
    "visual_people_state",
    "visual_trust_signals",
    "visual_trust_risk_flags",
    "visual_content_formats",
    "visual_product_features",
    "visual_insight_notes",
}


def is_vision_available() -> bool:
    """检查千问 VL 是否可用（API key 存在且 SDK 可导入）。"""
    if not _DASHSCOPE_API_KEY:
        return False
    try:
        import dashscope  # noqa: F401
        return True
    except ImportError:
        return False


def build_system_prompt(lens: CategoryLens | None) -> str:
    """根据 CategoryLens 生成类目感知的 system prompt。

    未传入 lens 时使用通用模板，保持向后兼容。
    """
    category_cn = lens.category_cn if lens else "通用"
    focus = lens.visual_prompt_hints.focus if lens else []
    risks = lens.visual_prompt_hints.risk_flags if lens else []
    people_taxonomy = lens.visual_prompt_hints.people_state_taxonomy if lens else []
    trust_taxonomy = lens.visual_prompt_hints.trust_signal_taxonomy if lens else []
    format_taxonomy = lens.visual_prompt_hints.content_format_taxonomy if lens else []
    product_taxonomy = lens.product_feature_taxonomy if lens else []

    focus_hint = "、".join(focus) if focus else "整体氛围与产品特征"
    risk_hint = "、".join(risks) if risks else "过度精修、色差、塑料感"

    def _format_list(values: list[str], fallback: str) -> str:
        return "、".join(values) if values else fallback

    return f"""你是电商视觉分析专家，现在正在分析【{category_cn}】类目的小红书笔记图片。

请重点关注：{focus_hint}
需要特别警惕：{risk_hint}

请严格返回 JSON，每个字段为字符串数组（0-5 个标签），不要输出任何解释文字。字段含义：

{{
  "visual_style_signals": ["整体风格，如：奶油风、ins风、北欧风、法式；或：妈生感、韩剧、港风"],
  "visual_scene_signals": ["使用场景，如：餐桌、书桌、出租屋；或：通勤、约会、婚礼"],
  "visual_composition_types": ["构图类型，如：俯拍、近距离特写、前后对比、全景"],
  "visual_color_palette": ["色彩特征，如：低饱和、暖白、柔和、高对比"],
  "visual_texture_signals": ["材质/质感，如：棉麻、PVC、蕾丝、真发丝、高温丝"],
  "visual_expression_patterns": ["表达模式，如：氛围图、功能说明、前后对比、真人试戴"],
  "visual_people_state": ["人物状态，如：{_format_list(people_taxonomy, '无人物/模特/素人')}"],
  "visual_trust_signals": ["信任证据，如：{_format_list(trust_taxonomy, '近距离特写、无滤镜正面')}"],
  "visual_trust_risk_flags": ["信任风险，如：{risk_hint}"],
  "visual_content_formats": ["内容形式，如：{_format_list(format_taxonomy, '种草、测评、避坑、教程')}"],
  "visual_product_features": ["识别到的商品特征，参考：{_format_list(product_taxonomy, '材质/工艺/功能卖点')}"],
  "visual_insight_notes": ["一句话总结这组图片想讲述的故事"]
}}

只返回 JSON。"""


def sample_image_urls(
    frame: NoteContentFrame,
    *,
    lens: CategoryLens | None,
    max_images_fallback: int = 2,
) -> list[str]:
    """按 lens.visual_prompt_hints.sample_strategy 挑选图片 URL。

    - ``prefer_cover``: 封面优先并去重
    - ``prefer_first_and_last``: 若图片数 > max，取首 + 中间 + 末尾
    - ``max_images_per_note``: 控制成本，缺省 fallback
    """
    images = list(frame.image_list or [])
    if not images:
        return []

    strategy: dict[str, Any] = {}
    if lens is not None:
        strategy = dict(lens.visual_prompt_hints.sample_strategy or {})

    max_images = int(strategy.get("max_images_per_note") or max_images_fallback)
    prefer_cover = bool(strategy.get("prefer_cover", True))
    prefer_first_and_last = bool(strategy.get("prefer_first_and_last", False))

    selected: list[str] = []
    seen: set[str] = set()

    def _push(url: str) -> None:
        url = url.strip()
        if url and url not in seen:
            selected.append(url)
            seen.add(url)

    if prefer_cover and frame.cover_image:
        _push(frame.cover_image)

    if prefer_first_and_last and len(images) > max_images:
        _push(images[0])
        mid_idx = len(images) // 2
        _push(images[mid_idx])
        _push(images[-1])

    for url in images:
        if len(selected) >= max_images:
            break
        _push(url)

    return selected[:max_images]


def analyze_note_images(
    frame: NoteContentFrame,
    *,
    lens: CategoryLens | None = None,
    max_images: int = 2,
) -> dict[str, Any]:
    """用千问 VL 分析笔记图片，返回 CategoryLens 对齐的视觉信号 dict。

    - 返回字段参见 ``_VALID_KEYS``，其中 ``visual_insight_notes``
      为字符串（若模型返回数组会被拼接成一段文本），其余为字符串列表。
    - 失败时返回空 dict，**不抛出异常**。
    """
    if not is_vision_available():
        return {}

    urls = sample_image_urls(frame, lens=lens, max_images_fallback=max_images)
    if not urls:
        return {}

    try:
        return _call_qwen_vl(urls, frame.title_text, lens=lens)
    except Exception:
        logger.warning(
            "visual_analyzer: failed for note %s, skipping", frame.note_id, exc_info=True
        )
        return {}


def _call_qwen_vl(
    image_urls: list[str],
    title_hint: str,
    *,
    lens: CategoryLens | None,
) -> dict[str, Any]:
    """调用千问 VL API 分析图片。"""
    import dashscope
    from dashscope import MultiModalConversation

    dashscope.api_key = _DASHSCOPE_API_KEY

    content: list[dict[str, Any]] = []
    for url in image_urls:
        content.append({"image": url})
    hint_prefix = (
        f"【类目】{lens.category_cn}\n" if lens is not None else ""
    )
    content.append({
        "text": f"{hint_prefix}笔记标题：{title_hint}\n\n请按 system prompt 输出 JSON。"
    })

    messages = [
        {"role": "system", "content": [{"text": build_system_prompt(lens)}]},
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


def _parse_vision_response(raw_text: str) -> dict[str, Any]:
    """从千问 VL 返回的文本中解析 JSON。"""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "visual_analyzer: failed to parse JSON from response: %s", text[:200]
        )
        return {}

    result: dict[str, Any] = {}
    for key in _VALID_KEYS:
        value = data.get(key)
        if key == "visual_insight_notes":
            if isinstance(value, list):
                result[key] = "；".join(str(v) for v in value if v)
            elif isinstance(value, str):
                result[key] = value.strip()
            continue
        if isinstance(value, list):
            result[key] = [str(v) for v in value if v]
        elif isinstance(value, str) and value:
            result[key] = [value]
    return result
