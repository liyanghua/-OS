"""从标题与正文抽取关键词布尔特征（YAML 规则）。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RULES_PATH = _REPO_ROOT / "config" / "template_extraction" / "feature_rules.yaml"

_KW_GROUP_KEYS = (
    "kw_style",
    "kw_scene",
    "kw_price",
    "kw_event",
    "kw_upgrade",
    "kw_gift",
    "kw_aesthetic",
)


def _load_rules(config_path: str | Path | None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _DEFAULT_RULES_PATH
    if not path.is_file():
        logger.warning("feature_rules 未找到: %s，使用空规则", path)
        return {"keyword_groups": {}}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {"keyword_groups": {}}


def extract_text_features(title: str, body: str, config_path: str | None = None) -> dict:
    """基于 feature_rules.yaml 的 keyword_groups 匹配标题+正文。"""
    data = _load_rules(config_path)
    groups = data.get("keyword_groups") or {}
    if not isinstance(groups, dict):
        groups = {}

    text = f"{title or ''} {body or ''}".strip()
    matched_keywords: dict[str, list[str]] = {k: [] for k in _KW_GROUP_KEYS}
    flags: dict[str, bool] = {k: False for k in _KW_GROUP_KEYS}

    for key in _KW_GROUP_KEYS:
        entry = groups.get(key)
        if not isinstance(entry, dict):
            continue
        kws = entry.get("keywords") or []
        if not isinstance(kws, list):
            continue
        hits: list[str] = []
        for raw in kws:
            if not isinstance(raw, str) or not raw.strip():
                continue
            kw = raw.strip()
            if kw and kw in text:
                hits.append(kw)
        matched_keywords[key] = hits
        flags[key] = len(hits) > 0

    return {
        "title_embedding": None,
        "kw_style": flags["kw_style"],
        "kw_scene": flags["kw_scene"],
        "kw_price": flags["kw_price"],
        "kw_event": flags["kw_event"],
        "kw_upgrade": flags["kw_upgrade"],
        "kw_gift": flags["kw_gift"],
        "kw_aesthetic": flags["kw_aesthetic"],
        "matched_keywords": matched_keywords,
    }
