"""两阶段聚类流水线入口：读配置、聚类、产出 ClusterSample 与报告。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from apps.template_extraction.clustering.cluster_report import generate_cluster_report
from apps.template_extraction.clustering.cover_clustering import (
    get_cluster_summary,
    run_cover_clustering,
)
from apps.template_extraction.clustering.strategy_clustering import (
    get_strategy_cluster_summary,
    map_clusters_to_templates,
    run_strategy_clustering,
)
from apps.template_extraction.schemas.cluster_sample import ClusterSample
from apps.template_extraction.schemas.cover_features import CoverFeaturePack
from apps.template_extraction.schemas.gallery_features import GalleryFeaturePack

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_config_path() -> Path:
    return _repo_root() / "config" / "template_extraction" / "clustering_params.yaml"


def _load_clustering_config(config_path: str | Path | None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _default_config_path()
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _cover_summary_text(cid: int, sample_count: int, top_positions: list[tuple[int, int]]) -> str:
    tops = ", ".join(f"任务位{i}({c})" for i, c in top_positions) if top_positions else "无显著任务位"
    return f"封面簇 {cid}，共 {sample_count} 条；{tops}"


def _strategy_pattern_text(template: str, mean_eng: float) -> str:
    return f"策略模式 `{template}`，簇内互动代理均值 {mean_eng:.4f}"


def run_cluster_pipeline(
    cover_packs: list[CoverFeaturePack],
    gallery_packs: list[GalleryFeaturePack],
    config_path: str | None = None,
    output_dir: str | None = None,
    note_ids: list[str] | None = None,
) -> list[ClusterSample]:
    """执行两阶段聚类并生成 ClusterSample 列表；可选写报告与 jsonl。"""
    if len(cover_packs) != len(gallery_packs):
        raise ValueError("cover_packs 与 gallery_packs 条数须一致")
    n = len(cover_packs)
    if note_ids is None:
        note_ids = [f"row_{i}" for i in range(n)]
    elif len(note_ids) != n:
        raise ValueError("note_ids 长度须与特征包列表一致")

    cfg = _load_clustering_config(config_path)
    cover_cfg = cfg.get("cover_clustering") or {}
    strat_cfg = cfg.get("strategy_clustering") or {}
    target_templates = cfg.get("target_templates")

    n_cover = int(cover_cfg.get("n_clusters", 15))
    rs_cover = int(cover_cfg.get("random_state", 42))
    n_strat = int(strat_cfg.get("n_clusters", 6))
    rs_strat = int(strat_cfg.get("random_state", 42))

    cover_labels, _ = run_cover_clustering(
        cover_packs, n_clusters=n_cover, random_state=rs_cover
    )
    cover_summaries = get_cluster_summary(cover_packs, cover_labels, note_ids=note_ids)

    strategy_labels, _ = run_strategy_clustering(
        gallery_packs,
        cover_labels,
        n_clusters=n_strat,
        random_state=rs_strat,
    )
    templates_list = (
        list(target_templates)
        if target_templates
        else None
    )
    cluster_to_template = map_clusters_to_templates(
        strategy_labels,
        gallery_packs,
        cover_packs=cover_packs,
        target_templates=templates_list,
    )
    strategy_summaries = get_strategy_cluster_summary(
        gallery_packs,
        strategy_labels,
        note_ids=note_ids,
        cluster_to_template=cluster_to_template,
    )

    cover_rep_idx: dict[int, int] = {}
    for s in cover_summaries:
        cid = s["cluster_id"]
        members = [i for i, c in enumerate(cover_labels) if c == cid]
        if not members:
            continue
        best_i = max(
            members,
            key=lambda idx: float(gallery_packs[idx].engagement_proxy_score),
        )
        cover_rep_idx[cid] = best_i

    strat_rep_idx: dict[int, int] = {}
    for s in strategy_summaries:
        cid = s["cluster_id"]
        members = [i for i, lab in enumerate(strategy_labels) if lab == cid]
        if not members:
            continue
        best_i = max(
            members,
            key=lambda idx: float(gallery_packs[idx].engagement_proxy_score),
        )
        strat_rep_idx[cid] = best_i

    summary_by_cover = {s["cluster_id"]: s for s in cover_summaries}
    summary_by_strat = {s["cluster_id"]: s for s in strategy_summaries}

    samples: list[ClusterSample] = []
    for i in range(n):
        cc = cover_labels[i]
        sc = strategy_labels[i]
        tpl = cluster_to_template.get(sc, "")
        cov_s = summary_by_cover.get(cc, {})
        st_s = summary_by_strat.get(sc, {})
        top_task = cov_s.get("top_task_label_positions") or []

        samples.append(
            ClusterSample(
                note_id=note_ids[i],
                cover_cluster_id=str(cc),
                strategy_cluster_id=str(sc),
                is_cover_representative=(cover_rep_idx.get(cc) == i),
                is_strategy_representative=(strat_rep_idx.get(sc) == i),
                engagement_proxy_score=float(gallery_packs[i].engagement_proxy_score),
                cover_cluster_summary=_cover_summary_text(
                    cc,
                    int(cov_s.get("sample_count", 0)),
                    list(top_task),
                ),
                strategy_cluster_pattern=_strategy_pattern_text(
                    tpl,
                    float(st_s.get("mean_engagement_proxy", 0.0)),
                ),
                dominant_title_keywords=[],
                template_candidate_hint=tpl,
            )
        )

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        report_path = out / "cluster_report.md"
        generate_cluster_report(
            cover_summaries,
            strategy_summaries,
            cluster_to_template,
            output_path=str(report_path),
        )
        jsonl_path = out / "cluster_samples.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as fj:
            for row in samples:
                fj.write(json.dumps(row.model_dump(mode="json"), ensure_ascii=False) + "\n")
        logger.info("已写入 %s 与 %s", report_path, jsonl_path)

    return samples
