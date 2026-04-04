"""聚类流水线与 sklearn 封装单测。"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from apps.template_extraction.clustering.cluster_pipeline import run_cluster_pipeline
from apps.template_extraction.clustering.cover_clustering import run_cover_clustering
from apps.template_extraction.clustering.strategy_clustering import run_strategy_clustering
from apps.template_extraction.features.label_features import vectorize_labels
from apps.template_extraction.schemas.cluster_sample import ClusterSample
from apps.template_extraction.schemas.cover_features import CoverFeaturePack
from apps.template_extraction.schemas.gallery_features import GalleryFeaturePack
from apps.template_extraction.schemas.labels import LabelResult
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled


def _labeled_stub(note_id: str, cover_id: str, *, visual: str | None = None, semantic: str = "mood_photo_friendly") -> XHSNoteLabeled:
    vlist = []
    if visual:
        vlist.append(LabelResult(label_id=visual, confidence=0.55, evidence_snippet="v", labeler_mode="rule"))
    return XHSNoteLabeled(
        note_id=note_id,
        cover_task_labels=[
            LabelResult(label_id=cover_id, confidence=0.6, evidence_snippet="c", labeler_mode="rule")
        ],
        visual_structure_labels=vlist,
        business_semantic_labels=[
            LabelResult(label_id=semantic, confidence=0.5, evidence_snippet="s", labeler_mode="rule")
        ],
    )


def _make_cover_pack(i: int) -> CoverFeaturePack:
    lids = ["scene_seed", "style_anchor", "price_value", "gift_event", "texture_detail", "set_combo"]
    lid = lids[i % len(lids)]
    labeled = _labeled_stub(f"s{i}", lid, visual="shot_closeup" if i % 4 == 0 else "shot_topdown")
    v = vectorize_labels(labeled)
    return CoverFeaturePack(
        task_label_vector=v["task_label_vector"],
        visual_label_vector=v["visual_label_vector"],
        semantic_label_vector=v["semantic_label_vector"],
        risk_label_vector=v["risk_label_vector"],
        kw_style=bool(i % 2),
        kw_scene=bool(i % 3 == 0),
        kw_price=bool(i % 5 == 0),
        kw_event=bool(i % 7 == 0),
        kw_upgrade=bool(i % 6 == 0),
        kw_gift=bool(i % 8 == 0),
        kw_aesthetic=bool(i % 9 == 0),
        has_festival_element_visible=bool(i % 10 == 0),
    )


def _make_gallery_pack(i: int) -> GalleryFeaturePack:
    labeled = _labeled_stub(f"g{i}", "scene_seed")
    sem = vectorize_labels(labeled)["semantic_label_vector"]
    return GalleryFeaturePack(
        image_count=3 + (i % 5),
        cover_role="scene_seed",
        role_seq_top5=["cover_hook", "style_expand", "texture_expand", "usage_expand", "guide_expand"],
        style_consistency_score=0.5 + (i % 5) * 0.05,
        color_consistency_score=0.55,
        scene_consistency_score=0.6,
        has_scene_image=bool(i % 2),
        has_texture_closeup=bool(i % 3),
        has_buying_guide=bool(i % 4),
        has_before_after=bool(i % 6 == 0),
        has_set_combo=bool(i % 7 == 0),
        like_count=10 + i,
        save_count=2 + i // 2,
        comment_count=1 + i // 3,
        engagement_proxy_score=min(1.0, 0.1 + i * 0.04),
        semantic_label_vector=sem,
    )


@pytest.fixture
def twenty_feature_packs() -> tuple[list[CoverFeaturePack], list[GalleryFeaturePack]]:
    """20 组封面 / 图组特征包，向量维度与真实流水线一致。"""
    covers = [_make_cover_pack(i) for i in range(20)]
    galleries = [_make_gallery_pack(i) for i in range(20)]
    return covers, galleries


def test_run_cover_clustering_valid_labels(twenty_feature_packs: tuple[list, list]) -> None:
    """run_cover_clustering 产出与样本等长的整数簇标签。"""
    covers, _ = twenty_feature_packs
    labels, model = run_cover_clustering(covers, n_clusters=8, random_state=42)
    assert len(labels) == len(covers)
    assert all(isinstance(x, int) for x in labels)
    assert all(0 <= x < 8 for x in labels)
    assert model is not None


def test_run_strategy_clustering_valid_labels(twenty_feature_packs: tuple[list, list]) -> None:
    """run_strategy_clustering 在封面簇 ID 辅助下产出策略簇标签。"""
    covers, galleries = twenty_feature_packs
    cover_labels, _ = run_cover_clustering(covers, n_clusters=6, random_state=0)
    strat_labels, model = run_strategy_clustering(galleries, cover_labels, n_clusters=5, random_state=0)
    assert len(strat_labels) == len(galleries)
    assert all(0 <= x < 5 for x in strat_labels)
    assert model is not None


def test_cluster_pipeline_end_to_end(twenty_feature_packs: tuple[list, list], tmp_path: Path) -> None:
    """run_cluster_pipeline 端到端返回 ClusterSample 列表并可写盘。"""
    covers, galleries = twenty_feature_packs
    note_ids = [f"note_{i:02d}" for i in range(20)]
    cfg = tmp_path / "clustering.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            cover_clustering:
              n_clusters: 6
              random_state: 42
            strategy_clustering:
              n_clusters: 4
              random_state: 42
            target_templates:
              - scene_seed
              - style_anchor
            """
        ).strip(),
        encoding="utf-8",
    )
    samples = run_cluster_pipeline(
        covers,
        galleries,
        config_path=str(cfg),
        output_dir=str(tmp_path / "out"),
        note_ids=note_ids,
    )
    assert len(samples) == 20
    for s in samples:
        assert isinstance(s, ClusterSample)
        assert s.note_id in note_ids
        assert s.cover_cluster_id is not None
        assert s.strategy_cluster_id is not None
    assert (tmp_path / "out" / "cluster_report.md").is_file()
    assert (tmp_path / "out" / "cluster_samples.jsonl").is_file()


def test_fewer_samples_than_requested_clusters() -> None:
    """请求簇数大于样本数时，实现应收缩为 min(n_clusters, n_samples)，标签仍合法。"""
    packs = [_make_cover_pack(i) for i in range(5)]
    labels, _ = run_cover_clustering(packs, n_clusters=100, random_state=99)
    assert len(labels) == 5
    assert len(set(labels)) <= 5
    assert all(0 <= x < len(packs) for x in labels)
