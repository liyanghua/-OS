"""图组结构、一致性与互动特征。"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.template_extraction.features.label_features import vectorize_labels
from apps.template_extraction.schemas.gallery_features import GalleryFeaturePack
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled
from apps.template_extraction.schemas.labels import CoverTaskLabel

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RULES_PATH = _REPO_ROOT / "config" / "template_extraction" / "feature_rules.yaml"


def _load_role_keywords() -> dict[str, list[str]]:
    path = _DEFAULT_RULES_PATH
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    rk = data.get("role_keywords") if isinstance(data, dict) else None
    if not isinstance(rk, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in rk.items():
        if isinstance(v, list):
            out[str(k)] = [str(x).strip() for x in v if str(x).strip()]
    return out


def _label_ids_flat(labeled: XHSNoteLabeled) -> set[str]:
    s: set[str] = set()
    for lst in (
        labeled.cover_task_labels,
        labeled.gallery_task_labels,
        labeled.visual_structure_labels,
        labeled.business_semantic_labels,
        labeled.risk_labels,
    ):
        for r in lst:
            if getattr(r, "label_id", None):
                s.add(r.label_id)
    return s


def _style_signals_present(ids: set[str]) -> bool:
    if CoverTaskLabel.style_anchor.value in ids:
        return True
    style_markers = (
        "text_style_label",
        "cloth_pattern_emphasis",
    )
    if any(m in ids for m in style_markers):
        return True
    return any(x.startswith("palette_") for x in ids)


def _texture_signals_present(ids: set[str]) -> bool:
    if CoverTaskLabel.texture_detail.value in ids:
        return True
    return bool({"cloth_texture_emphasis", "shot_closeup"} & ids)


def _text_hits(text: str, kws: list[str]) -> bool:
    return any(kw and kw in text for kw in kws)


def _infer_cover_role(labeled: XHSNoteLabeled) -> str:
    best: tuple[float, str] = (-1.0, "")
    for r in labeled.cover_task_labels:
        c = float(getattr(r, "confidence", 0.0) or 0.0)
        lid = getattr(r, "label_id", "") or ""
        if lid and c >= best[0]:
            best = (c, lid)
    return best[1]


def _build_role_seq_top5(image_count: int, style_ok: bool, texture_ok: bool) -> list[str]:
    if image_count <= 0:
        return []
    n = min(5, image_count)
    seq: list[str] = []
    for i in range(n):
        pos = i + 1
        if pos == 1:
            seq.append("cover_hook")
        elif pos == 2:
            seq.append("style_expand" if style_ok else "usage_expand")
        elif pos == 3:
            seq.append("texture_expand" if texture_ok else "style_expand")
        elif pos == 4:
            seq.append("usage_expand")
        else:
            seq.append("guide_expand")
    return seq


def _engagement_proxy(engagement_summary: dict[str, Any]) -> float:
    total = int(engagement_summary.get("total_engagement") or 0)
    if total <= 0:
        return 0.0
    return min(1.0, math.log1p(total) / math.log1p(10_000))


def analyze_gallery(
    parsed_note: XHSParsedNote,
    labeled: XHSNoteLabeled,
) -> GalleryFeaturePack:
    """图组张数、角色序列、一致性占位、标签/文本推断的覆盖与互动比率。"""
    raw = parsed_note.raw_note
    image_count = len(parsed_note.parsed_images) if parsed_note.parsed_images else int(
        raw.image_count or 0
    )

    ids = _label_ids_flat(labeled)
    style_ok = _style_signals_present(ids)
    texture_ok = _texture_signals_present(ids)

    cover_role = _infer_cover_role(labeled)
    role_seq_top5 = _build_role_seq_top5(image_count, style_ok, texture_ok)

    text_blob = f"{parsed_note.normalized_title} {parsed_note.normalized_body}".strip()
    rk = _load_role_keywords()

    has_scene_image = bool(
        {"shot_wide_scene", "has_chair_or_room_bg"}.intersection(ids)
        or _text_hits(text_blob, rk.get("scene_image", []))
    )
    has_texture_closeup = bool(
        {"shot_closeup", "cloth_texture_emphasis"}.intersection(ids)
        or _text_hits(text_blob, rk.get("texture_closeup", []))
    )
    has_buying_guide = bool(
        {CoverTaskLabel.shopping_guide.value, "guide_expand"}.intersection(ids)
        or _text_hits(text_blob, rk.get("buying_guide", []))
    )
    has_before_after = bool(
        {CoverTaskLabel.before_after.value}.intersection(ids)
        or _text_hits(text_blob, rk.get("before_after", []))
    )
    has_set_combo = CoverTaskLabel.set_combo.value in ids

    es = parsed_note.engagement_summary or {}
    like_count = int(es.get("like_count", raw.like_count) or 0)
    save_count = int(es.get("collect_count", raw.collect_count) or 0)
    comment_count = int(es.get("comment_count", raw.comment_count) or 0)

    engagement_proxy_score = _engagement_proxy(es if isinstance(es, dict) else {})
    save_like_ratio = save_count / max(like_count, 1)
    comment_like_ratio = comment_count / max(like_count, 1)

    sem_vec = vectorize_labels(labeled)["semantic_label_vector"]

    return GalleryFeaturePack(
        img_embedding_top3_mean=None,
        image_count=image_count,
        cover_role=cover_role,
        role_seq_top5=role_seq_top5,
        style_consistency_score=0.7,
        color_consistency_score=0.7,
        scene_consistency_score=0.6,
        text_density_variance=0.2,
        has_scene_image=has_scene_image,
        has_texture_closeup=has_texture_closeup,
        has_buying_guide=has_buying_guide,
        has_before_after=has_before_after,
        has_set_combo=has_set_combo,
        like_count=like_count,
        save_count=save_count,
        comment_count=comment_count,
        engagement_proxy_score=engagement_proxy_score,
        save_like_ratio=save_like_ratio,
        comment_like_ratio=comment_like_ratio,
        semantic_label_vector=sem_vec,
    )
