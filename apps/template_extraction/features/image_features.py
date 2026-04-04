"""单图规则特征与从正文推断的视觉元素（无重依赖）。"""

from __future__ import annotations

from typing import Final

# 关键词：小写/原文混合，匹配时对中文用子串即可
_FOOD_KW: Final[tuple[str, ...]] = (
    "美食",
    "食物",
    "早餐",
    "午餐",
    "晚餐",
    "brunch",
    "蛋糕",
    "甜品",
    "咖啡",
    "餐点",
    "一人食",
    "二人餐",
    "聚餐",
    "下午茶",
)
_TABLEWARE_KW: Final[tuple[str, ...]] = (
    "餐具",
    "餐盘",
    "盘子",
    "碗",
    "杯",
    "刀叉",
    "筷子",
    "杯碟",
)
_FLOWER_KW: Final[tuple[str, ...]] = ("花", "花瓶", "花艺", "鲜花", "插花")
_CANDLE_KW: Final[tuple[str, ...]] = ("蜡烛", "烛台", "香薰烛")
_PEOPLE_KW: Final[tuple[str, ...]] = (
    "人",
    "出镜",
    "合影",
    "闺蜜",
    "朋友",
    "家人",
    "手模",
    "手部",
)
_FESTIVAL_KW: Final[tuple[str, ...]] = (
    "圣诞",
    "新年",
    "春节",
    "节日",
    "过年",
    "情人节",
    "生日派对",
    "气球",
    "彩带",
)
_TOPDOWN_KW: Final[tuple[str, ...]] = ("俯拍", "俯视", "顶视", "上帝视角", "俯瞰")
_CLOSEUP_KW: Final[tuple[str, ...]] = ("特写", "近景", "细节", "微距")
_FULL_SCENE_KW: Final[tuple[str, ...]] = (
    "全景",
    "完整",
    "整桌",
    "一桌",
    "全貌",
    "场景图",
)


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    h = haystack.lower()
    return any(n.lower() in h for n in needles)


def extract_image_features(image_url: str | None) -> dict:
    """提取单张图像特征（基础规则版，embedding 接口预留）。"""
    _ = image_url  # 预留：未来可下载图像做像素级特征
    return {
        "img_embedding": None,
        "dominant_colors": ["warm"],
        "brightness_score": 0.5,
        "contrast_score": 0.5,
        "text_area_ratio": 0.0,
    }


def detect_elements_from_text(title: str, body: str) -> dict[str, bool]:
    """从文本推断图像元素存在性。"""
    text = f"{title or ''} {body or ''}".strip()
    if not text:
        return {
            "has_food": False,
            "has_tableware": False,
            "has_flower": False,
            "has_candle": False,
            "has_people": False,
            "has_festival_props": False,
            "is_topdown": False,
            "is_closeup": False,
            "is_full_scene": False,
        }

    return {
        "has_food": _contains_any(text, _FOOD_KW),
        "has_tableware": _contains_any(text, _TABLEWARE_KW),
        "has_flower": _contains_any(text, _FLOWER_KW),
        "has_candle": _contains_any(text, _CANDLE_KW),
        "has_people": _contains_any(text, _PEOPLE_KW),
        "has_festival_props": _contains_any(text, _FESTIVAL_KW),
        "is_topdown": _contains_any(text, _TOPDOWN_KW),
        "is_closeup": _contains_any(text, _CLOSEUP_KW),
        "is_full_scene": _contains_any(text, _FULL_SCENE_KW),
    }
