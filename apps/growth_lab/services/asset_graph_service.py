"""asset_graph_service — 资产图谱管理与全链路闭环。

Phase 3 核心服务：
1. 从 ResultSnapshot 自动沉淀高表现资产
2. 从高表现资产提取模式模板
3. 模板推荐回流到 Radar/Compiler
4. 搜索与标签管理
"""

from __future__ import annotations

import logging
from typing import Any

from apps.growth_lab.schemas.asset_performance import (
    AssetPerformanceCard,
    PatternTemplate,
    ReuseRecommendation,
)
from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)

_HIGH_PERFORMER_CTR = 0.03
_PATTERN_MIN_ASSETS = 2


class AssetGraphService:
    """资产图谱管理——沉淀、模式提取、推荐闭环。"""

    def __init__(self, store: GrowthLabStore | None = None) -> None:
        self._store = store or GrowthLabStore()

    # ── 高表现沉淀 ────────────────────────────────────────────

    def promote_high_performers(self, workspace_id: str = "") -> list[AssetPerformanceCard]:
        """扫描测试结果，将高表现版本自动沉淀为资产卡。"""
        tasks = self._store.list_test_tasks(where={"workspace_id": workspace_id} if workspace_id else None)
        promoted: list[AssetPerformanceCard] = []

        for task in tasks:
            task_id = task.get("task_id", "")
            results = self._store.list_result_snapshots(task_id)
            best = self._find_best_result(results)
            if not best:
                continue

            ctr = best.get("ctr", 0) or 0
            if ctr < _HIGH_PERFORMER_CTR:
                continue

            existing = self._store.get_asset_performance_card(task.get("source_variant_id", ""))
            if existing:
                continue

            card = AssetPerformanceCard(
                asset_type="high_performer",
                source_platform=task.get("platform", ""),
                source_variant_id=task.get("source_variant_id", ""),
                source_test_task_id=task_id,
                best_metrics={
                    "ctr": ctr,
                    "traffic": best.get("traffic"),
                    "conversion_rate": best.get("conversion_rate"),
                    "refund_rate": best.get("refund_rate"),
                },
                tags=self._auto_tag(task, best),
                description=f"高表现素材 CTR {ctr*100:.1f}%",
                workspace_id=task.get("workspace_id", ""),
                brand_id=task.get("brand_id", ""),
                status="active",
            )
            self._store.save_asset_performance_card(card.model_dump())
            promoted.append(card)

        logger.info("高表现沉淀: 扫描 %d 个任务，沉淀 %d 个资产", len(tasks), len(promoted))
        return promoted

    # ── 模式提取 ──────────────────────────────────────────────

    def extract_patterns(self, workspace_id: str = "") -> list[PatternTemplate]:
        """从高表现资产中提取可复用的模式模板。"""
        where: dict[str, Any] = {"status": "active"}
        if workspace_id:
            where["workspace_id"] = workspace_id
        assets = self._store.list_asset_performance_cards(where=where)

        tag_groups: dict[str, list[dict]] = {}
        for a in assets:
            for tag in a.get("tags", []):
                tag_groups.setdefault(tag, []).append(a)

        templates: list[PatternTemplate] = []
        for tag, group in tag_groups.items():
            if len(group) < _PATTERN_MIN_ASSETS:
                continue

            avg_ctr = sum(
                (a.get("best_metrics", {}).get("ctr", 0) or 0) for a in group
            ) / len(group)

            tpl = PatternTemplate(
                template_type="high_ctr_combo",
                name=f"高表现模式: {tag}",
                description=f"基于 {len(group)} 个高表现素材的共性模式",
                source_asset_ids=[a.get("asset_id", "") for a in group],
                avg_performance={"avg_ctr": round(avg_ctr, 4)},
                usage_count=0,
                workspace_id=workspace_id,
                brand_id=group[0].get("brand_id", ""),
                status="published",
            )
            self._store.save_pattern_template(tpl.model_dump())
            templates.append(tpl)

        logger.info("模式提取: %d 个标签组 → %d 个模板", len(tag_groups), len(templates))
        return templates

    # ── 推荐回流 ──────────────────────────────────────────────

    def recommend_for_selling_point(
        self,
        selling_point_id: str,
        workspace_id: str = "",
    ) -> list[ReuseRecommendation]:
        """为给定卖点推荐可复用资产和模板。"""
        spec = self._store.get_selling_point_spec(selling_point_id)
        if not spec:
            return []

        target_people = set(spec.get("target_people", []))
        target_scenarios = set(spec.get("target_scenarios", []))
        core_claim = spec.get("core_claim", "")

        where: dict[str, Any] = {"status": "active"}
        if workspace_id:
            where["workspace_id"] = workspace_id
        assets = self._store.list_asset_performance_cards(where=where)

        recs: list[ReuseRecommendation] = []
        for asset in assets:
            tags = set(asset.get("tags", []))
            overlap = len(tags & (target_people | target_scenarios))
            if overlap == 0:
                if core_claim and any(kw in asset.get("description", "") for kw in core_claim.split()[:3]):
                    overlap = 1
                else:
                    continue

            confidence = min(0.3 + overlap * 0.2, 1.0)
            recs.append(ReuseRecommendation(
                target_selling_point_id=selling_point_id,
                recommended_asset_id=asset.get("asset_id", ""),
                match_reason=f"标签匹配 {overlap} 个维度",
                confidence=confidence,
            ))

        templates = self._store.list_pattern_templates(
            where={"status": "published", "workspace_id": workspace_id} if workspace_id else {"status": "published"},
        )
        for tpl in templates:
            recs.append(ReuseRecommendation(
                target_selling_point_id=selling_point_id,
                recommended_template_id=tpl.get("template_id", ""),
                match_reason=f"模式模板: {tpl.get('name', '')}",
                confidence=0.5,
            ))

        recs.sort(key=lambda r: r.confidence, reverse=True)
        return recs[:10]

    # ── 全链路闭环：Asset -> Radar/Compiler 反馈 ──────────────

    def feedback_to_radar(self, workspace_id: str = "") -> list[dict]:
        """将高表现资产的模式反馈到 Radar 作为新信号。"""
        from apps.growth_lab.schemas.trend_opportunity import TrendOpportunity

        templates = self._store.list_pattern_templates(
            where={"status": "published", "workspace_id": workspace_id} if workspace_id else {"status": "published"},
        )
        feedback_opps: list[dict] = []
        for tpl in templates:
            if tpl.get("usage_count", 0) > 0:
                continue

            opp = TrendOpportunity(
                title=f"[模式推荐] {tpl.get('name', '')}",
                summary=f"基于高表现素材沉淀的模式：{tpl.get('description', '')}",
                source_platform="internal_asset_graph",
                source_type="internal_feedback",
                freshness_score=0.8,
                actionability_score=0.9,
                relevance_score=0.7,
                suggested_actions=["复用模板", "主图裂变", "前3秒裂变"],
                workspace_id=workspace_id,
                brand_id=tpl.get("brand_id", ""),
                status="new",
            )
            self._store.save_trend_opportunity(opp.model_dump())
            feedback_opps.append(opp.model_dump())

        logger.info("资产->雷达反馈: %d 个模式模板 → %d 个新机会", len(templates), len(feedback_opps))
        return feedback_opps

    # ── 内部工具 ──────────────────────────────────────────────

    @staticmethod
    def _find_best_result(results: list[dict]) -> dict | None:
        best: dict | None = None
        best_ctr = -1.0
        for r in results:
            ctr = r.get("ctr")
            if ctr is not None and ctr > best_ctr:
                best_ctr = ctr
                best = r
        return best

    @staticmethod
    def _auto_tag(task: dict, result: dict) -> list[str]:
        tags: list[str] = []
        platform = task.get("platform", "")
        if platform:
            tags.append(platform)
        variant_type = task.get("variant_type", "")
        if variant_type:
            tags.append(variant_type)
        overall = result.get("overall_result", "")
        if overall == "excellent":
            tags.append("爆款")
        elif overall == "good":
            tags.append("优质")
        return tags
