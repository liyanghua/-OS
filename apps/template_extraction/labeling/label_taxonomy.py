"""从 YAML 加载标签体系，并提供触发词与全量标签 ID 集合。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_taxonomy_cache: dict[str, dict[str, Any]] = {}


def _default_config_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "config"
        / "template_extraction"
        / "label_taxonomy.yaml"
    )


def load_taxonomy(config_path: str | Path | None = None) -> dict[str, Any]:
    """加载 label_taxonomy.yaml，返回完整文档 dict。"""
    path = Path(config_path) if config_path is not None else _default_config_path()
    key = str(path.resolve())
    if key not in _taxonomy_cache:
        with path.open(encoding="utf-8") as f:
            _taxonomy_cache[key] = yaml.safe_load(f) or {}
    return _taxonomy_cache[key]


def get_trigger_keywords(label_id: str) -> list[str]:
    """返回某 label_id 在 YAML 中声明的 trigger_keywords；无则空列表。"""
    layers = load_taxonomy().get("layers") or {}
    for _layer_name, section in layers.items():
        if not isinstance(section, dict):
            continue
        entry = section.get(label_id)
        if not isinstance(entry, dict):
            continue
        raw = entry.get("trigger_keywords")
        if isinstance(raw, list):
            return [str(x) for x in raw]
    return []


def _default_layers() -> dict[str, Any]:
    return load_taxonomy().get("layers") or {}


_dl = _default_layers()
ALL_COVER_TASK_LABELS: set[str] = set((_dl.get("L1_cover_task") or {}).keys())
ALL_GALLERY_TASK_LABELS: set[str] = set((_dl.get("L1_gallery_task") or {}).keys())
ALL_VISUAL_LABELS: set[str] = set((_dl.get("L2_visual_structure") or {}).keys())
ALL_SEMANTIC_LABELS: set[str] = set((_dl.get("L3_business_semantic") or {}).keys())
ALL_RISK_LABELS: set[str] = set((_dl.get("L4_risk") or {}).keys())
