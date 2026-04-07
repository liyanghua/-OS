"""英文本体 ID → 运营友好中文标签的集中式映射。

映射来源：
1. config/ontology_mapping.yaml 各 section 的 keywords[0]
2. 硬编码补充：template_hints、value_propositions、opportunity_type、brief_status
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[3]
_YAML_SECTIONS = (
    "scenes",
    "styles",
    "needs",
    "risk_factors",
    "materials",
    "content_patterns",
    "visual_patterns",
    "audiences",
)

_EXTRA_MAP: dict[str, str] = {
    # template_hints
    "scene_seed": "场景种草",
    "style_anchor": "风格定锚",
    "texture_proof": "质感佐证",
    "budget_hero": "平价主打",
    "occasion_gift": "节庆礼赠",
    # value_propositions
    "vp_photogenic": "出片感",
    "vp_premium_feel": "高级感",
    "vp_easy_clean": "易清洁",
    "vp_affordable_upgrade": "平价升级",
    # opportunity_type
    "visual": "视觉",
    "demand": "需求",
    "product": "产品",
    "content": "内容",
    "scene": "场景",
    # brief_status
    "draft": "草稿",
    "generated": "已生成",
    "reviewed": "已审阅",
    "approved": "已定稿",
}

_cache: dict[str, str] | None = None


def _load_yaml() -> dict[str, Any]:
    import yaml

    path = _ROOT / "config" / "ontology_mapping.yaml"
    if not path.exists():
        logger.warning("label_zh: ontology_mapping.yaml not found at %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_map() -> dict[str, str]:
    mapping: dict[str, str] = dict(_EXTRA_MAP)
    cfg = _load_yaml()
    for section in _YAML_SECTIONS:
        items = cfg.get(section, {})
        if not isinstance(items, dict):
            continue
        for ref_id, definition in items.items():
            if ref_id in mapping:
                continue
            kws = definition.get("keywords") if isinstance(definition, dict) else None
            if kws and isinstance(kws, list) and kws[0]:
                mapping[ref_id] = str(kws[0])
    return mapping


def _get_map() -> dict[str, str]:
    global _cache
    if _cache is None:
        _cache = _build_map()
    return _cache


def to_zh(ref_id: str) -> str:
    """将英文 ref id 转为中文标签。支持 '+' 组合串。无映射时原样返回。"""
    if not ref_id:
        return ref_id
    m = _get_map()
    if ref_id in m:
        return m[ref_id]
    if "+" in ref_id:
        parts = ref_id.split("+")
        translated = [m.get(p.strip(), p.strip()) for p in parts]
        return "+".join(translated)
    return ref_id


def to_zh_list(ref_ids: list[str]) -> list[str]:
    """批量转换，保持顺序和去重。"""
    return [to_zh(r) for r in ref_ids]


def reset_cache() -> None:
    """测试用：清除缓存以强制重新加载。"""
    global _cache
    _cache = None
