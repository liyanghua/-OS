"""聚类结果 Markdown 报告。"""

from __future__ import annotations


def _fmt_positions(positions: list[tuple[int, int]] | None) -> str:
    if not positions:
        return "—"
    return ", ".join(f"位 {i}×{c}" for i, c in positions)


def generate_cluster_report(
    cover_summaries: list[dict],
    strategy_summaries: list[dict],
    cluster_to_template: dict[int, str],
    output_path: str | None = None,
) -> str:
    """生成聚类结果 Markdown 报告（封面簇表 + 策略簇表）。"""
    lines: list[str] = [
        "# 两阶段聚类报告",
        "",
        "## 阶段一：封面原型簇",
        "",
        "| 簇 ID | 样本数 | 任务标签 Top 位 | 代表 note_id |",
        "| --- | ---: | --- | --- |",
    ]
    for s in cover_summaries:
        cid = s["cluster_id"]
        n = s["sample_count"]
        tops = _fmt_positions(s.get("top_task_label_positions"))
        notes = ", ".join(s.get("note_ids") or []) or "—"
        lines.append(f"| {cid} | {n} | {tops} | {notes} |")
    lines.extend(
        [
            "",
            "## 阶段二：策略簇与模板映射",
            "",
            "| 簇 ID | 样本数 | 指派模板 | 语义标签 Top 位 | 互动代理均值 | 代表 note_id |",
            "| --- | ---: | --- | --- | ---: | --- |",
        ]
    )
    for s in strategy_summaries:
        cid = s["cluster_id"]
        n = s["sample_count"]
        tpl = s.get("assigned_template") or cluster_to_template.get(cid, "—")
        sem = _fmt_positions(s.get("top_semantic_label_positions"))
        eng = s.get("mean_engagement_proxy", 0.0)
        if isinstance(eng, float):
            eng_s = f"{eng:.4f}"
        else:
            eng_s = str(eng)
        notes = ", ".join(s.get("note_ids") or []) or "—"
        lines.append(f"| {cid} | {n} | `{tpl}` | {sem} | {eng_s} | {notes} |")

    lines.extend(["", "## 簇 → 模板（对照）", ""])
    for cid in sorted(cluster_to_template.keys()):
        lines.append(f"- **簇 {cid}** → `{cluster_to_template[cid]}`")
    lines.append("")

    text = "\n".join(lines)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
    return text
