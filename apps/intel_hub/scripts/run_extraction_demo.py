"""四维提取验证脚本 — 选取真实笔记，运行完整提取 + 跨模态校验，输出结构化结果。

用法:
    # 全量跑（前 5 篇）
    .venv/bin/python -m apps.intel_hub.scripts.run_extraction_demo

    # 指定笔记
    .venv/bin/python -m apps.intel_hub.scripts.run_extraction_demo --note-id <id>

    # 跑更多
    .venv/bin/python -m apps.intel_hub.scripts.run_extraction_demo --max-notes 10

    # 禁用 VLM（仅规则层）
    .venv/bin/python -m apps.intel_hub.scripts.run_extraction_demo --no-vlm

    # 输出为 JSON 文件
    .venv/bin/python -m apps.intel_hub.scripts.run_extraction_demo --output-json data/output/extraction_demo.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]

SEPARATOR = "=" * 72
SUBSEP = "-" * 60


def _load_notes_and_comments(jsonl_dir: str, note_id: str | None, max_notes: int):
    """加载笔记和评论。"""
    import json as json_mod
    from pathlib import Path as P

    jsonl_path = P(jsonl_dir)
    if not jsonl_path.exists():
        logger.error("JSONL 目录不存在: %s", jsonl_dir)
        return [], {}

    comment_index: dict[str, list[dict[str, Any]]] = {}
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

    raw_dicts: list[dict[str, Any]] = []
    for cf in sorted(jsonl_path.glob("search_contents_*.jsonl")):
        for line in cf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json_mod.loads(line)
                if item.get("note_id"):
                    if note_id and item["note_id"] != note_id:
                        continue
                    raw_dicts.append(item)
            except json_mod.JSONDecodeError:
                continue

    seen_ids: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for d in raw_dicts:
        nid = d.get("note_id", "")
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            deduped.append(d)
    raw_dicts = deduped

    if not note_id:
        raw_dicts = raw_dicts[:max_notes]

    return raw_dicts, comment_index


def _format_list(items: list, indent: int = 4) -> str:
    if not items:
        return " " * indent + "(无)"
    return "\n".join(f"{' ' * indent}• {item}" for item in items)


def _format_dict(d: dict, indent: int = 4) -> str:
    if not d:
        return " " * indent + "(无)"
    lines = []
    for k, v in d.items():
        if v is True:
            lines.append(f"{' ' * indent}✅ {k}")
        elif v is False:
            lines.append(f"{' ' * indent}❌ {k}")
        else:
            lines.append(f"{' ' * indent}❓ {k}: {v}")
    return "\n".join(lines)


def run_demo(args):
    from apps.intel_hub.extraction.cross_modal_validator import validate_cross_modal_consistency
    from apps.intel_hub.extraction.llm_client import is_llm_available, is_vlm_available
    from apps.intel_hub.extraction.scene_extractor import extract_scene_signals
    from apps.intel_hub.extraction.selling_theme_extractor import extract_selling_theme_signals
    from apps.intel_hub.extraction.visual_extractor import (
        extract_visual_signals,
        extract_visual_signals_from_metadata,
    )
    from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note

    jsonl_dir = args.jsonl_dir or str(ROOT / "third_party" / "MediaCrawler" / "data" / "xhs" / "jsonl")
    raw_dicts, comment_index = _load_notes_and_comments(jsonl_dir, args.note_id, args.max_notes)

    if not raw_dicts:
        logger.error("没有找到笔记数据")
        sys.exit(1)

    print(f"\n{SEPARATOR}")
    print(f"  四维提取验证 — {len(raw_dicts)} 篇笔记")
    print(f"  LLM 可用: {is_llm_available()}")
    print(f"  VLM 可用: {is_vlm_available() and not args.no_vlm}")
    print(SEPARATOR)

    all_results: list[dict[str, Any]] = []

    for i, raw in enumerate(raw_dicts):
        note_id = raw.get("note_id", "")
        comments = comment_index.get(str(note_id), [])
        raw_note = parse_raw_note(raw, comments=comments)
        parsed = parse_note(raw_note)

        print(f"\n{'#' * 60}")
        print(f"  笔记 [{i + 1}/{len(raw_dicts)}]: {note_id}")
        print(f"  标题: {parsed.normalized_title}")
        print(f"  图片数: {len(parsed.parsed_images)}")
        print(f"  评论数: {len(parsed.parsed_comments)}")
        print(f"  互动: {parsed.engagement_summary.get('total_engagement', 0)}")
        print(f"{'#' * 60}")

        # ---- 视觉提取 ----
        if args.no_vlm:
            visual = extract_visual_signals_from_metadata(parsed)
            vlm_note = "（仅规则层，VLM 已禁用）"
        else:
            visual = extract_visual_signals(parsed)
            vlm_note = "（规则层 + VLM）" if is_vlm_available() else "（仅规则层，VLM 不可用）"

        print(f"\n{SUBSEP}")
        print(f"  📸 视觉信号 {vlm_note}")
        print(SUBSEP)
        print(f"  主风格: {visual.primary_style or '(未识别)'}")
        print(f"  次风格: {', '.join(visual.secondary_styles) if visual.secondary_styles else '(无)'}")
        print(f"  风格置信度: {visual.style_confidence}")
        print(f"  全部风格: {visual.visual_style_signals}")
        print(f"  视觉场景: {visual.visual_scene_signals}")
        print(f"  构图类型: {visual.visual_composition_type}")
        print(f"  色彩: {visual.visual_color_palette}")
        print(f"  质感: {visual.visual_texture_signals}")
        print(f"  视觉表达: {visual.visual_expression_pattern}")
        print(f"  卖点可视化: {visual.visual_feature_highlights}")
        print(f"  缺失可视化: {visual.missing_feature_visualization}")
        print(f"  视觉差异化: {visual.visual_differentiation_points}")
        print(f"  误导风险: {visual.visual_misleading_risk}")
        print(f"  封面图模式: {visual.hero_image_pattern or '(未识别)'}")
        print(f"  信息密度: {visual.information_density}")
        print(f"  点击差异化得分: {visual.click_differentiation_score}")
        print(f"  转化对齐得分: {visual.conversion_alignment_score}")
        print(f"  风险得分: {visual.visual_risk_score}")
        print(f"  证据数: {len(visual.evidence_refs)}")

        # ---- 卖点提取 ----
        selling = extract_selling_theme_signals(parsed)

        print(f"\n{SUBSEP}")
        print(f"  🏷️ 卖点主题信号")
        print(SUBSEP)
        print(f"  主卖点: {selling.primary_selling_points}")
        print(f"  次卖点: {selling.secondary_selling_points}")
        print(f"  卖点优先级: {selling.selling_point_priority}")
        print(f"  评论验证: {selling.validated_selling_points}")
        print(f"  评论质疑: {selling.selling_point_challenges}")
        print(f"  购买意向: {selling.purchase_intent_signals}")
        print(f"  信任缺口: {selling.trust_gap_signals}")
        print(f"  点击型卖点: {selling.click_oriented_points}")
        print(f"  转化型卖点: {selling.conversion_oriented_points}")
        print(f"  可产品化: {selling.productizable_points}")
        print(f"  纯内容型: {selling.content_only_points}")
        print(f"  卖点主题: {selling.selling_theme_refs}")
        print(f"  证据数: {len(selling.evidence_refs)}")

        # ---- 场景提取 ----
        scene = extract_scene_signals(parsed, visual_signals=visual)

        print(f"\n{SUBSEP}")
        print(f"  🏠 场景信号")
        print(SUBSEP)
        print(f"  显式场景: {scene.scene_signals}")
        print(f"  隐式推断: {scene.inferred_scene_signals}")
        print(f"  推断置信度: {scene.inference_confidence}")
        print(f"  场景目标: {scene.scene_goal_signals}")
        print(f"  场景约束: {scene.scene_constraints}")
        print(f"  受众信号: {scene.audience_signals}")
        print(f"  组合 (前5):")
        for combo in scene.scene_style_value_combos[:5]:
            print(f"    • {combo}")
        print(f"  机会提示 (前3):")
        for hint in scene.scene_opportunity_hints[:3]:
            print(f"    💡 {hint}")
        print(f"  证据数: {len(scene.evidence_refs)}")

        # ---- 跨模态校验 ----
        validation = validate_cross_modal_consistency(visual, selling, scene, parsed)

        print(f"\n{SUBSEP}")
        print(f"  🔍 跨模态校验")
        print(SUBSEP)
        print(f"  总一致性得分: {validation.overall_consistency_score}")
        print(f"\n  卖点-视觉支持:")
        print(_format_dict(validation.selling_claim_visual_support))
        print(f"\n  卖点-评论验证:")
        print(_format_dict(validation.selling_claim_comment_validation))
        print(f"\n  场景一致性:")
        print(_format_dict(validation.scene_alignment))
        print(f"\n  ✅ 高置信结论: {validation.high_confidence_claims}")
        print(f"  ❌ 无支撑结论: {validation.unsupported_claims}")
        print(f"  ⚠️  被质疑结论: {validation.challenged_claims}")

        # 汇总
        result = {
            "note_id": note_id,
            "title": parsed.normalized_title,
            "image_count": len(parsed.parsed_images),
            "comment_count": len(parsed.parsed_comments),
            "visual_signals": visual.model_dump(mode="json"),
            "selling_theme_signals": selling.model_dump(mode="json"),
            "scene_signals": scene.model_dump(mode="json"),
            "cross_modal_validation": validation.model_dump(mode="json"),
        }
        all_results.append(result)

    # 输出 JSON
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(all_results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n\n结果已保存至: {output_path}")

    print(f"\n{SEPARATOR}")
    print(f"  提取完成: {len(all_results)} 篇笔记")
    print(SEPARATOR)


def main():
    parser = argparse.ArgumentParser(description="四维提取验证脚本")
    parser.add_argument("--jsonl-dir", type=str, default=None)
    parser.add_argument("--note-id", type=str, default=None)
    parser.add_argument("--max-notes", type=int, default=5)
    parser.add_argument("--no-vlm", action="store_true", help="禁用 VLM，仅跑规则层")
    parser.add_argument("--output-json", type=str, default=None, help="输出 JSON 路径")
    args = parser.parse_args()
    run_demo(args)


if __name__ == "__main__":
    main()
