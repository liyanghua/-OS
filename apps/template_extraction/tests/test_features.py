"""特征流水线相关函数单测：文本、标签向量、元素检测与图组分析。"""

from __future__ import annotations

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.intel_hub.schemas.xhs_raw import XHSNoteRaw
from apps.template_extraction.features.gallery_analyzer import analyze_gallery
from apps.template_extraction.features.image_features import detect_elements_from_text
from apps.template_extraction.features.label_features import vectorize_labels
from apps.template_extraction.features.text_features import extract_text_features
from apps.template_extraction.schemas.gallery_features import GalleryFeaturePack
from apps.template_extraction.schemas.labels import LabelResult
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled


def test_extract_text_features_various_inputs() -> None:
    """extract_text_features 对空串、仅标题、长正文均能返回稳定结构。"""
    for title, body in [
        ("", ""),
        ("奶油风桌布", ""),
        ("桌布", "百元平价改造出租屋 学生党必看"),
    ]:
        out = extract_text_features(title, body, config_path=None)
        assert "kw_style" in out
        assert "kw_scene" in out
        assert "matched_keywords" in out
        assert isinstance(out["kw_style"], bool)


def test_vectorize_labels_sample_labeled() -> None:
    """vectorize_labels 对 XHSNoteLabeled 产出四层 multi-hot，长度与枚举一致。"""
    labeled = XHSNoteLabeled(
        note_id="n1",
        cover_task_labels=[
            LabelResult(label_id="scene_seed", confidence=0.5, evidence_snippet="x", labeler_mode="rule")
        ],
        visual_structure_labels=[
            LabelResult(
                label_id="shot_topdown",
                confidence=0.5,
                evidence_snippet="y",
                labeler_mode="rule",
            )
        ],
        business_semantic_labels=[
            LabelResult(
                label_id="mood_photo_friendly",
                confidence=0.5,
                evidence_snippet="z",
                labeler_mode="rule",
            )
        ],
        risk_labels=[
            LabelResult(
                label_id="risk_too_generic",
                confidence=0.5,
                evidence_snippet="r",
                labeler_mode="rule",
            )
        ],
    )
    vecs = vectorize_labels(labeled)
    assert len(vecs["task_label_vector"]) == 10
    assert len(vecs["visual_label_vector"]) > 0
    assert sum(vecs["task_label_vector"]) >= 1.0
    assert any(v > 0 for v in vecs["visual_label_vector"])


def test_detect_elements_from_text() -> None:
    """detect_elements_from_text 根据关键词推断布尔元素标志。"""
    empty = detect_elements_from_text("", "")
    assert empty["has_food"] is False
    assert empty["is_closeup"] is False

    t = "俯拍早餐桌布特写 全景一桌"
    el = detect_elements_from_text(t, "")
    assert el["has_food"] is True
    assert el["is_topdown"] is True
    assert el["is_closeup"] is True
    assert el["is_full_scene"] is True


def test_analyze_gallery_returns_valid_pack() -> None:
    """analyze_gallery 返回符合 GalleryFeaturePack 的实例且字段合理。"""
    raw = XHSNoteRaw(
        note_id="g1",
        title_text="法式桌布",
        body_text="",
        image_count=5,
        image_list=[],
        like_count=100,
        collect_count=20,
        comment_count=5,
    )
    parsed = XHSParsedNote(
        raw_note=raw,
        normalized_title="法式桌布",
        normalized_body="",
        normalized_tags=[],
        parsed_images=[],
    )
    labeled = XHSNoteLabeled(
        note_id="g1",
        cover_task_labels=[
            LabelResult(label_id="style_anchor", confidence=0.7, evidence_snippet="法式", labeler_mode="rule")
        ],
    )
    pack = analyze_gallery(parsed, labeled)
    assert isinstance(pack, GalleryFeaturePack)
    assert pack.image_count == 5
    assert isinstance(pack.role_seq_top5, list)
    assert len(pack.semantic_label_vector) > 0
