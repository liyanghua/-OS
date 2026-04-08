"""Prompt Registry：从 YAML 配置加载 LLM 提示词，替代硬编码。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "config" / "prompts"
_CATEGORIES_DIR = Path(__file__).resolve().parents[3] / "config" / "categories"
_cache: dict[str, dict[str, Any]] = {}
_category_cache: dict[str, dict[str, Any]] = {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.warning("Prompt config not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_prompt(
    scene: str,
    variant: str = "default",
    category: str | None = None,
) -> dict[str, str]:
    """Load prompt config for a scene.

    Returns dict with keys: system, user_template, output_hint (all str).
    Supports {variable} placeholders in user_template for later .format() calls.
    When ``category`` is set, ``prompt_fragments`` from that category YAML are merged
    via ``str.format`` so templates can reference e.g. ``{category_context}``.
    """
    cache_key = f"{scene}:{variant}"
    if cache_key in _cache:
        base = _cache[cache_key]
    else:
        path = _PROMPTS_DIR / f"{scene}.yaml"
        data = _load_yaml(path)

        variants = data.get("variants", {})
        chosen = variants.get(variant, variants.get("default", {}))

        base = {
            "system": chosen.get("system", data.get("system", "")),
            "user_template": chosen.get("user_template", data.get("user_template", "")),
            "output_hint": chosen.get("output_hint", data.get("output_hint", "")),
        }
        _cache[cache_key] = base

    if category is None:
        return base

    cat_config = load_category(category)
    fragments = cat_config.get("prompt_fragments", {})

    result: dict[str, str] = {}
    for key, val in base.items():
        if isinstance(val, str):
            try:
                result[key] = val.format(**fragments)
            except KeyError:
                result[key] = val
        else:
            result[key] = val

    return result


def load_category(category: str) -> dict[str, Any]:
    """Load category configuration."""
    if category in _category_cache:
        return _category_cache[category]
    path = _CATEGORIES_DIR / f"{category}.yaml"
    data = _load_yaml(path)
    _category_cache[category] = data
    return data


def load_prompt_with_category(
    scene: str,
    variant: str = "default",
    category: str | None = None,
) -> dict[str, str]:
    """Load prompt config with optional category context injection.

    Three-level loading: scene YAML -> variant -> category fragments.
    """
    return load_prompt(scene, variant, category)


def reset_cache() -> None:
    _cache.clear()
    _category_cache.clear()
