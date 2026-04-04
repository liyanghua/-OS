"""标签枚举与 XHSNoteLabeled / LabelResult 模型单测。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.template_extraction.schemas.labels import (
    BusinessSemanticLabel,
    CoverTaskLabel,
    GalleryTaskLabel,
    LabelResult,
    VisualStructureLabel,
)
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled


def test_four_enum_classes_expected_members() -> None:
    """四个枚举类包含与产品约定一致的成员（与 labels.py 定义对齐）。"""
    assert {m.value for m in CoverTaskLabel} == {
        "hook_click",
        "scene_seed",
        "style_anchor",
        "texture_detail",
        "feature_explain",
        "price_value",
        "gift_event",
        "set_combo",
        "before_after",
        "shopping_guide",
    }
    assert {m.value for m in GalleryTaskLabel} == {
        "cover_hook",
        "style_expand",
        "texture_expand",
        "usage_expand",
        "guide_expand",
    }
    assert VisualStructureLabel.shot_topdown.value == "shot_topdown"
    assert VisualStructureLabel.lighting_dramatic.value == "lighting_dramatic"
    assert len(list(VisualStructureLabel)) >= 30
    assert {m.value for m in BusinessSemanticLabel} == {
        "mood_daily_healing",
        "mood_refined_life",
        "mood_brunch_afternoontea",
        "mood_friends_gathering",
        "mood_festival_setup",
        "mood_anniversary",
        "mood_low_cost_upgrade",
        "mood_small_space_upgrade",
        "mood_photo_friendly",
        "mood_style_identity",
        "mood_giftable",
        "mood_practical_value",
    }


def test_label_result_valid_creation() -> None:
    """LabelResult 可用合法字段构造。"""
    lr = LabelResult(
        label_id="scene_seed",
        confidence=0.85,
        evidence_snippet="氛围感",
        labeler_mode="rule",
        human_override=False,
    )
    assert lr.label_id == "scene_seed"
    assert lr.confidence == 0.85
    assert lr.evidence_snippet == "氛围感"
    assert lr.labeler_mode == "rule"
    assert lr.human_override is False


def test_label_result_confidence_bounds() -> None:
    """置信度须在 [0.0, 1.0] 内，越界应校验失败。"""
    LabelResult(label_id="x", confidence=0.0)
    LabelResult(label_id="x", confidence=1.0)
    with pytest.raises(ValidationError):
        LabelResult(label_id="x", confidence=-0.01)
    with pytest.raises(ValidationError):
        LabelResult(label_id="x", confidence=1.01)


def test_xhs_note_labeled_defaults_and_populated() -> None:
    """XHSNoteLabeled 默认空列表与显式填充字段行为正确。"""
    minimal = XHSNoteLabeled(note_id="n1")
    assert minimal.note_id == "n1"
    assert minimal.cover_task_labels == []
    assert minimal.gallery_task_labels == []
    assert minimal.labeler_version == "v1"

    full = XHSNoteLabeled(
        note_id="n2",
        cover_task_labels=[
            LabelResult(label_id="style_anchor", confidence=0.6, evidence_snippet="奶油风")
        ],
        gallery_task_labels=[
            LabelResult(label_id="cover_hook", confidence=0.5, evidence_snippet="首图")
        ],
        visual_structure_labels=[],
        business_semantic_labels=[
            LabelResult(label_id="mood_photo_friendly", confidence=0.4, evidence_snippet="出片")
        ],
        risk_labels=[],
        labeler_version="v2-test",
    )
    assert full.note_id == "n2"
    assert len(full.cover_task_labels) == 1
    assert full.cover_task_labels[0].label_id == "style_anchor"
    assert full.labeler_version == "v2-test"
