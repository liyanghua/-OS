"""阶段一：封面特征 KMeans 聚类。"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans

from apps.template_extraction.schemas.cover_features import CoverFeaturePack

logger = logging.getLogger(__name__)


def build_cover_feature_matrix(cover_packs: list[CoverFeaturePack]) -> np.ndarray:
    """从 CoverFeaturePack 构建特征矩阵。"""
    rows = []
    for p in cover_packs:
        kw_vec = [
            float(v)
            for v in [
                p.kw_style,
                p.kw_scene,
                p.kw_price,
                p.kw_event,
                p.kw_upgrade,
                p.kw_gift,
                p.kw_aesthetic,
            ]
        ]
        row = p.task_label_vector + p.visual_label_vector + p.semantic_label_vector + kw_vec
        rows.append(row)
    return np.array(rows, dtype=np.float64)


def run_cover_clustering(
    cover_packs: list[CoverFeaturePack],
    n_clusters: int = 15,
    random_state: int = 42,
) -> tuple[list[int], KMeans | None]:
    """阶段一聚类。返回 (labels, model)；样本过少时 model 为 None。"""
    if not cover_packs:
        return [], None
    X = build_cover_feature_matrix(cover_packs)
    n_clusters = min(n_clusters, len(cover_packs))
    if n_clusters < 2:
        return [0] * len(cover_packs), None
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = model.fit_predict(X).tolist()
    logger.info("封面聚类: %d 条 -> %d 簇", len(cover_packs), n_clusters)
    return labels, model


def get_cluster_summary(
    cover_packs: list[CoverFeaturePack],
    labels: list[int],
    note_ids: list[str] | None = None,
) -> list[dict]:
    """按簇汇总：样本数、代表 note_id、任务标签位次 Top。"""
    if note_ids is None:
        note_ids = [f"row_{i}" for i in range(len(cover_packs))]
    if len(note_ids) != len(cover_packs):
        raise ValueError("note_ids 长度须与 cover_packs 一致")

    clusters: dict[int, list[tuple[int, CoverFeaturePack]]] = {}
    for i, (pack, cid) in enumerate(zip(cover_packs, labels)):
        clusters.setdefault(cid, []).append((i, pack))

    summaries = []
    for cid in sorted(clusters.keys()):
        members = clusters[cid]
        rep_ids = [note_ids[i] for i, _ in members]
        task_counts: Counter[int] = Counter()
        for _, pack in members:
            for j, v in enumerate(pack.task_label_vector):
                if v > 0:
                    task_counts[j] += 1
        summaries.append(
            {
                "cluster_id": cid,
                "sample_count": len(members),
                "note_ids": rep_ids[:5],
                "top_task_label_positions": task_counts.most_common(3),
            }
        )
    return summaries
