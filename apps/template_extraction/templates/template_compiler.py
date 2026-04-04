"""模板编译器：从聚类结果 + 默认配置生成模板库。"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path

import yaml

from apps.template_extraction.schemas.cluster_sample import ClusterSample
from apps.template_extraction.schemas.template import (
    ClusterFeatures,
    CopyRules,
    DerivationRules,
    EvaluationMetrics,
    ProductVisibilityRules,
    SceneRules,
    TableclothMainImageStrategyTemplate,
    VisualRules,
)

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "template_extraction"

_DEFAULT_EVALUATION = EvaluationMetrics(
    target_save_like_ratio=0.35,
    target_click_proxy_score=0.7,
    scene_visibility_score_min=0.6,
)

def load_template_defaults(config_path: str | None = None) -> dict:
    """加载 6 套模板默认配置。"""
    path = Path(config_path) if config_path else _CONFIG_DIR / "template_defaults.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sample_cluster_int(sample: ClusterSample) -> int | None:
    """从样本解析与 cluster_to_template 对齐的整数簇 ID（优先策略簇）。"""
    for raw in (sample.strategy_cluster_id, sample.cover_cluster_id):
        if raw is None or raw == "":
            continue
        try:
            return int(str(raw).strip())
        except ValueError:
            continue
    return None


def _top_keywords_from_samples(samples: list[ClusterSample], limit: int = 12) -> list[str]:
    """从样本的标题关键词与簇摘要中抽取高频词（作为语义补充）。"""
    counter: Counter[str] = Counter()
    for s in samples:
        for kw in s.dominant_title_keywords:
            k = str(kw).strip()
            if k:
                counter[k] += 1
        for blob in (s.cover_cluster_summary, s.strategy_cluster_pattern):
            if not blob:
                continue
            for token in re.findall(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z]{3,}", blob):
                counter[token] += 1
    return [w for w, _ in counter.most_common(limit)]


def _merge_cluster_features(
    cfg: dict,
    samples: list[ClusterSample],
) -> ClusterFeatures:
    """合并 YAML 中的主导标签与聚类样本统计。"""
    base_task = list(cfg.get("dominant_task_labels") or [])
    base_visual = list(cfg.get("dominant_visual_labels") or [])
    base_semantic = list(cfg.get("dominant_semantic_labels") or [])
    extra_semantic = _top_keywords_from_samples(samples)
    merged_semantic: list[str] = []
    seen: set[str] = set()
    for x in base_semantic + extra_semantic:
        if x not in seen:
            seen.add(x)
            merged_semantic.append(x)
    return ClusterFeatures(
        dominant_task_labels=_dedupe_preserve(base_task),
        dominant_visual_labels=_dedupe_preserve(base_visual),
        dominant_semantic_labels=merged_semantic[:24],
    )


def _dedupe_preserve(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _seed_examples_from_samples(samples: list[ClusterSample], limit: int = 3) -> list[str]:
    reps = [
        s.note_id
        for s in samples
        if s.is_strategy_representative or s.is_cover_representative
    ]
    rest = [s.note_id for s in samples if s.note_id not in reps]
    ordered = reps + rest
    return ordered[:limit]


def _cfg_to_template(
    template_id: str,
    cfg: dict,
    cluster_features: ClusterFeatures,
    seed_examples: list[str],
) -> TableclothMainImageStrategyTemplate:
    vr = cfg.get("visual_rules") or {}
    cr = cfg.get("copy_rules") or {}
    sr = cfg.get("scene_rules") or {}
    pvr = cfg.get("product_visibility_rules") or {}
    return TableclothMainImageStrategyTemplate(
        template_id=template_id,
        template_name=str(cfg.get("template_name") or ""),
        template_version="1.0",
        template_goal=str(cfg.get("template_goal") or ""),
        fit_platform=["小红书"],
        fit_category=["桌布"],
        fit_scenarios=list(cfg.get("fit_scenarios") or []),
        fit_styles=list(cfg.get("fit_styles") or []),
        fit_price_band=list(cfg.get("fit_price_band") or []),
        core_user_motive=list(cfg.get("core_user_motive") or []),
        hook_mechanism=list(cfg.get("hook_mechanism") or []),
        cover_role=str(cfg.get("cover_role") or ""),
        image_sequence_pattern=list(cfg.get("image_sequence_pattern") or []),
        visual_rules=VisualRules(**vr) if vr else VisualRules(),
        copy_rules=CopyRules(**cr) if cr else CopyRules(),
        scene_rules=SceneRules(**sr) if sr else SceneRules(),
        product_visibility_rules=ProductVisibilityRules(**pvr) if pvr else ProductVisibilityRules(),
        risk_rules=list(cfg.get("risk_rules") or []),
        best_for=list(cfg.get("best_for") or []),
        avoid_when=list(cfg.get("avoid_when") or []),
        seed_examples=seed_examples,
        cluster_features=cluster_features,
        evaluation_metrics=_DEFAULT_EVALUATION,
        derivation_rules=DerivationRules(can_extend_to=[], prompt_style=""),
    )


def compile_templates(
    cluster_samples: list[ClusterSample],
    cluster_to_template: dict[int, str],
    config_path: str | None = None,
) -> list[TableclothMainImageStrategyTemplate]:
    """从聚类结果 + 默认配置编译模板库。"""
    defaults = load_template_defaults(config_path)
    templates_config: dict = defaults.get("templates") or {}

    # 每个目标模板名 -> 归属该模板的样本
    template_to_samples: dict[str, list[ClusterSample]] = {}
    for sample in cluster_samples:
        cid = _sample_cluster_int(sample)
        if cid is None:
            continue
        tid = cluster_to_template.get(cid)
        if not tid:
            continue
        template_to_samples.setdefault(tid, []).append(sample)

    target_ids = sorted(set(cluster_to_template.values()))
    compiled: list[TableclothMainImageStrategyTemplate] = []

    for template_id in target_ids:
        cfg = templates_config.get(template_id)
        if not cfg:
            logger.warning("模板 %s 在 template_defaults.yaml 中无配置，跳过", template_id)
            continue
        samples = template_to_samples.get(template_id, [])
        cluster_features = _merge_cluster_features(cfg, samples)
        seed_examples = _seed_examples_from_samples(samples)
        compiled.append(
            _cfg_to_template(template_id, cfg, cluster_features, seed_examples),
        )

    return compiled


def save_templates(
    templates: list[TableclothMainImageStrategyTemplate],
    output_dir: str,
) -> None:
    """保存模板库到 JSON 文件。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    for tpl in templates:
        tpl_file = out / f"{tpl.template_id}.json"
        tpl_file.write_text(
            json.dumps(tpl.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        index.append(
            {
                "template_id": tpl.template_id,
                "template_name": tpl.template_name,
                "version": tpl.template_version,
            },
        )
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved %d templates to %s", len(templates), out)
