"""验收报告生成器。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from apps.template_extraction.schemas.cluster_sample import ClusterSample
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled
from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate

logger = logging.getLogger(__name__)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """将表头与行渲染为 GitHub 风格 Markdown 表格。"""
    if not headers:
        return []
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    out = [
        "| " + " | ".join(headers) + " |",
        sep,
    ]
    for row in rows:
        padded = list(row) + [""] * (len(headers) - len(row))
        out.append("| " + " | ".join(padded[: len(headers)]) + " |")
    return out


def _distribution_table(title: str, dist: dict[str, int]) -> list[str]:
    lines: list[str] = [f"### {title}", ""]
    if not dist:
        lines.append("_（无计数）_")
        lines.append("")
        return lines
    rows = [[k, str(v)] for k, v in dist.items()]
    lines.extend(_markdown_table(["标签 ID", "出现次数"], rows))
    lines.append("")
    return lines


def _status_emoji(ok: bool) -> str:
    return "通过" if ok else "待改进"


def generate_acceptance_report(
    labeled_notes: list[XHSNoteLabeled] | None = None,
    cluster_samples: list[ClusterSample] | None = None,
    templates: list[TableclothMainImageStrategyTemplate] | None = None,
    output_path: str | None = None,
    ground_truth_labels: dict[str, str] | None = None,
) -> str:
    """生成 Markdown 格式的验收报告。"""
    from apps.template_extraction.evaluation.cluster_quality import (
        evaluate_cluster_balance,
        evaluate_cluster_purity,
        evaluate_engagement_coverage,
    )
    from apps.template_extraction.evaluation.label_quality import (
        evaluate_label_coverage,
        evaluate_label_distribution,
    )
    from apps.template_extraction.evaluation.template_quality import (
        evaluate_template_boundaries,
        evaluate_template_completeness,
        evaluate_template_executability,
    )

    labeled_notes = labeled_notes or []
    cluster_samples = cluster_samples or []
    templates = templates or []

    coverage: dict = {}
    dist: dict = {}
    purity: dict = {}
    balance: dict = {}
    engagement: dict = {}
    completeness: dict = {}
    boundaries: dict = {}
    executability: dict = {}

    lines: list[str] = []
    lines.append("# 桌布主图策略模板库 - 验收报告")
    lines.append("")
    lines.append(f"生成时间（UTC）：`{datetime.now(UTC).isoformat()}`")
    lines.append("")

    # --- 1. 标注质量 ---
    lines.append("## 1. 标注质量")
    lines.append("")
    if labeled_notes:
        coverage = evaluate_label_coverage(labeled_notes)
        dist = evaluate_label_distribution(labeled_notes)

        cov_rows = [
            ["样本总量", str(coverage["total"])],
            [
                "封面任务标注覆盖率",
                f"{coverage['cover_task_coverage']:.1%}",
            ],
            ["视觉结构标注覆盖率", f"{coverage['visual_coverage']:.1%}"],
            ["经营语义标注覆盖率", f"{coverage['semantic_coverage']:.1%}"],
            ["风险标注覆盖率", f"{coverage['risk_coverage']:.1%}"],
        ]
        lines.extend(_markdown_table(["指标", "值"], cov_rows))
        lines.append("")

        lines.append("### 1.1 标签分布")
        lines.append("")
        lines.extend(
            _distribution_table("封面任务标签分布", dist.get("cover_task_distribution", {}))
        )
        lines.extend(
            _distribution_table("经营语义标签分布", dist.get("semantic_distribution", {}))
        )
        lines.extend(_distribution_table("风险标签分布", dist.get("risk_distribution", {})))
    else:
        lines.append("_无标注数据，跳过本节。_")
        lines.append("")

    # --- 2. 聚类质量 ---
    lines.append("## 2. 聚类质量")
    lines.append("")
    if cluster_samples:
        purity = evaluate_cluster_purity(cluster_samples, ground_truth_labels=ground_truth_labels)
        balance = evaluate_cluster_balance(cluster_samples)
        engagement = evaluate_engagement_coverage(cluster_samples)

        lines.append("### 2.1 汇总指标")
        lines.append("")
        summary_rows = [
            ["簇数量", str(purity["num_clusters"])],
            ["平均纯度（代理或真值）", f"{purity['average_purity']:.4f}"],
            [
                "纯度计算方式",
                "真值标签" if purity.get("used_ground_truth") else "标题关键词众数占比",
            ],
            ["平均簇规模", f"{balance['avg_size']:.2f}"],
            ["最大簇规模", str(balance["max_size"])],
            ["最小簇规模", str(balance["min_size"])],
            ["规模均衡比（最小/最大）", f"{balance['balance_ratio']:.4f}"],
            ["样本总量", str(engagement["total_samples"])],
            ["高互动样本数（>0.5）", str(engagement["high_engagement_samples"])],
            ["高互动样本占比", f"{engagement['high_engagement_ratio']:.1%}"],
            ["含高互动样本的簇数", str(engagement["clusters_with_high_engagement"])],
            ["簇总数（含未分配键）", str(engagement["total_clusters"])],
            ["高互动簇覆盖率", f"{engagement['cluster_coverage']:.1%}"],
        ]
        lines.extend(_markdown_table(["指标", "值"], summary_rows))
        lines.append("")

        lines.append("### 2.2 各簇纯度")
        lines.append("")
        purities = purity.get("cluster_purities", {})
        if purities:
            p_rows = [
                [cid, f"{val:.4f}"]
                for cid, val in sorted(
                    purities.items(),
                    key=lambda x: x[0],
                )
            ]
            lines.extend(_markdown_table(["策略簇 ID", "纯度"], p_rows))
        else:
            lines.append("_（无簇纯度数据）_")
        lines.append("")

        lines.append("### 2.3 各簇样本量")
        lines.append("")
        sizes = balance.get("cluster_sizes", {})
        if sizes:
            s_rows = [
                [cid, str(cnt)]
                for cid, cnt in sorted(sizes.items(), key=lambda x: (-x[1], x[0]))
            ]
            lines.extend(_markdown_table(["策略簇 ID", "样本数"], s_rows))
        else:
            lines.append("_（无簇规模数据）_")
        lines.append("")
    else:
        lines.append("_无聚类样本数据，跳过本节。_")
        lines.append("")

    # --- 3. 模板质量 ---
    lines.append("## 3. 模板质量")
    lines.append("")
    if templates:
        completeness = evaluate_template_completeness(templates)
        boundaries = evaluate_template_boundaries(templates)
        executability = evaluate_template_executability(templates)

        lines.append("### 3.1 完整性得分（按模板）")
        lines.append("")
        c_rows = [
            [tid, f"{data['completeness_score']:.2f}"]
            for tid, data in sorted(completeness.items(), key=lambda x: x[0])
        ]
        lines.extend(_markdown_table(["模板 ID", "完整性得分（0–1）"], c_rows))
        lines.append("")

        lines.append("### 3.2 边界重叠（场景 / 风格）")
        lines.append("")
        lines.append("#### 场景维度：多模板共用同一 `fit_scenarios` 条目")
        lines.append("")
        so = boundaries.get("scenario_overlaps", {})
        if so:
            ov_rows = [
                [scen, ", ".join(sorted(ids))]
                for scen, ids in sorted(so.items(), key=lambda x: x[0])
            ]
            lines.extend(_markdown_table(["场景", "模板 ID 列表"], ov_rows))
        else:
            lines.append("_无多模板场景重叠。_")
        lines.append("")

        lines.append("#### 风格维度：多模板共用同一 `fit_styles` 条目")
        lines.append("")
        sto = boundaries.get("style_overlaps", {})
        if sto:
            st_rows = [
                [sty, ", ".join(sorted(ids))]
                for sty, ids in sorted(sto.items(), key=lambda x: x[0])
            ]
            lines.extend(_markdown_table(["风格", "模板 ID 列表"], st_rows))
        else:
            lines.append("_无多模板风格重叠。_")
        lines.append("")

        lines.append("#### 重叠计数摘要")
        lines.append("")
        lines.extend(
            _markdown_table(
                ["类型", "重叠条目数"],
                [
                    ["场景", str(boundaries.get("scenario_overlap_count", 0))],
                    ["风格", str(boundaries.get("style_overlap_count", 0))],
                ],
            )
        )
        lines.append("")

        lines.append("### 3.3 可执行性检查")
        lines.append("")
        ex_rows = []
        for tid in sorted(executability.keys()):
            ex = executability[tid]
            ok = ex.get("is_executable", False)
            issues = ex.get("issues", [])
            issues_s = "；".join(issues) if issues else "—"
            ex_rows.append([tid, _status_emoji(ok), issues_s])
        lines.extend(_markdown_table(["模板 ID", "状态", "问题说明"], ex_rows))
        lines.append("")
    else:
        lines.append("_无模板数据，跳过本节。_")
        lines.append("")

    # --- 4. 综合评估 ---
    lines.append("## 4. 综合评估")
    lines.append("")
    lines.append("以下阈值用于快速验收：封面任务覆盖率 > 80%；簇规模均衡比 > 0.3；各模板完整性 ≥ 0.8。")
    lines.append("")

    summary_rows: list[list[str]] = []

    if labeled_notes and coverage:
        c_cov = coverage.get("cover_task_coverage", 0)
        summary_rows.append(
            [
                "标注覆盖（封面任务）",
                f"{c_cov:.1%}",
                _status_emoji(c_cov > 0.8),
            ]
        )
        v_cov = coverage.get("visual_coverage", 0)
        summary_rows.append(
            ["标注覆盖（视觉结构）", f"{v_cov:.1%}", _status_emoji(v_cov > 0.5)]
        )
        s_cov = coverage.get("semantic_coverage", 0)
        summary_rows.append(
            ["标注覆盖（经营语义）", f"{s_cov:.1%}", _status_emoji(s_cov > 0.5)]
        )

    if cluster_samples and balance:
        br = balance.get("balance_ratio", 0)
        summary_rows.append(
            [
                "聚类规模均衡",
                f"均衡比 {br:.4f}",
                _status_emoji(br > 0.3),
            ]
        )
    if cluster_samples and purity:
        ap = purity.get("average_purity", 0)
        summary_rows.append(
            [
                "聚类平均纯度",
                f"{ap:.4f}",
                _status_emoji(ap >= 0.35),
            ]
        )
    if cluster_samples and engagement:
        ec = engagement.get("cluster_coverage", 0)
        summary_rows.append(
            [
                "高互动簇覆盖",
                f"{ec:.1%}",
                _status_emoji(ec > 0.5),
            ]
        )

    if templates and completeness:
        all_complete = all(
            v.get("completeness_score", 0) >= 0.8 for v in completeness.values()
        )
        min_c = min((v.get("completeness_score", 0) for v in completeness.values()), default=0)
        summary_rows.append(
            [
                "模板完整性",
                f"最低分 {min_c:.2f}",
                _status_emoji(all_complete),
            ]
        )
    if templates and executability:
        all_exec = all(v.get("is_executable") for v in executability.values())
        bad = sum(1 for v in executability.values() if not v.get("is_executable"))
        summary_rows.append(
            [
                "模板可执行性",
                f"未通过 {bad} / {len(executability)}",
                _status_emoji(all_exec),
            ]
        )
    if templates and boundaries:
        soc = boundaries.get("scenario_overlap_count", 0)
        stc = boundaries.get("style_overlap_count", 0)
        low_overlap = soc <= 3 and stc <= 5
        summary_rows.append(
            [
                "模板边界（重叠条目数）",
                f"场景 {soc}，风格 {stc}",
                _status_emoji(low_overlap),
            ]
        )

    if summary_rows:
        lines.extend(_markdown_table(["维度", "摘要", "结论"], summary_rows))
    else:
        lines.append("_无可用输入数据，无法生成综合表。_")
    lines.append("")

    report = "\n".join(lines)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        logger.info("验收报告已保存: %s", output_path)

    return report
