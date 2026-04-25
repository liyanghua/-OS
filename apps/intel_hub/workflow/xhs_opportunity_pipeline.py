"""XHS 三维结构化机会卡流水线。

XHSNoteRaw -> XHSParsedNote -> VisualSignals / SellingThemeSignals / SceneSignals
-> OntologyMapping -> OpportunityCard

用法:
    python -m apps.intel_hub.workflow.xhs_opportunity_pipeline
    python -m apps.intel_hub.workflow.xhs_opportunity_pipeline --note-id <id>
    python -m apps.intel_hub.workflow.xhs_opportunity_pipeline --jsonl-dir path/to/dir
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class PipelineResult:
    """单篇笔记的流水线完整输出。"""

    note_id: str = ""
    parsed_note: Any = None
    visual_signals: Any = None
    selling_theme_signals: Any = None
    scene_signals: Any = None
    cross_modal_validation: Any = None
    ontology_mapping: Any = None
    opportunity_cards: list = field(default_factory=list)
    lens_id: str | None = None


@dataclass
class PipelineRunOutput:
    """流水线完整输出：单笔记 results + lens 聚合 bundles。"""

    results: list[PipelineResult] = field(default_factory=list)
    lens_bundles: dict[str, Any] = field(default_factory=dict)


def run_xhs_opportunity_pipeline(
    notes_dicts: list[dict[str, Any]],
    comment_index: dict[str, list[dict[str, Any]]] | None = None,
    ontology_config: dict[str, Any] | None = None,
    rules_config: dict[str, Any] | None = None,
    *,
    return_bundles: bool = False,
) -> list[PipelineResult] | PipelineRunOutput:
    """运行完整流水线，返回每篇笔记的处理结果。

    当 ``return_bundles=True`` 时返回 :class:`PipelineRunOutput`，其中包含按
    ``lens_id`` 分组的 :class:`LensInsightBundle`。默认保持向后兼容：返回 results 列表。
    """
    from apps.intel_hub.compiler.opportunity_compiler import compile_xhs_opportunities
    from apps.intel_hub.config_loader import load_category_lenses, route_keyword_to_lens_id
    from apps.intel_hub.engine.category_lens_engine import CategoryLensEngine, LensEngineInput
    from apps.intel_hub.extraction.cross_modal_validator import validate_cross_modal_consistency
    from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
    from apps.intel_hub.extraction.selling_theme_extractor import extract_selling_theme_signals
    from apps.intel_hub.extraction.visual_extractor import extract_visual_signals
    from apps.intel_hub.extractor import extract_business_signals
    from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
    from apps.intel_hub.projector.ontology_projector import project_xhs_signals
    from apps.intel_hub.schemas.content_frame import NoteContentFrame

    if ontology_config is None:
        ontology_config = _load_yaml(ROOT / "config" / "ontology_mapping.yaml")
    if rules_config is None:
        rules_config = _load_yaml(ROOT / "config" / "opportunity_rules.yaml")

    lenses = load_category_lenses()
    lens_engine_inputs: dict[str, list[Any]] = {}

    results: list[PipelineResult] = []

    for raw in notes_dicts:
        note_id = raw.get("note_id", "")
        if not note_id:
            continue

        comments = (comment_index or {}).get(str(note_id), [])

        # Step 1: Parse
        raw_note = parse_raw_note(raw, comments=comments)
        parsed = parse_note(raw_note)
        logger.info("[%s] 解析完成: %s (互动 %d)", note_id, parsed.normalized_title[:30], parsed.engagement_summary.get("total_engagement", 0))

        # Step 2: Extract
        visual = extract_visual_signals(parsed)
        selling = extract_selling_theme_signals(parsed)
        scene = extract_scene_signals(parsed, visual_signals=visual)
        logger.info(
            "[%s] 信号提取 — 视觉:%d 卖点:%d 场景:%d",
            note_id,
            len(visual.visual_style_signals),
            len(selling.selling_point_signals),
            len(scene.scene_signals),
        )

        # Step 2.5: Cross-modal validation
        validation = validate_cross_modal_consistency(visual, selling, scene, parsed)
        logger.info(
            "[%s] 跨模态校验 — 一致性:%.2f 高置信:%d 无支撑:%d 被质疑:%d",
            note_id,
            validation.overall_consistency_score or 0,
            len(validation.high_confidence_claims),
            len(validation.unsupported_claims),
            len(validation.challenged_claims),
        )

        # Step 3: Ontology Mapping (cross_modal 用于增补风险映射)
        mapping = project_xhs_signals(visual, selling, scene, ontology_config, cross_modal=validation)
        logger.info(
            "[%s] 本体映射 — 场景:%s 风格:%s 需求:%s 风险:%s VP:%s",
            note_id,
            mapping.scene_refs,
            mapping.style_refs,
            mapping.need_refs,
            mapping.risk_refs,
            mapping.value_proposition_refs[:3],
        )

        # Step 4: Compile Opportunities (cross_modal 用于评分调节, note_context 用于洞察)
        note_ctx: dict[str, Any] = {}
        if parsed:
            rn = parsed.raw_note
            note_ctx = {
                "like_count": rn.like_count,
                "collect_count": rn.collect_count,
                "comment_count": rn.comment_count,
                "share_count": rn.share_count,
            }
        cards = compile_xhs_opportunities(
            mapping, visual, selling, scene, rules_config,
            cross_modal=validation, note_context=note_ctx,
        )
        logger.info("[%s] 机会卡生成: %d 张", note_id, len(cards))

        # Lens 路由 + 聚合队列
        lens_id = raw.get("lens_id") or route_keyword_to_lens_id(raw.get("source_keyword") or raw.get("keyword"))
        lens = lenses.get(lens_id) if lens_id else None

        if lens is not None and lens_id:
            lens_frame = _build_lens_content_frame(raw_note, parsed)
            lens_bsf = extract_business_signals(lens_frame, lens=lens)
            lens_engine_inputs.setdefault(lens_id, []).append(
                LensEngineInput(frame=lens_frame, business_signals=lens_bsf)
            )

        results.append(PipelineResult(
            note_id=note_id,
            parsed_note=parsed,
            visual_signals=visual,
            selling_theme_signals=selling,
            scene_signals=scene,
            cross_modal_validation=validation,
            ontology_mapping=mapping,
            opportunity_cards=cards,
            lens_id=lens_id,
        ))

    total_cards = sum(len(r.opportunity_cards) for r in results)
    logger.info("流水线完成: %d 篇笔记 → %d 张机会卡", len(results), total_cards)

    # 类目透视聚合
    lens_bundles: dict[str, Any] = {}
    for lens_id, inputs in lens_engine_inputs.items():
        lens = lenses.get(lens_id)
        if lens is None or not inputs:
            continue
        try:
            bundle = CategoryLensEngine(lens).run(inputs)
            lens_bundles[lens_id] = bundle
            logger.info(
                "[lens:%s] 透视完成: 笔记=%d score=%.2f 决策=%s",
                lens_id,
                len(inputs),
                bundle.evidence_score.total,
                bundle.recommended_action.decision,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[lens:%s] CategoryLensEngine 失败: %s", lens_id, exc)

    # Phase F: 把 bundle 写回每张 card 的 lens_* 字段
    if lens_bundles:
        from apps.intel_hub.compiler.opportunity_compiler import (
            apply_lens_bundles_to_cards,
        )
        cards_by_note = {r.note_id: r.opportunity_cards for r in results if r.opportunity_cards}
        lens_id_by_note = {r.note_id: r.lens_id for r in results}
        apply_lens_bundles_to_cards(cards_by_note, lens_id_by_note, lens_bundles)

    if return_bundles:
        return PipelineRunOutput(results=results, lens_bundles=lens_bundles)
    return results


def _build_lens_content_frame(raw_note: Any, parsed: Any) -> Any:
    """从 XHSNoteRaw/XHSParsedNote 构造 V2 的 NoteContentFrame，供 LensEngine 使用。"""
    from apps.intel_hub.schemas.content_frame import CommentFrame, NoteContentFrame

    def _to_comment_frame(items: list[Any]) -> list[CommentFrame]:
        frames: list[CommentFrame] = []
        for c in items or []:
            frames.append(
                CommentFrame(
                    comment_id=str(getattr(c, "comment_id", "") or ""),
                    user_name=str(getattr(c, "nickname", "") or ""),
                    comment_text=str(getattr(c, "content", "") or ""),
                    like_count=int(getattr(c, "like_count", 0) or 0),
                )
            )
        return frames

    image_urls = [img.url for img in (raw_note.image_list or []) if getattr(img, "url", "")]

    return NoteContentFrame(
        note_id=raw_note.note_id,
        note_url=raw_note.note_url,
        author_id=raw_note.author_id,
        author_name=raw_note.author_name,
        published_at=raw_note.published_at or "",
        crawled_at=raw_note.crawled_at or "",
        platform=raw_note.platform,
        source_type=raw_note.source_type,
        title_text=raw_note.title_text,
        body_text=raw_note.body_text,
        tag_list=list(raw_note.tag_list or []),
        like_count=raw_note.like_count,
        comment_count=raw_note.comment_count,
        collect_count=raw_note.collect_count,
        share_count=raw_note.share_count,
        image_count=raw_note.image_count,
        cover_image=raw_note.cover_image,
        image_list=image_urls,
        comments=_to_comment_frame(raw_note.comments),
        top_comments=_to_comment_frame(raw_note.top_comments),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_results(
    results: list[PipelineResult],
    output_dir: str | Path,
    *,
    lens_bundles: dict[str, Any] | None = None,
) -> None:
    """保存结果为 JSON 和 Markdown summary。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if lens_bundles:
        bundles_dir = output_dir / "lens_bundles"
        bundles_dir.mkdir(parents=True, exist_ok=True)
        for lens_id, bundle in lens_bundles.items():
            payload = bundle.model_dump(mode="json") if hasattr(bundle, "model_dump") else bundle
            (bundles_dir / f"{lens_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    all_cards: list[dict[str, Any]] = []
    for r in results:
        for card in r.opportunity_cards:
            all_cards.append(card.model_dump(mode="json"))

    json_path = output_dir / "opportunity_cards.json"
    json_path.write_text(json.dumps(all_cards, ensure_ascii=False, indent=2), encoding="utf-8")

    details: list[dict[str, Any]] = []
    for r in results:
        note_ctx: dict[str, Any] = {}
        if r.parsed_note:
            rn = r.parsed_note.raw_note
            note_ctx = {
                "note_id": rn.note_id,
                "note_url": rn.note_url,
                "title": rn.title_text,
                "body": rn.body_text,
                "author_name": rn.author_name,
                "cover_image": rn.cover_image,
                "image_urls": [img.url for img in rn.image_list],
                "tag_list": rn.tag_list,
                "like_count": rn.like_count,
                "collect_count": rn.collect_count,
                "comment_count": rn.comment_count,
                "share_count": rn.share_count,
                "top_comments": [
                    {"nickname": c.nickname, "content": c.content, "like_count": c.like_count}
                    for c in rn.top_comments[:5]
                ],
            }
        details.append({
            "note_id": r.note_id,
            "title": r.parsed_note.normalized_title if r.parsed_note else "",
            "note_context": note_ctx,
            "visual_signals": r.visual_signals.model_dump(mode="json") if r.visual_signals else {},
            "selling_theme_signals": r.selling_theme_signals.model_dump(mode="json") if r.selling_theme_signals else {},
            "scene_signals": r.scene_signals.model_dump(mode="json") if r.scene_signals else {},
            "cross_modal_validation": r.cross_modal_validation.model_dump(mode="json") if r.cross_modal_validation else {},
            "ontology_mapping": r.ontology_mapping.model_dump(mode="json") if r.ontology_mapping else {},
            "opportunity_cards": [c.model_dump(mode="json") for c in r.opportunity_cards],
        })
    detail_path = output_dir / "pipeline_details.json"
    detail_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# XHS 机会卡流水线报告",
        f"\n生成时间: {datetime.now(timezone.utc).isoformat()}",
        f"\n## 总览\n",
        f"- 笔记数: {len(results)}",
        f"- 机会卡数: {len(all_cards)}",
        "",
    ]
    for r in results:
        title = r.parsed_note.normalized_title[:50] if r.parsed_note else "N/A"
        md_lines.append(f"### {r.note_id[:12]}... — {title}")
        md_lines.append(f"- 视觉信号: {r.visual_signals.visual_style_signals if r.visual_signals else []}")
        md_lines.append(f"- 卖点信号: {r.selling_theme_signals.selling_point_signals if r.selling_theme_signals else []}")
        md_lines.append(f"- 场景信号: {r.scene_signals.scene_signals if r.scene_signals else []}")
        md_lines.append(f"- 机会卡: {len(r.opportunity_cards)} 张")
        for card in r.opportunity_cards:
            md_lines.append(f"  - **[{card.opportunity_type}]** {card.title}")
            md_lines.append(f"    - 置信度: {card.confidence}")
            md_lines.append(f"    - 证据数: {len(card.evidence_refs)}")
            md_lines.append(f"    - 下一步: {card.suggested_next_step}")
        md_lines.append("")

    md_path = output_dir / "pipeline_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    logger.info("结果保存至: %s", output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="XHS 三维结构化机会卡流水线")
    parser.add_argument("--jsonl-dir", type=str, default=None, help="MediaCrawler JSONL 目录")
    parser.add_argument("--note-id", type=str, default=None, help="只处理指定 note_id")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录")
    args = parser.parse_args()

    _fixtures_dir = ROOT / "data" / "fixtures" / "mediacrawler_output" / "xhs" / "jsonl"
    _default_dir = ROOT / "third_party" / "MediaCrawler" / "data" / "xhs" / "jsonl"
    jsonl_dir = args.jsonl_dir or str(_fixtures_dir if _fixtures_dir.exists() else _default_dir)
    output_dir = args.output_dir or str(ROOT / "data" / "output" / "xhs_opportunities")

    from apps.intel_hub.parsing.xhs_note_parser import load_and_parse_notes
    parsed_notes = load_and_parse_notes(jsonl_dir)

    if args.note_id:
        parsed_notes = [n for n in parsed_notes if n.note_id == args.note_id]

    if not parsed_notes:
        logger.warning("没有找到可处理的笔记")
        sys.exit(1)

    raw_dicts: list[dict[str, Any]] = []
    comment_index: dict[str, list[dict[str, Any]]] = {}
    from collections import defaultdict
    import json as json_mod
    from pathlib import Path as P
    jsonl_path = P(jsonl_dir)
    for cf in sorted(jsonl_path.glob("search_comments_*.jsonl")):
        for line in cf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json_mod.loads(line)
                nid = item.get("note_id")
                if nid:
                    comment_index.setdefault(str(nid), []).append(item)
            except json_mod.JSONDecodeError:
                continue

    for cf in sorted(jsonl_path.glob("search_contents_*.jsonl")):
        for line in cf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json_mod.loads(line)
                if item.get("note_id"):
                    if args.note_id and item["note_id"] != args.note_id:
                        continue
                    raw_dicts.append(item)
            except json_mod.JSONDecodeError:
                continue

    if not raw_dicts:
        logger.warning("没有找到原始笔记数据")
        sys.exit(1)

    output = run_xhs_opportunity_pipeline(
        raw_dicts, comment_index=comment_index, return_bundles=True
    )
    results = output.results
    lens_bundles = output.lens_bundles
    save_results(results, output_dir, lens_bundles=lens_bundles)

    print(f"\n{'='*60}")
    print(f"处理完成: {len(results)} 篇笔记")
    total_cards = sum(len(r.opportunity_cards) for r in results)
    print(f"生成机会卡: {total_cards} 张")
    for r in results:
        if r.opportunity_cards:
            print(f"\n  [{r.note_id[:12]}] {r.parsed_note.normalized_title[:40] if r.parsed_note else ''}")
            for c in r.opportunity_cards:
                print(f"    → [{c.opportunity_type}] {c.title} (conf={c.confidence}, evidence={len(c.evidence_refs)})")
    if lens_bundles:
        print(f"\n类目透视 Bundle: {len(lens_bundles)}")
        for lens_id, bundle in lens_bundles.items():
            print(f"  - {lens_id}: 分数={bundle.evidence_score.total:.2f} 决策={bundle.recommended_action.decision}")
    print(f"\n输出目录: {output_dir}")


if __name__ == "__main__":
    main()
