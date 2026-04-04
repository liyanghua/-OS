"""批量标注入口：规则 / VLM mock / 融合。"""

from __future__ import annotations

import logging
from pathlib import Path

from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.template_extraction.schemas.labels import LabelResult
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled

from apps.template_extraction.labeling.rule_labeler import label_note_by_rules
from apps.template_extraction.labeling.vlm_labeler import label_note_by_vlm

logger = logging.getLogger(__name__)


def _merge_label_lists(a: list[LabelResult], b: list[LabelResult]) -> list[LabelResult]:
    """同一 label_id 保留置信度更高的一条，标注模式记为 ensemble。"""
    merged: dict[str, LabelResult] = {}
    for lr in a + b:
        cur = merged.get(lr.label_id)
        if cur is not None and cur.confidence >= lr.confidence:
            winner = cur
        else:
            winner = lr
        merged[lr.label_id] = LabelResult(
            label_id=winner.label_id,
            confidence=winner.confidence,
            evidence_snippet=winner.evidence_snippet,
            labeler_mode="ensemble",
            human_override=winner.human_override,
        )
    return list(merged.values())


def _merge_labeled(rule_note: XHSNoteLabeled, vlm_note: XHSNoteLabeled) -> XHSNoteLabeled:
    return XHSNoteLabeled(
        note_id=rule_note.note_id,
        cover_task_labels=_merge_label_lists(rule_note.cover_task_labels, vlm_note.cover_task_labels),
        gallery_task_labels=_merge_label_lists(rule_note.gallery_task_labels, vlm_note.gallery_task_labels),
        visual_structure_labels=_merge_label_lists(
            rule_note.visual_structure_labels, vlm_note.visual_structure_labels
        ),
        business_semantic_labels=_merge_label_lists(
            rule_note.business_semantic_labels, vlm_note.business_semantic_labels
        ),
        risk_labels=_merge_label_lists(rule_note.risk_labels, vlm_note.risk_labels),
        labeler_version=rule_note.labeler_version,
        labeled_at=vlm_note.labeled_at,
    )


def run_labeling_pipeline(
    notes: list[XHSParsedNote],
    mode: str = "rule",
    output_dir: str | None = None,
) -> list[XHSNoteLabeled]:
    """对笔记列表跑标注流水线，可选写出 JSONL。"""
    mode_norm = (mode or "rule").strip().lower()
    out: list[XHSNoteLabeled] = []
    total = len(notes)
    logger.info("labeling_pipeline start mode=%s notes=%s", mode_norm, total)

    for i, note in enumerate(notes, start=1):
        if mode_norm == "rule":
            labeled = label_note_by_rules(note)
        elif mode_norm == "vlm":
            labeled = label_note_by_vlm(note)
        elif mode_norm == "ensemble":
            labeled = _merge_labeled(label_note_by_rules(note), label_note_by_vlm(note))
        else:
            raise ValueError(f"Unsupported mode: {mode!r}; use rule|vlm|ensemble")

        out.append(labeled)
        if i % max(1, total // 10) == 0 or i == total:
            logger.info("labeling_pipeline progress %s/%s note_id=%s", i, total, note.note_id)

    if output_dir:
        p = Path(output_dir)
        p.mkdir(parents=True, exist_ok=True)
        jsonl_path = p / "labeled_notes.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as f:
            for row in out:
                f.write(row.model_dump_json() + "\n")
        logger.info("labeling_pipeline wrote %s rows -> %s", len(out), jsonl_path)

    logger.info("labeling_pipeline done mode=%s count=%s", mode_norm, len(out))
    return out
