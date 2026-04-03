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
    ontology_mapping: Any = None
    opportunity_cards: list = field(default_factory=list)


def run_xhs_opportunity_pipeline(
    notes_dicts: list[dict[str, Any]],
    comment_index: dict[str, list[dict[str, Any]]] | None = None,
    ontology_config: dict[str, Any] | None = None,
    rules_config: dict[str, Any] | None = None,
) -> list[PipelineResult]:
    """运行完整流水线，返回每篇笔记的处理结果。"""
    from apps.intel_hub.compiler.opportunity_compiler import compile_xhs_opportunities
    from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
    from apps.intel_hub.extraction.selling_theme_extractor import extract_selling_theme_signals
    from apps.intel_hub.extraction.visual_extractor import extract_visual_signals
    from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note
    from apps.intel_hub.projector.ontology_projector import project_xhs_signals

    if ontology_config is None:
        ontology_config = _load_yaml(ROOT / "config" / "ontology_mapping.yaml")
    if rules_config is None:
        rules_config = _load_yaml(ROOT / "config" / "opportunity_rules.yaml")

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
        scene = extract_scene_signals(parsed)
        logger.info(
            "[%s] 信号提取 — 视觉:%d 卖点:%d 场景:%d",
            note_id,
            len(visual.visual_style_signals),
            len(selling.selling_point_signals),
            len(scene.scene_signals),
        )

        # Step 3: Ontology Mapping
        mapping = project_xhs_signals(visual, selling, scene, ontology_config)
        logger.info(
            "[%s] 本体映射 — 场景:%s 风格:%s 需求:%s 风险:%s",
            note_id,
            mapping.scene_refs,
            mapping.style_refs,
            mapping.need_refs,
            mapping.risk_refs,
        )

        # Step 4: Compile Opportunities
        cards = compile_xhs_opportunities(mapping, visual, selling, scene, rules_config)
        logger.info("[%s] 机会卡生成: %d 张", note_id, len(cards))

        results.append(PipelineResult(
            note_id=note_id,
            parsed_note=parsed,
            visual_signals=visual,
            selling_theme_signals=selling,
            scene_signals=scene,
            ontology_mapping=mapping,
            opportunity_cards=cards,
        ))

    total_cards = sum(len(r.opportunity_cards) for r in results)
    logger.info("流水线完成: %d 篇笔记 → %d 张机会卡", len(results), total_cards)
    return results


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_results(
    results: list[PipelineResult],
    output_dir: str | Path,
) -> None:
    """保存结果为 JSON 和 Markdown summary。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_cards: list[dict[str, Any]] = []
    for r in results:
        for card in r.opportunity_cards:
            all_cards.append(card.model_dump(mode="json"))

    json_path = output_dir / "opportunity_cards.json"
    json_path.write_text(json.dumps(all_cards, ensure_ascii=False, indent=2), encoding="utf-8")

    details: list[dict[str, Any]] = []
    for r in results:
        details.append({
            "note_id": r.note_id,
            "title": r.parsed_note.normalized_title if r.parsed_note else "",
            "visual_signals": r.visual_signals.model_dump(mode="json") if r.visual_signals else {},
            "selling_theme_signals": r.selling_theme_signals.model_dump(mode="json") if r.selling_theme_signals else {},
            "scene_signals": r.scene_signals.model_dump(mode="json") if r.scene_signals else {},
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

    jsonl_dir = args.jsonl_dir or str(ROOT / "third_party" / "MediaCrawler" / "data" / "xhs" / "jsonl")
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

    results = run_xhs_opportunity_pipeline(raw_dicts, comment_index=comment_index)
    save_results(results, output_dir)

    print(f"\n{'='*60}")
    print(f"处理完成: {len(results)} 篇笔记")
    total_cards = sum(len(r.opportunity_cards) for r in results)
    print(f"生成机会卡: {total_cards} 张")
    for r in results:
        if r.opportunity_cards:
            print(f"\n  [{r.note_id[:12]}] {r.parsed_note.normalized_title[:40] if r.parsed_note else ''}")
            for c in r.opportunity_cards:
                print(f"    → [{c.opportunity_type}] {c.title} (conf={c.confidence}, evidence={len(c.evidence_refs)})")
    print(f"\n输出目录: {output_dir}")


if __name__ == "__main__":
    main()
