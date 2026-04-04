"""从解析笔记 + 标注构建封面/图组特征包并可落盘 JSONL。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.template_extraction.features.gallery_analyzer import analyze_gallery
from apps.template_extraction.features.image_features import (
    detect_elements_from_text,
    extract_image_features,
)
from apps.template_extraction.features.label_features import vectorize_labels
from apps.template_extraction.features.text_features import extract_text_features
from apps.template_extraction.schemas.cover_features import CoverFeaturePack
from apps.template_extraction.schemas.gallery_features import GalleryFeaturePack
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled

logger = logging.getLogger(__name__)


def _cover_image_url(note: XHSParsedNote) -> str | None:
    frames = note.parsed_images
    if frames:
        cover = next((f for f in frames if getattr(f, "is_cover", False)), None)
        if cover and getattr(cover, "url", None):
            return cover.url
        ordered = sorted(frames, key=lambda f: getattr(f, "index", 0))
        if ordered and getattr(ordered[0], "url", None):
            return ordered[0].url
    url = getattr(note.raw_note, "cover_image", None)
    return url if url else None


def _visual_ids(labeled: XHSNoteLabeled) -> set[str]:
    return {r.label_id for r in labeled.visual_structure_labels if getattr(r, "label_id", None)}


def _dominant_color_vector(colors: list[str] | None) -> list[float] | None:
    if not colors:
        return None
    if any(c.lower() == "warm" for c in colors):
        return [0.92, 0.72, 0.55]
    return None


def _object_count_estimate(elements: dict[str, bool]) -> float:
    keys = (
        "has_food",
        "has_tableware",
        "has_flower",
        "has_candle",
        "has_people",
        "has_festival_props",
    )
    return float(sum(1 for k in keys if elements.get(k)))


def _build_cover_pack(
    parsed: XHSParsedNote,
    labeled: XHSNoteLabeled,
) -> CoverFeaturePack:
    title = parsed.normalized_title
    body = parsed.normalized_body
    img = extract_image_features(_cover_image_url(parsed))
    el = detect_elements_from_text(title, body)
    txt = extract_text_features(title, body, config_path=None)
    vecs = vectorize_labels(labeled)
    vids = _visual_ids(labeled)

    def _or_visual(detect: bool, *label_names: str) -> bool:
        return detect or bool(vids.intersection(set(label_names)))

    tablecloth_ratio = 0.0
    if "has_tablecloth_main" in vids:
        tablecloth_ratio = 0.85
    elif "cloth_full_spread" in vids:
        tablecloth_ratio = 0.9
    elif "cloth_partial_visible" in vids:
        tablecloth_ratio = 0.45

    food_ratio = 0.65 if _or_visual(el["has_food"], "has_food") else 0.0
    tableware_ratio = 0.55 if _or_visual(el["has_tableware"], "has_tableware") else 0.0
    festival_ratio = 0.5 if _or_visual(el["has_festival_props"], "has_festival_props", "has_gift_box") else 0.0

    return CoverFeaturePack(
        img_embedding_cover=img.get("img_embedding"),
        dominant_color_vector=_dominant_color_vector(img.get("dominant_colors")),
        brightness_score=float(img.get("brightness_score", 0.5)),
        contrast_score=float(img.get("contrast_score", 0.5)),
        text_area_ratio=float(img.get("text_area_ratio", 0.0)),
        object_count_estimate=_object_count_estimate(el),
        tablecloth_area_ratio=tablecloth_ratio,
        food_area_ratio=food_ratio,
        tableware_area_ratio=tableware_ratio,
        festival_prop_ratio=festival_ratio,
        is_topdown=_or_visual(el["is_topdown"], "shot_topdown"),
        is_closeup=_or_visual(el["is_closeup"], "shot_closeup"),
        is_full_table_scene=_or_visual(el["is_full_scene"], "shot_wide_scene", "composition_dense"),
        is_room_context="has_chair_or_room_bg" in vids,
        is_texture_focused="cloth_texture_emphasis" in vids,
        is_style_focused=bool({"text_style_label", "cloth_pattern_emphasis"} & vids),
        has_food_visible=_or_visual(el["has_food"], "has_food"),
        has_flower_vase_visible=_or_visual(el["has_flower"], "has_flower_vase"),
        has_tableware_visible=_or_visual(el["has_tableware"], "has_tableware"),
        has_festival_element_visible=_or_visual(
            el["has_festival_props"],
            "has_festival_props",
            "has_gift_box",
        ),
        title_embedding=txt.get("title_embedding"),
        title_keyword_vector=None,
        body_intro_embedding=None,
        kw_style=bool(txt.get("kw_style")),
        kw_scene=bool(txt.get("kw_scene")),
        kw_price=bool(txt.get("kw_price")),
        kw_event=bool(txt.get("kw_event")),
        kw_upgrade=bool(txt.get("kw_upgrade")),
        kw_gift=bool(txt.get("kw_gift")),
        kw_aesthetic=bool(txt.get("kw_aesthetic")),
        task_label_vector=vecs["task_label_vector"],
        visual_label_vector=vecs["visual_label_vector"],
        semantic_label_vector=vecs["semantic_label_vector"],
        risk_label_vector=vecs["risk_label_vector"],
    )


def run_feature_pipeline(
    labeled_notes: list[tuple[XHSParsedNote, XHSNoteLabeled]],
    output_dir: str | None = None,
) -> list[tuple[CoverFeaturePack, GalleryFeaturePack]]:
    """对每条笔记生成封面特征包与图组特征包；可选写入 JSONL。"""
    out: list[tuple[CoverFeaturePack, GalleryFeaturePack]] = []
    total = len(labeled_notes)
    logger.info("feature_pipeline 开始，笔记数=%s", total)

    cover_lines: list[dict[str, Any]] = []
    gallery_lines: list[dict[str, Any]] = []

    for i, (parsed, labeled) in enumerate(labeled_notes, start=1):
        note_id = labeled.note_id
        logger.info("处理进度 %s/%s note_id=%s", i, total, note_id)

        cover = _build_cover_pack(parsed, labeled)
        gallery = analyze_gallery(parsed, labeled)
        out.append((cover, gallery))

        cover_lines.append({"note_id": note_id, **cover.model_dump(mode="json")})
        gallery_lines.append({"note_id": note_id, **gallery.model_dump(mode="json")})

    if output_dir:
        d = Path(output_dir)
        d.mkdir(parents=True, exist_ok=True)
        cover_path = d / "cover_features.jsonl"
        gallery_path = d / "gallery_features.jsonl"
        with cover_path.open("w", encoding="utf-8") as fc:
            for row in cover_lines:
                fc.write(json.dumps(row, ensure_ascii=False) + "\n")
        with gallery_path.open("w", encoding="utf-8") as fg:
            for row in gallery_lines:
                fg.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("已写入 %s 与 %s", cover_path, gallery_path)

    logger.info("feature_pipeline 完成，输出条数=%s", len(out))
    return out
