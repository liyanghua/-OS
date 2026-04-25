"""context_compiler — 组装 ContextSpec 上下文。

将 XHSOpportunityCard / SellingPointSpec / BrandProfile / 用户输入的 store_visual
聚合到 ContextSpec，作为后续 StrategyCompiler 的输入。

注意：MVP 不为 StoreVisualSystem 单建 schema，
所有店铺视觉特征都装进 context.store_visual_system 字段。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.schemas.context_spec import (
    ContextAudience,
    ContextCompetitor,
    ContextPlatform,
    ContextProduct,
    ContextSpec,
    ContextStoreVisualSystem,
    VisualScene,
)
from apps.content_planning.storage.rule_store import RuleStore

logger = logging.getLogger(__name__)


_DEFAULT_STORE_VISUAL: dict[str, Any] = {
    "style": "森系简约",
    "colors": ["奶白", "浅灰", "森绿"],
    "typography": "细黑体 + 衬线点缀",
    "image_tone": "明亮通透",
    "allowed_elements": ["叶子", "纯色背景", "硅胶质感"],
    "avoid_elements": ["满印卡通", "高饱和", "杂乱"],
    "example_images": [],
}


class ContextCompiler:
    """构建一次策略编译的上下文包。"""

    def __init__(self, store: RuleStore | None = None) -> None:
        self.store = store or RuleStore()

    def compile_from_opportunity(
        self,
        opportunity_card: dict | Any,
        *,
        category: str,
        scene: VisualScene = "taobao_main_image",
        selling_point_spec: dict | None = None,
        brand_profile: dict | None = None,
        store_visual_overrides: dict | None = None,
        product_overrides: dict | None = None,
    ) -> ContextSpec:
        """从 OpportunityCard 组装 ContextSpec。"""
        oc = opportunity_card if isinstance(opportunity_card, dict) else opportunity_card.model_dump()

        product = self._build_product(oc, category=category, brand_profile=brand_profile, overrides=product_overrides)
        store_visual = self._build_store_visual(brand_profile, store_visual_overrides)
        audience = self._build_audience(oc, selling_point_spec)
        competitor = self._build_competitor(oc)
        platform = self._build_platform(scene)

        ctx = ContextSpec(
            source_type="opportunity_card",
            source_id=oc.get("opportunity_id", ""),
            workspace_id=(brand_profile or {}).get("workspace_id", ""),
            brand_id=(brand_profile or {}).get("brand_id", ""),
            category=category,
            scene=scene,
            product=product,
            store_visual_system=store_visual,
            audience=audience,
            competitor=competitor,
            platform=platform,
            selling_point_spec_id=(selling_point_spec or {}).get("spec_id", ""),
            opportunity_card_id=oc.get("opportunity_id", ""),
            extra={
                "opportunity_summary": oc.get("summary", ""),
                "opportunity_type": oc.get("opportunity_type", ""),
                "selling_points": oc.get("selling_points", []),
                "hook": oc.get("hook", ""),
            },
        )
        self.store.save_context_spec(ctx.model_dump())
        return ctx

    def compile_manual(
        self,
        *,
        category: str,
        scene: VisualScene = "taobao_main_image",
        product: dict | None = None,
        store_visual: dict | None = None,
        audience: dict | None = None,
        brand_profile: dict | None = None,
    ) -> ContextSpec:
        """手动构造 ContextSpec（专家测试 / 扩品类调试）。"""
        ctx = ContextSpec(
            source_type="manual",
            workspace_id=(brand_profile or {}).get("workspace_id", ""),
            brand_id=(brand_profile or {}).get("brand_id", ""),
            category=category,
            scene=scene,
            product=ContextProduct(**(product or {"category": category})),
            store_visual_system=self._build_store_visual(brand_profile, store_visual),
            audience=ContextAudience(**(audience or {})),
            platform=self._build_platform(scene),
        )
        self.store.save_context_spec(ctx.model_dump())
        return ctx

    # ── helpers ─────────────────────────────────────────────────

    def _build_product(
        self,
        oc: dict,
        *,
        category: str,
        brand_profile: dict | None,
        overrides: dict | None,
    ) -> ContextProduct:
        # 从 OpportunityCard 与 BrandProfile 合成；overrides 优先覆盖
        base = {
            "name": oc.get("title", ""),
            "category": category,
            "claims": list(oc.get("selling_points", []) or []),
            "target_age_range": "",
            "gender": "",
            "material": "",
            "price_band": "",
            "pattern_theme": "",
        }
        if brand_profile:
            if brand_profile.get("name"):
                base["name"] = base["name"] or brand_profile["name"]
        if overrides:
            base.update({k: v for k, v in overrides.items() if v is not None})
        return ContextProduct(**base)

    def _build_store_visual(
        self,
        brand_profile: dict | None,
        overrides: dict | None,
    ) -> ContextStoreVisualSystem:
        merged: dict[str, Any] = dict(_DEFAULT_STORE_VISUAL)
        if brand_profile:
            tone = brand_profile.get("tone_of_voice") or []
            if tone:
                merged["style"] = tone[0]
            forbidden = brand_profile.get("forbidden_terms") or []
            if forbidden:
                merged["avoid_elements"] = list({*merged.get("avoid_elements", []), *forbidden})
        if overrides:
            for key, value in overrides.items():
                if value is None:
                    continue
                if key in {"colors", "allowed_elements", "avoid_elements", "example_images"}:
                    merged[key] = list(value or [])
                else:
                    merged[key] = value
        return ContextStoreVisualSystem(**merged)

    def _build_audience(
        self,
        oc: dict,
        selling_point_spec: dict | None,
    ) -> ContextAudience:
        buyer = oc.get("audience", "") or ""
        user = ""
        decision_logic: list[str] = []
        if selling_point_spec:
            tg_people = selling_point_spec.get("target_people", []) or []
            tg_scenarios = selling_point_spec.get("target_scenarios", []) or []
            if tg_people and not buyer:
                buyer = "; ".join(tg_people[:2])
            decision_logic.extend([f"人群偏好：{p}" for p in tg_people[:3]])
            decision_logic.extend([f"使用场景：{s}" for s in tg_scenarios[:3]])
        # 推断使用者：儿童类目下 buyer=家长，user=儿童
        if any(k in buyer for k in ["宝妈", "妈妈", "家长"]):
            user = "儿童"
        return ContextAudience(buyer=buyer, user=user, decision_logic=decision_logic)

    def _build_competitor(self, oc: dict) -> ContextCompetitor:
        common_visuals: list[str] = []
        common_claims: list[str] = []
        diff_opps: list[str] = []
        # 从机会卡 visual_pattern_refs / value_proposition_refs 推断（粗粒度）
        common_visuals.extend(list(oc.get("visual_pattern_refs", []) or []))
        common_claims.extend(list(oc.get("value_proposition_refs", []) or []))
        if oc.get("why_worth_doing"):
            diff_opps.append(oc["why_worth_doing"])
        return ContextCompetitor(
            common_visuals=common_visuals,
            common_claims=common_claims,
            differentiation_opportunities=diff_opps,
        )

    def _build_platform(self, scene: VisualScene) -> ContextPlatform:
        if scene == "xhs_cover":
            return ContextPlatform(ratio="3:4", copy_limit=2, product_visibility_min=0.5)
        if scene == "video_first_frame":
            return ContextPlatform(ratio="9:16", copy_limit=1, product_visibility_min=0.5)
        if scene == "detail_first_screen":
            return ContextPlatform(ratio="1:1", copy_limit=4, product_visibility_min=0.55)
        return ContextPlatform(ratio="1:1", copy_limit=3, product_visibility_min=0.6)
