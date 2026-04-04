"""聚类质量评估。"""

from __future__ import annotations

import logging
from collections import Counter

from apps.template_extraction.schemas.cluster_sample import ClusterSample

logger = logging.getLogger(__name__)


def _cluster_key(sample: ClusterSample) -> str:
    cid = sample.strategy_cluster_id
    return str(cid) if cid is not None else "__unassigned__"


def evaluate_cluster_purity(
    samples: list[ClusterSample],
    ground_truth_labels: dict[str, str] | None = None,
) -> dict:
    """聚类纯度评估（无真值时用簇内 dominant_title_keywords 众数占比作为代理）。"""
    clusters: dict[str, list[ClusterSample]] = {}
    for s in samples:
        clusters.setdefault(_cluster_key(s), []).append(s)

    purities: dict[str, float] = {}
    for cid, members in clusters.items():
        if ground_truth_labels:
            gt_counts: Counter[str] = Counter()
            for m in members:
                g = ground_truth_labels.get(m.note_id)
                if g:
                    gt_counts[g] += 1
            if gt_counts:
                top = gt_counts.most_common(1)[0][1]
                purities[cid] = top / len(members)
            else:
                purities[cid] = 0.0
        else:
            all_kw: list[str] = []
            for m in members:
                all_kw.extend(m.dominant_title_keywords)
            if all_kw:
                counter = Counter(all_kw)
                most_common_count = counter.most_common(1)[0][1]
                purities[cid] = most_common_count / len(all_kw)
            else:
                purities[cid] = 0.0

    avg_purity = sum(purities.values()) / max(len(purities), 1)
    return {
        "cluster_purities": purities,
        "average_purity": avg_purity,
        "num_clusters": len(clusters),
        "used_ground_truth": ground_truth_labels is not None,
    }


def evaluate_cluster_balance(samples: list[ClusterSample]) -> dict:
    """聚类均衡性评估。"""
    clusters = Counter(_cluster_key(s) for s in samples)
    sizes = list(clusters.values())
    avg_size = sum(sizes) / max(len(sizes), 1)
    max_size = max(sizes) if sizes else 0
    min_size = min(sizes) if sizes else 0

    return {
        "cluster_sizes": dict(clusters.most_common()),
        "avg_size": avg_size,
        "max_size": max_size,
        "min_size": min_size,
        "balance_ratio": min_size / max(max_size, 1),
    }


def evaluate_engagement_coverage(samples: list[ClusterSample]) -> dict:
    """高互动样本覆盖率。"""
    high_engagement = [s for s in samples if s.engagement_proxy_score > 0.5]
    clusters_with_high = {_cluster_key(s) for s in high_engagement}
    all_clusters = {_cluster_key(s) for s in samples}

    return {
        "total_samples": len(samples),
        "high_engagement_samples": len(high_engagement),
        "high_engagement_ratio": len(high_engagement) / max(len(samples), 1),
        "clusters_with_high_engagement": len(clusters_with_high),
        "total_clusters": len(all_clusters),
        "cluster_coverage": len(clusters_with_high) / max(len(all_clusters), 1),
    }
