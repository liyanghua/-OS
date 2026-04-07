"""BriefCompiler：从 promoted 机会卡提炼 OpportunityBrief。"""

from __future__ import annotations

from typing import Any

from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard


_GOAL_MAP: dict[str, str] = {
    "visual": "种草收藏",
    "scene": "种草收藏",
    "demand": "转化",
    "product": "转化",
    "content": "展示种草",
}

_TEMPLATE_HINT_MAP: dict[str, list[str]] = {
    "种草收藏": ["scene_seed", "style_anchor"],
    "转化": ["budget_hero", "texture_proof"],
    "展示种草": ["scene_seed", "style_anchor", "texture_proof"],
}


class BriefCompiler:
    """规则优先的 Brief 编译器，逐字段从机会卡提取。"""

    def compile(
        self,
        card: XHSOpportunityCard,
        parsed_note: dict[str, Any] | None = None,
        review_summary: dict[str, Any] | None = None,
    ) -> OpportunityBrief:
        content_goal = self._infer_content_goal(card)
        return OpportunityBrief(
            opportunity_id=card.opportunity_id,
            source_note_ids=list(card.source_note_ids),
            opportunity_type=card.opportunity_type,
            opportunity_title=card.title,
            opportunity_summary=card.summary,
            target_user=self._extract_target_user(card),
            target_scene=self._extract_target_scene(card),
            core_motive=self._extract_core_motive(card),
            content_goal=content_goal,
            primary_value=self._extract_primary_value(card),
            secondary_values=self._extract_secondary_values(card),
            visual_style_direction=self._extract_visual_direction(card),
            price_positioning=self._extract_price_positioning(card, parsed_note),
            template_hints=self._generate_template_hints(card, content_goal),
            avoid_directions=self._extract_avoid_directions(card),
            proof_from_source=self._extract_proof(card),
        )

    @staticmethod
    def _extract_target_scene(card: XHSOpportunityCard) -> list[str]:
        scenes: list[str] = []
        scenes.extend(card.scene_refs[:5])
        for tag in card.entity_refs[:3]:
            if any(kw in tag for kw in ("场景", "桌", "餐", "茶", "聚", "早")):
                scenes.append(tag)
        return list(dict.fromkeys(scenes))[:6]

    @staticmethod
    def _extract_target_user(card: XHSOpportunityCard) -> list[str]:
        users: list[str] = []
        users.extend(card.audience_refs[:5])
        for ref in card.need_refs[:3]:
            if any(kw in ref for kw in ("人群", "用户", "宝妈", "上班族", "学生", "租房")):
                users.append(ref)
        return list(dict.fromkeys(users))[:6]

    @staticmethod
    def _extract_core_motive(card: XHSOpportunityCard) -> str | None:
        if card.need_refs:
            return card.need_refs[0]
        if card.summary:
            return card.summary[:60]
        return None

    @staticmethod
    def _infer_content_goal(card: XHSOpportunityCard) -> str:
        return _GOAL_MAP.get(card.opportunity_type, "种草收藏")

    @staticmethod
    def _extract_primary_value(card: XHSOpportunityCard) -> str | None:
        if card.value_proposition_refs:
            return card.value_proposition_refs[0]
        if card.need_refs:
            return card.need_refs[0]
        return None

    @staticmethod
    def _extract_secondary_values(card: XHSOpportunityCard) -> list[str]:
        vals: list[str] = []
        vals.extend(card.value_proposition_refs[1:4])
        vals.extend(card.need_refs[1:3])
        return list(dict.fromkeys(vals))[:5]

    @staticmethod
    def _extract_visual_direction(card: XHSOpportunityCard) -> list[str]:
        dirs: list[str] = []
        dirs.extend(card.style_refs[:4])
        dirs.extend(card.visual_pattern_refs[:3])
        return list(dict.fromkeys(dirs))[:6]

    @staticmethod
    def _extract_price_positioning(
        card: XHSOpportunityCard,
        parsed_note: dict[str, Any] | None,
    ) -> str | None:
        for ref in card.need_refs + card.entity_refs:
            if any(kw in ref for kw in ("平价", "性价比", "高端", "轻奢", "便宜", "贵")):
                return ref
        if parsed_note:
            price_info = parsed_note.get("selling_theme_signals", {}).get("price_tier")
            if price_info:
                return str(price_info)
        return None

    @staticmethod
    def _generate_template_hints(card: XHSOpportunityCard, content_goal: str | None) -> list[str]:
        hints = _TEMPLATE_HINT_MAP.get(content_goal or "", [])
        if card.opportunity_type == "visual":
            hints = list(dict.fromkeys(["style_anchor", "texture_proof"] + hints))
        if card.opportunity_type == "scene":
            hints = list(dict.fromkeys(["scene_seed", "occasion_gift"] + hints))
        return hints[:4]

    @staticmethod
    def _extract_avoid_directions(card: XHSOpportunityCard) -> list[str]:
        avoids: list[str] = []
        avoids.extend(card.risk_refs[:3])
        return avoids

    @staticmethod
    def _extract_proof(card: XHSOpportunityCard) -> list[str]:
        proofs: list[str] = []
        for ev in card.evidence_refs[:5]:
            snippet = getattr(ev, "snippet", "") or getattr(ev, "text", "")
            if snippet:
                proofs.append(str(snippet)[:200])
        return proofs
