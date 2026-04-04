"""阶段二：图组策略聚类（融合封面簇 one-hot）。"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans

from apps.template_extraction.schemas.cover_features import CoverFeaturePack
from apps.template_extraction.schemas.gallery_features import GalleryFeaturePack

logger = logging.getLogger(__name__)

TARGET_TEMPLATES = [
    "scene_seed",
    "style_anchor",
    "texture_detail",
    "affordable_makeover",
    "festival_gift",
    "set_combo",
]

_ROLE_BIN_DIM = 8


def _stable_bucket(s: str, n_bins: int) -> int:
    if not s:
        return 0
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % n_bins


def _encode_role_sequence(g: GalleryFeaturePack) -> list[float]:
    """将 cover_role 与 role_seq_top5 映射为固定维度的多桶计数向量。"""
    bins = [0.0] * _ROLE_BIN_DIM
    parts = [g.cover_role, *g.role_seq_top5]
    for p in parts:
        b = _stable_bucket(str(p).strip(), _ROLE_BIN_DIM)
        bins[b] += 1.0
    return bins


def build_strategy_feature_matrix(
    gallery_packs: list[GalleryFeaturePack],
    cover_cluster_ids: list[int],
) -> np.ndarray:
    """拼接图组数值特征、语义向量与封面簇 one-hot。"""
    if len(gallery_packs) != len(cover_cluster_ids):
        raise ValueError("gallery_packs 与 cover_cluster_ids 长度须一致")
    if not gallery_packs:
        return np.zeros((0, 0), dtype=np.float64)

    max_cid = max(cover_cluster_ids, default=0)
    n_cover = max_cid + 1

    rows = []
    for g, cid in zip(gallery_packs, cover_cluster_ids):
        role_vec = _encode_role_sequence(g)
        mid = [
            float(g.style_consistency_score),
            float(g.color_consistency_score),
            float(g.has_scene_image),
            float(g.has_texture_closeup),
            float(g.has_buying_guide),
            float(g.engagement_proxy_score),
        ]
        sem = [float(x) for x in g.semantic_label_vector]
        one_hot = [0.0] * n_cover
        if 0 <= cid < n_cover:
            one_hot[cid] = 1.0
        row = role_vec + mid + sem + one_hot
        rows.append(row)
    return np.array(rows, dtype=np.float64)


def run_strategy_clustering(
    gallery_packs: list[GalleryFeaturePack],
    cover_cluster_ids: list[int],
    n_clusters: int = 6,
    random_state: int = 42,
) -> tuple[list[int], KMeans | None]:
    """阶段二聚类，得到策略簇标签。"""
    if not gallery_packs:
        return [], None
    X = build_strategy_feature_matrix(gallery_packs, cover_cluster_ids)
    n_clusters = min(n_clusters, len(gallery_packs))
    if n_clusters < 2:
        return [0] * len(gallery_packs), None
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = model.fit_predict(X).tolist()
    logger.info("策略聚类: %d 条 -> %d 簇", len(gallery_packs), n_clusters)
    return labels, model


def _mean_attr_float(xs: list[GalleryFeaturePack], name: str) -> float:
    if not xs:
        return 0.0
    return sum(float(getattr(x, name, 0.0)) for x in xs) / len(xs)


def _mean_attr_bool_gallery(xs: list[GalleryFeaturePack], name: str) -> float:
    if not xs:
        return 0.0
    return sum(float(getattr(x, name)) for x in xs) / len(xs)


def _mean_attr_bool_cover(xs: list[CoverFeaturePack], name: str) -> float:
    if not xs:
        return 0.0
    return sum(float(getattr(x, name)) for x in xs) / len(xs)


def _template_scores_for_cluster(
    g_sub: list[GalleryFeaturePack],
    c_sub: list[CoverFeaturePack] | None,
) -> dict[str, float]:
    """基于簇内均值特征，为各目标模板打分（启发式）。"""
    s_scene = _mean_attr_bool_gallery(g_sub, "has_scene_image") + _mean_attr_float(
        g_sub, "scene_consistency_score"
    )
    s_style = _mean_attr_float(g_sub, "style_consistency_score") + _mean_attr_float(
        g_sub, "color_consistency_score"
    )
    s_tex = _mean_attr_bool_gallery(g_sub, "has_texture_closeup") * 2.0
    s_aff = _mean_attr_bool_gallery(g_sub, "has_before_after") + _mean_attr_bool_gallery(
        g_sub, "has_buying_guide"
    )
    if c_sub:
        s_aff += sum(float(c.kw_price) for c in c_sub) / len(c_sub)
    s_fest = 0.0
    if c_sub:
        s_fest += _mean_attr_bool_cover(c_sub, "has_festival_element_visible")
        s_fest += sum(float(c.kw_event) + float(c.kw_gift) for c in c_sub) / len(c_sub)
    s_set = _mean_attr_bool_gallery(g_sub, "has_set_combo")
    return {
        "scene_seed": s_scene,
        "style_anchor": s_style,
        "texture_detail": s_tex,
        "affordable_makeover": s_aff,
        "festival_gift": s_fest,
        "set_combo": s_set,
    }


def map_clusters_to_templates(
    strategy_labels: list[int],
    gallery_packs: list[GalleryFeaturePack],
    cover_packs: list[CoverFeaturePack] | None = None,
    target_templates: list[str] | None = None,
) -> dict[int, str]:
    """将每个策略簇 ID 映射到最可能的目标模板名（启发式 + 贪心去重）。"""
    templates = list(target_templates or TARGET_TEMPLATES)
    cluster_ids = sorted(set(strategy_labels))
    scores_by_cluster: dict[int, dict[str, float]] = {}
    for cid in cluster_ids:
        idxs = [i for i, lab in enumerate(strategy_labels) if lab == cid]
        g_sub = [gallery_packs[i] for i in idxs]
        c_sub = [cover_packs[i] for i in idxs] if cover_packs else None
        raw = _template_scores_for_cluster(g_sub, c_sub)
        scores_by_cluster[cid] = {t: float(raw.get(t, 0.0)) for t in templates}

    def margin(cid: int) -> float:
        vals = sorted(scores_by_cluster[cid].values(), reverse=True)
        if len(vals) >= 2:
            return vals[0] - vals[1]
        return vals[0] if vals else 0.0

    order = sorted(cluster_ids, key=lambda c: margin(c), reverse=True)
    used: set[str] = set()
    mapping: dict[int, str] = {}
    for cid in order:
        ranked = sorted(templates, key=lambda t: scores_by_cluster[cid][t], reverse=True)
        chosen = None
        for t in ranked:
            if t not in used:
                chosen = t
                used.add(t)
                break
        if chosen is None:
            chosen = ranked[0] if ranked else templates[0]
        mapping[cid] = chosen
    for cid in cluster_ids:
        if cid not in mapping:
            mapping[cid] = templates[cid % len(templates)]
    return mapping


def get_strategy_cluster_summary(
    gallery_packs: list[GalleryFeaturePack],
    labels: list[int],
    note_ids: list[str] | None = None,
    cluster_to_template: dict[int, str] | None = None,
) -> list[dict]:
    """按策略簇汇总：样本数、代表 note、指派模板、语义位次 Top。"""
    if note_ids is None:
        note_ids = [f"row_{i}" for i in range(len(gallery_packs))]
    if len(note_ids) != len(gallery_packs):
        raise ValueError("note_ids 长度须与 gallery_packs 一致")

    clusters: dict[int, list[tuple[int, GalleryFeaturePack]]] = {}
    for i, (pack, cid) in enumerate(zip(gallery_packs, labels)):
        clusters.setdefault(cid, []).append((i, pack))

    summaries = []
    for cid in sorted(clusters.keys()):
        members = clusters[cid]
        rep_ids = [note_ids[i] for i, _ in members]
        sem_counts: Counter[int] = Counter()
        eng_sum = 0.0
        for _, pack in members:
            eng_sum += float(pack.engagement_proxy_score)
            for j, v in enumerate(pack.semantic_label_vector):
                if v > 0:
                    sem_counts[j] += 1
        tpl = (cluster_to_template or {}).get(cid, "")
        summaries.append(
            {
                "cluster_id": cid,
                "sample_count": len(members),
                "note_ids": rep_ids[:5],
                "assigned_template": tpl,
                "top_semantic_label_positions": sem_counts.most_common(3),
                "mean_engagement_proxy": eng_sum / len(members) if members else 0.0,
            }
        )
    return summaries
