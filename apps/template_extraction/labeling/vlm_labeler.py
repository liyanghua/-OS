"""VLM 辅助标注（当前为 mock：在规则结果上微调置信度与标注模式）。"""

from __future__ import annotations

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.template_extraction.schemas.labels import LabelResult
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled

from apps.template_extraction.labeling.rule_labeler import label_note_by_rules


def _call_vlm_for_labels(image_urls: list[str], title: str, body: str) -> dict:
    """预留 VLM 调用接口，当前返回空结果。"""
    return {}


def _bump_result(lr: LabelResult) -> LabelResult:
    return LabelResult(
        label_id=lr.label_id,
        confidence=min(1.0, round(lr.confidence + 0.1, 4)),
        evidence_snippet=lr.evidence_snippet,
        labeler_mode="vlm",
        human_override=lr.human_override,
    )


def label_note_by_vlm(parsed_note: XHSParsedNote) -> XHSNoteLabeled:
    """VLM 辅助标注（当前为 mock 实现）。"""
    urls = [f.url for f in parsed_note.parsed_images if getattr(f, "url", None)]
    _call_vlm_for_labels(
        image_urls=urls,
        title=parsed_note.normalized_title,
        body=parsed_note.normalized_body,
    )

    base = label_note_by_rules(parsed_note)
    return XHSNoteLabeled(
        note_id=base.note_id,
        cover_task_labels=[_bump_result(x) for x in base.cover_task_labels],
        gallery_task_labels=[_bump_result(x) for x in base.gallery_task_labels],
        visual_structure_labels=[_bump_result(x) for x in base.visual_structure_labels],
        business_semantic_labels=[_bump_result(x) for x in base.business_semantic_labels],
        risk_labels=[_bump_result(x) for x in base.risk_labels],
        labeler_version=base.labeler_version,
        labeled_at=base.labeled_at,
    )
