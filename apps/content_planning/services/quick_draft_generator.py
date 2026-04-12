"""QuickDraftGenerator: 从 V6 Brief 一次 LLM 调用生成小红书笔记草稿。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.schemas.expert_scorecard import ExpertScorecard
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.services.prompt_registry import load_prompt
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard

logger = logging.getLogger(__name__)


class QuickDraftGenerator:
    """从 V6 Brief + 可选 Scorecard/Card 快速生成笔记草稿。

    输出格式兼容 previewCanvas.renderPreview(data)。
    """

    def generate(
        self,
        brief: OpportunityBrief,
        scorecard: ExpertScorecard | None = None,
        card: XHSOpportunityCard | None = None,
    ) -> dict[str, Any]:
        prompt_cfg = load_prompt("quick_draft")
        system_prompt = prompt_cfg.get("system", "你是资深小红书内容创作专家。")
        output_hint = prompt_cfg.get("output_hint", "")

        user_prompt = self._build_user_prompt(brief, scorecard, card)
        full_user = f"{user_prompt}\n\n{output_hint}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=full_user),
        ]

        try:
            response = llm_router.chat(
                messages, temperature=0.55, max_tokens=4096,
            )
            if response.degraded or not response.content.strip():
                logger.warning("LLM degraded for quick_draft, falling back to rules")
                return self._rule_fallback(brief, card)

            draft = self._parse_response(response.content)
            if not draft.get("selected_title") and not draft.get("final_body"):
                return self._rule_fallback(brief, card)
            draft.setdefault("character_count", len(draft.get("final_body", "")))
            draft["mode"] = "llm"
            return draft

        except Exception:
            logger.warning("QuickDraft LLM failed, falling back", exc_info=True)
            return self._rule_fallback(brief, card)

    def _build_user_prompt(
        self,
        brief: OpportunityBrief,
        scorecard: ExpertScorecard | None,
        card: XHSOpportunityCard | None,
    ) -> str:
        sections: list[str] = []

        sections.append(f"## 机会标题\n{brief.opportunity_title or '(未填)'}")
        sections.append(f"## 内容目标\n{brief.content_goal or brief.opportunity_summary or '(未填)'}")

        audience = brief.target_audience or ""
        if card and not audience:
            audience = card.audience or ", ".join(card.audience_refs[:3])
        if audience:
            sections.append(f"## 目标受众\n{audience}")

        scene = ", ".join(brief.target_scene) if brief.target_scene else ""
        if card and not scene:
            scene = card.scene or ", ".join(card.scene_refs[:3])
        if scene:
            sections.append(f"## 场景\n{scene}")

        if brief.title_directions:
            sections.append(f"## 标题方向参考\n" + "\n".join(f"- {t}" for t in brief.title_directions))

        if brief.opening_hook:
            sections.append(f"## 开场钩子\n{brief.opening_hook}")

        if brief.content_structure:
            sections.append(f"## 内容结构\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(brief.content_structure)))

        if brief.core_claim:
            sections.append(f"## 核心主张\n{brief.core_claim}")

        if brief.proof_points:
            sections.append(f"## 论证要点\n" + "\n".join(f"- {p}" for p in brief.proof_points))

        if brief.cta:
            sections.append(f"## 行动引导\n{brief.cta}")

        if brief.tone:
            sections.append(f"## 语气风格\n{brief.tone}")

        if brief.cover_direction:
            sections.append(f"## 封面方向\n{brief.cover_direction}")

        if brief.visual_direction:
            sections.append(f"## 视觉方向\n{brief.visual_direction}")

        if brief.risk_boundaries:
            sections.append(f"## 避免事项\n" + "\n".join(f"- {r}" for r in brief.risk_boundaries))

        if card:
            extras: list[str] = []
            if card.pain_point:
                extras.append(f"痛点: {card.pain_point}")
            if card.hook:
                extras.append(f"钩子: {card.hook}")
            if card.selling_points:
                extras.append(f"卖点: {', '.join(card.selling_points[:5])}")
            if extras:
                sections.append(f"## 补充上下文（来自机会卡）\n" + "\n".join(extras))

        if scorecard:
            strengths: list[str] = []
            weaknesses: list[str] = []
            for dim in scorecard.dimensions:
                effective = (1.0 - dim.score) if dim.inverse else dim.score
                if effective >= 0.7:
                    strengths.append(f"{dim.label}: {effective:.0%}")
                elif effective < 0.4:
                    weaknesses.append(f"{dim.label}: {effective:.0%}")
            hints: list[str] = []
            if strengths:
                hints.append(f"强势维度: {', '.join(strengths)}")
            if weaknesses:
                hints.append(f"待加强: {', '.join(weaknesses)}")
            if scorecard.upgrade_advice:
                hints.append(f"优化建议: {'; '.join(scorecard.upgrade_advice[:3])}")
            if hints:
                sections.append(f"## 评分卡提示\n" + "\n".join(hints))

        return "\n\n".join(sections)

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        text = raw.strip()

        fence = re.search(r"```(?:json)?\s*\n([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        elif text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]).rstrip("`").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        brace = re.search(r"\{", text)
        if brace:
            candidate = text[brace.start():]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            patched = candidate.rstrip().rstrip(",")
            depth_brace = patched.count("{") - patched.count("}")
            depth_bracket = patched.count("[") - patched.count("]")
            patched += '""' if patched.endswith(":") else ""
            patched += "]" * max(depth_bracket, 0)
            patched += "}" * max(depth_brace, 0)
            try:
                return json.loads(patched)
            except json.JSONDecodeError:
                pass
        return {}

    @staticmethod
    def _rule_fallback(
        brief: OpportunityBrief,
        card: XHSOpportunityCard | None,
    ) -> dict[str, Any]:
        title = ""
        if brief.title_directions:
            title = brief.title_directions[0]
        elif brief.opportunity_title:
            title = brief.opportunity_title
        elif card and card.title:
            title = card.title

        body_parts: list[str] = []
        if brief.opening_hook:
            body_parts.append(brief.opening_hook)
        if brief.content_structure:
            body_parts.extend(brief.content_structure)
        if brief.core_claim:
            body_parts.append(brief.core_claim)
        if brief.proof_points:
            body_parts.extend(brief.proof_points[:3])
        if brief.cta:
            body_parts.append(brief.cta)
        if not body_parts:
            body_parts.append(brief.opportunity_summary or brief.content_goal or "")

        body = "\n\n".join(p for p in body_parts if p)

        return {
            "selected_title": title,
            "title_rationale": "基于 Brief 字段自动拼装（规则降级）",
            "final_body": body,
            "cover_image_prompt": brief.cover_direction or brief.visual_direction or "",
            "hashtags": [],
            "topic_tags": [],
            "character_count": len(body),
            "mode": "rule_fallback",
        }
