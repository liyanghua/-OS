"""StrategyCompiler — 把 RulePack + ContextSpec 编译成 6 个 StrategyCandidate。

承接 docs/SOP_to_content_plan.md 第 10 节（match_rules / 评分公式 / 冲突检测）。

关键设计点：
- archetype 列表完全由 RulePack 配置驱动，不写死 enum。
- 评分公式：score = base_weight × confidence × (1 + boost) × (1 - penalty)。
- CONFLICT_RULES 顶层常量字典，按 category 标签隔离，扩品类不串味。
- 每个 StrategyCandidate.rule_refs 必填，沉淀依据可回链。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from apps.content_planning.schemas.context_spec import ContextSpec
from apps.content_planning.schemas.rule_pack import ArchetypeConfig, RulePack
from apps.content_planning.schemas.rule_spec import RuleSpec
from apps.content_planning.storage.rule_store import RuleStore
from apps.growth_lab.schemas.strategy_candidate import (
    StrategyCandidate,
    StrategyScore,
    StrategySelectedVariables,
)
from apps.growth_lab.schemas.visual_strategy_pack import (
    VisualStrategyPack,
    VisualStrategyPackSource,
)
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore

logger = logging.getLogger(__name__)


# ─── 冲突规则（顶层常量；按 category 隔离） ──────────────────────────
CONFLICT_RULES: dict[str, list[dict[str, Any]]] = {
    "children_desk_mat": [
        {
            "name": "satin_with_kids",
            "description": "高端极简画面不能与儿童密集互动并存",
            "if_keywords": {"pattern_style": ["极简", "高级感"]},
            "incompatible_keywords": {"people_interaction": ["儿童", "家长陪伴", "低龄"]},
            "penalty": 0.4,
        },
        {
            "name": "function_with_warm",
            "description": "功能演示画面不应同时强调温馨马卡龙",
            "if_keywords": {"pattern_style": ["功能演示", "真实清晰"]},
            "incompatible_keywords": {"pattern_style": ["温馨可爱", "马卡龙"]},
            "penalty": 0.25,
        },
    ],
}

# 各维度的 RuleSpec 来源 dimension key
_DIMENSIONS = [
    "visual_core",
    "people_interaction",
    "function_selling_point",
    "pattern_style",
    "marketing_info",
    "differentiation",
]


class StrategyCompiler:
    """编译 RulePack × ContextSpec → 多个 StrategyCandidate。"""

    def __init__(
        self,
        rule_store: RuleStore | None = None,
        visual_strategy_store: VisualStrategyStore | None = None,
    ) -> None:
        self.rule_store = rule_store or RuleStore()
        self.vs_store = visual_strategy_store or VisualStrategyStore()

    def compile(
        self,
        *,
        context: ContextSpec | dict,
        rule_pack: RulePack | dict | None = None,
        rule_pack_id: str | None = None,
    ) -> VisualStrategyPack:
        ctx = context if isinstance(context, ContextSpec) else ContextSpec.model_validate(context)

        pack = self._resolve_rule_pack(rule_pack, rule_pack_id, ctx.category)
        if not pack:
            raise ValueError(f"未找到 category={ctx.category} 的活跃 RulePack")

        rules = self._load_approved_rules(pack)
        if not rules:
            raise ValueError(f"RulePack {pack.id} 没有可用的 approved RuleSpec")

        # 按维度分桶，便于 archetype 匹配
        rules_by_dim: dict[str, list[RuleSpec]] = {d: [] for d in _DIMENSIONS}
        for r in rules:
            rules_by_dim.setdefault(r.dimension, []).append(r)

        archetypes = pack.default_strategy_archetypes or []
        if not archetypes:
            raise ValueError(f"RulePack {pack.id} 缺少 default_strategy_archetypes 配置")

        pack_id = uuid.uuid4().hex[:16]
        candidates: list[StrategyCandidate] = []
        for arche in archetypes:
            cand = self._build_candidate(
                archetype=arche,
                ctx=ctx,
                rules_by_dim=rules_by_dim,
                category=ctx.category,
            )
            cand.visual_strategy_pack_id = pack_id
            candidates.append(cand)

        candidates.sort(key=lambda c: c.score.total, reverse=True)

        vs_pack = VisualStrategyPack(
            id=pack_id,
            source=VisualStrategyPackSource(
                opportunity_card_id=ctx.opportunity_card_id,
                selling_point_spec_id=ctx.selling_point_spec_id,
                brand_id=ctx.brand_id,
            ),
            category=ctx.category,
            scene=ctx.scene,
            rule_pack_id=pack.id,
            context_spec_id=ctx.id,
            candidate_ids=[c.id for c in candidates],
            workspace_id=ctx.workspace_id,
            brand_id=ctx.brand_id,
            status="compiled",
        )
        self.vs_store.save_visual_strategy_pack(vs_pack.model_dump())
        for c in candidates:
            self.vs_store.save_strategy_candidate(c.model_dump())
        return vs_pack

    # ── archetype matching & scoring ────────────────────────────

    def _build_candidate(
        self,
        *,
        archetype: ArchetypeConfig,
        ctx: ContextSpec,
        rules_by_dim: dict[str, list[RuleSpec]],
        category: str,
    ) -> StrategyCandidate:
        selected = StrategySelectedVariables()
        rationale: list[str] = []
        risks: list[str] = []
        rule_refs: list[str] = []
        # 维度 → 评分聚合
        dim_scores: dict[str, list[float]] = {}

        for dim in _DIMENSIONS:
            preferred = archetype.preferred_keywords.get(dim, [])
            avoided = archetype.avoid_keywords + ctx.store_visual_system.avoid_elements
            rule_pool = rules_by_dim.get(dim, [])
            if not rule_pool:
                continue
            best_rule, best_score = self._pick_best_rule(
                rule_pool,
                preferred,
                avoided,
                ctx,
            )
            if not best_rule:
                continue
            chosen = self._project_rule_to_variables(best_rule, preferred)
            getattr(selected, dim).update(chosen)
            rule_refs.append(best_rule.id)
            dim_scores.setdefault(dim, []).append(best_score)
            if best_rule.evidence.source_quote:
                rationale.append(
                    f"[{archetype.name}|{dim}] {best_rule.variable_name}·{best_rule.option_name} ← "
                    f"{best_rule.evidence.source_quote[:60]}"
                )
            for must_avoid in best_rule.constraints.must_avoid[:2]:
                risks.append(f"[{dim}] 避免：{must_avoid}")

        # 冲突检测 → penalty
        conflict_penalty = self._detect_conflicts(category, selected)
        score = self._compute_score(
            archetype=archetype,
            ctx=ctx,
            dim_scores=dim_scores,
            conflict_penalty=conflict_penalty,
        )
        if conflict_penalty > 0:
            risks.append(f"冲突惩罚：-{conflict_penalty:.2f}（维度组合不一致）")

        return StrategyCandidate(
            name=archetype.name,
            archetype=archetype.slug,
            hypothesis=archetype.hypothesis,
            target_audience=list(archetype.target_audience),
            selected_variables=selected,
            rationale=rationale,
            risks=risks,
            score=score,
            rule_refs=rule_refs,
        )

    def _pick_best_rule(
        self,
        rules: list[RuleSpec],
        preferred: list[str],
        avoided: list[str],
        ctx: ContextSpec,
    ) -> tuple[RuleSpec | None, float]:
        best: RuleSpec | None = None
        best_score = -1.0
        for rule in rules:
            # category_scope 不匹配则跳过
            if rule.category_scope and ctx.category not in rule.category_scope:
                continue
            if rule.scene_scope and ctx.scene not in rule.scene_scope:
                continue
            haystack = " ".join(
                [
                    rule.variable_name or "",
                    rule.option_name or "",
                    " ".join(rule.recommendation.creative_direction.values() if isinstance(rule.recommendation.creative_direction, dict) else []),
                    " ".join(rule.scoring.boost_factors),
                    rule.evidence.source_quote or "",
                ]
            )
            boost = sum(0.15 for kw in preferred if kw and kw in haystack)
            penalty = sum(0.25 for kw in avoided if kw and kw in haystack)
            base = rule.scoring.base_weight
            conf = rule.evidence.confidence or 0.5
            score = base * conf * (1 + boost) * max(0.1, 1 - penalty)
            if score > best_score:
                best_score = score
                best = rule
        return best, max(0.0, best_score)

    def _project_rule_to_variables(self, rule: RuleSpec, preferred: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "rule_id": rule.id,
            "variable_category": rule.variable_category,
            "variable_name": rule.variable_name,
            "option_name": rule.option_name,
            "preferred_match": [kw for kw in preferred if kw and kw in (rule.option_name or rule.variable_name)],
        }
        if rule.recommendation.creative_direction:
            result["creative_direction"] = rule.recommendation.creative_direction
        if rule.recommendation.copywriting_direction:
            result["copywriting_direction"] = rule.recommendation.copywriting_direction
        if rule.recommendation.prompt_direction:
            result["prompt_direction"] = rule.recommendation.prompt_direction
        if rule.constraints.must_follow:
            result["must_follow"] = list(rule.constraints.must_follow)
        if rule.constraints.must_avoid:
            result["must_avoid"] = list(rule.constraints.must_avoid)
        return result

    def _detect_conflicts(self, category: str, selected: StrategySelectedVariables) -> float:
        rules = CONFLICT_RULES.get(category, [])
        if not rules:
            return 0.0
        flat: dict[str, str] = {}
        for dim in _DIMENSIONS:
            block = getattr(selected, dim, {}) or {}
            haystack = " ".join(
                str(v) for v in [
                    block.get("variable_name", ""),
                    block.get("option_name", ""),
                    *(block.get("preferred_match", []) or []),
                ]
            )
            flat[dim] = haystack

        penalty = 0.0
        for rule in rules:
            if_keywords = rule.get("if_keywords", {})
            incompatible = rule.get("incompatible_keywords", {})
            if not self._keywords_hit(if_keywords, flat):
                continue
            if self._keywords_hit(incompatible, flat):
                penalty += float(rule.get("penalty", 0.2))
        return min(penalty, 0.8)

    def _keywords_hit(self, keyword_map: dict[str, list[str]], flat: dict[str, str]) -> bool:
        for dim, keywords in keyword_map.items():
            haystack = flat.get(dim, "")
            if any(kw and kw in haystack for kw in keywords):
                return True
        return False

    def _compute_score(
        self,
        *,
        archetype: ArchetypeConfig,
        ctx: ContextSpec,
        dim_scores: dict[str, list[float]],
        conflict_penalty: float,
    ) -> StrategyScore:
        base_total = sum(sum(v) for v in dim_scores.values())
        # 归一到 0-1（一个维度满分 ~= 1.0 × confidence）
        normalized = min(1.0, base_total / max(1, len(_DIMENSIONS)))

        brand_fit = self._brand_fit(archetype, ctx)
        audience_fit = self._audience_fit(archetype, ctx)
        differentiation = self._differentiation_score(archetype, ctx)
        function_clarity = self._dim_avg(dim_scores.get("function_selling_point", []))
        category_recognition = self._dim_avg(dim_scores.get("visual_core", []))
        generation_control = max(0.1, 1.0 - conflict_penalty)
        conversion_potential = (audience_fit + function_clarity) / 2

        total = (
            normalized * 0.35
            + brand_fit * 0.15
            + audience_fit * 0.15
            + differentiation * 0.1
            + function_clarity * 0.1
            + category_recognition * 0.05
            + generation_control * 0.05
            + conversion_potential * 0.05
        )
        total = max(0.0, total - conflict_penalty * 0.3)

        return StrategyScore(
            total=round(total, 4),
            brand_fit=round(brand_fit, 4),
            audience_fit=round(audience_fit, 4),
            differentiation=round(differentiation, 4),
            function_clarity=round(function_clarity, 4),
            category_recognition=round(category_recognition, 4),
            generation_control=round(generation_control, 4),
            conversion_potential=round(conversion_potential, 4),
        )

    def _brand_fit(self, archetype: ArchetypeConfig, ctx: ContextSpec) -> float:
        if not ctx.store_visual_system.style:
            return 0.6
        archetype_text = " ".join(
            [archetype.name, archetype.hypothesis, " ".join(archetype.target_audience)]
            + sum(archetype.preferred_keywords.values(), [])
        )
        score = 0.5
        if ctx.store_visual_system.style and ctx.store_visual_system.style in archetype_text:
            score += 0.3
        for color in ctx.store_visual_system.colors:
            if color and color in archetype_text:
                score += 0.05
        for avoid in ctx.store_visual_system.avoid_elements:
            if avoid and avoid in archetype_text:
                score -= 0.1
        return max(0.0, min(1.0, score))

    def _audience_fit(self, archetype: ArchetypeConfig, ctx: ContextSpec) -> float:
        if not archetype.target_audience:
            return 0.5
        if not ctx.audience.buyer and not ctx.audience.user:
            return 0.5
        haystack = " ".join([ctx.audience.buyer, ctx.audience.user, " ".join(ctx.audience.decision_logic)])
        hits = sum(1 for tag in archetype.target_audience if tag and tag in haystack)
        if hits == 0:
            return 0.4
        return min(1.0, 0.5 + 0.2 * hits)

    def _differentiation_score(self, archetype: ArchetypeConfig, ctx: ContextSpec) -> float:
        common = " ".join(ctx.competitor.common_visuals + ctx.competitor.common_claims)
        archetype_keywords = sum(archetype.preferred_keywords.values(), [])
        overlap = sum(1 for kw in archetype_keywords if kw and kw in common)
        diff_text = " ".join(ctx.competitor.differentiation_opportunities)
        diff_hits = sum(1 for kw in archetype_keywords if kw and kw in diff_text)
        score = 0.5 + 0.15 * diff_hits - 0.1 * overlap
        return max(0.0, min(1.0, score))

    def _dim_avg(self, scores: list[float]) -> float:
        if not scores:
            return 0.5
        return min(1.0, sum(scores) / len(scores))

    # ── data loading ─────────────────────────────────────────────

    def _resolve_rule_pack(
        self,
        rule_pack: RulePack | dict | None,
        rule_pack_id: str | None,
        category: str,
    ) -> RulePack | None:
        if isinstance(rule_pack, RulePack):
            return rule_pack
        if isinstance(rule_pack, dict):
            return RulePack.model_validate(rule_pack)
        if rule_pack_id:
            data = self.rule_store.get_rule_pack(rule_pack_id)
            return RulePack.model_validate(data) if data else None
        active = self.rule_store.get_active_rule_pack(category)
        return RulePack.model_validate(active) if active else None

    def _load_approved_rules(self, pack: RulePack) -> list[RuleSpec]:
        rules: list[RuleSpec] = []
        for rule_id in pack.rule_ids:
            data = self.rule_store.get_rule_spec(rule_id)
            if not data:
                continue
            rule = RuleSpec.model_validate(data)
            if rule.review.status != "approved":
                continue
            rules.append(rule)
        return rules
