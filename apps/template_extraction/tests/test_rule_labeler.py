"""规则标注器单测：10 条构造笔记的触发与证据一致性。"""

from __future__ import annotations

import pytest

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.intel_hub.schemas.xhs_raw import XHSNoteRaw
from apps.template_extraction.labeling.rule_labeler import label_note_by_rules
from apps.template_extraction.schemas.labels import LabelResult


def _parsed_note(note_id: str, title: str) -> XHSParsedNote:
    """构造最小 XHSParsedNote：parsed_images 为空，用 image_count 驱动图组启发式。"""
    raw = XHSNoteRaw(
        note_id=note_id,
        title_text=title,
        body_text="",
        tag_list=[],
        image_count=3,
        image_list=[],
    )
    return XHSParsedNote(
        raw_note=raw,
        normalized_title=title,
        normalized_body="",
        normalized_tags=[],
        parsed_images=[],
        engagement_summary={"total_engagement": 10, "like_count": 8, "collect_count": 1, "comment_count": 1},
    )


@pytest.fixture
def sample_parsed_notes() -> list[XHSParsedNote]:
    """10 条标题各异的笔记，覆盖风格/场景/价格/礼赠/纹理等触发面。"""
    titles = [
        "奶油风桌布｜氛围感拉满的周末早餐",
        "桌布特写｜蕾丝纹理超好看",
        "百元改造出租屋餐桌｜学生党必看",
        "圣诞桌搭指南｜节日氛围拉满",
        "5件套桌布搭配方案｜一键搞定",
        "ins风桌布开箱",
        "桌布使用前后对比",
        "Top10桌布推荐避坑指南",
        "下午茶桌搭｜高级感出片",
        "法式复古桌布",
    ]
    return [_parsed_note(f"note_{i + 1:02d}", t) for i, t in enumerate(titles)]


def _all_label_results(labeled) -> list[LabelResult]:
    return (
        labeled.cover_task_labels
        + labeled.gallery_task_labels
        + labeled.visual_structure_labels
        + labeled.business_semantic_labels
        + labeled.risk_labels
    )


def test_rule_labeler_ten_notes_cover_and_evidence(sample_parsed_notes: list[XHSParsedNote]) -> None:
    """每条笔记至少有一个封面任务标签；证据非空；模式均为 rule。"""
    assert len(sample_parsed_notes) == 10
    labeled_list = [label_note_by_rules(n) for n in sample_parsed_notes]

    for labeled in labeled_list:
        assert len(labeled.cover_task_labels) >= 1
        for lr in _all_label_results(labeled):
            assert lr.evidence_snippet.strip() != ""
            assert lr.labeler_mode == "rule"

    ids_note1 = {x.label_id for x in labeled_list[0].cover_task_labels}
    assert "scene_seed" in ids_note1 or "style_anchor" in ids_note1

    ids_note3 = {x.label_id for x in labeled_list[2].cover_task_labels}
    assert "price_value" in ids_note3

    ids_note4 = {x.label_id for x in labeled_list[3].cover_task_labels}
    assert "gift_event" in ids_note4
