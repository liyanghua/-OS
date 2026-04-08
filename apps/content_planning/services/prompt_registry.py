"""Prompt Registry：从 YAML 配置加载 LLM 提示词，替代硬编码。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "config" / "prompts"
_cache: dict[str, dict[str, Any]] = {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.warning("Prompt config not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_prompt(scene: str, variant: str = "default") -> dict[str, str]:
    """Load prompt config for a scene.

    Returns dict with keys: system, user_template, output_hint (all str).
    Supports {variable} placeholders in user_template for later .format() calls.
    """
    cache_key = f"{scene}:{variant}"
    if cache_key in _cache:
        return _cache[cache_key]

    path = _PROMPTS_DIR / f"{scene}.yaml"
    data = _load_yaml(path)

    variants = data.get("variants", {})
    chosen = variants.get(variant, variants.get("default", {}))

    result = {
        "system": chosen.get("system", data.get("system", "")),
        "user_template": chosen.get("user_template", data.get("user_template", "")),
        "output_hint": chosen.get("output_hint", data.get("output_hint", "")),
    }
    _cache[cache_key] = result
    return result


def reset_cache() -> None:
    _cache.clear()
