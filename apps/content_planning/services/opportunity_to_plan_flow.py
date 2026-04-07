"""OpportunityToPlanFlow：从 promoted 机会卡到完整内容策划的一站式编排。"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
from apps.content_planning.exceptions import OpportunityNotPromotedError
from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    TitleGenerationResult,
)
from apps.content_planning.schemas.note_plan import NewNotePlan
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.schemas.template_match_result import (
    TemplateMatchEntry,
    TemplateMatchResult,
)
from apps.content_planning.services.body_generator import BodyGenerator
from apps.content_planning.services.brief_compiler import BriefCompiler
from apps.content_planning.services.image_brief_generator import ImageBriefGenerator
from apps.content_planning.services.new_note_plan_compiler import NewNotePlanCompiler
from apps.content_planning.services.strategy_generator import RewriteStrategyGenerator
from apps.content_planning.services.title_generator import TitleGenerator
from apps.template_extraction.agent import TemplateMatcher, TemplateRetriever

logger = logging.getLogger(__name__)


class OpportunityToPlanFlow:
    """统一编排入口：promoted 卡 -> Brief -> 选模板 -> Strategy -> NotePlan -> (可选) 内容生成。"""

    def __init__(self, adapter: IntelHubAdapter | None = None) -> None:
        self._adapter = adapter or IntelHubAdapter()
        self._brief_compiler = BriefCompiler()
        self._strategy_gen = RewriteStrategyGenerator()
        self._plan_compiler = NewNotePlanCompiler()
        self._title_gen = TitleGenerator()
        self._body_gen = BodyGenerator()
        self._image_gen = ImageBriefGenerator()
        self._retriever = TemplateRetriever()

    def build_brief(self, opportunity_id: str) -> OpportunityBrief:
        card = self._adapter.get_card(opportunity_id)
        if card is None:
            raise ValueError(f"机会卡 {opportunity_id} 未找到")
        if card.opportunity_status != "promoted":
            raise OpportunityNotPromotedError(opportunity_id, card.opportunity_status)

        source_notes = self._adapter.get_source_notes(card.source_note_ids)
        parsed_note = source_notes[0] if source_notes else None
        review_summary = self._adapter.get_review_summary(opportunity_id)

        return self._brief_compiler.compile(card, parsed_note, review_summary)

    def build_note_plan(
        self,
        opportunity_id: str,
        *,
        with_generation: bool = False,
        preferred_template_id: str | None = None,
    ) -> dict[str, Any]:
        """完整编排流程。

        返回 dict 包含:
            brief, match_result, strategy, note_plan,
            以及可选的 title_gen, body_gen, image_gen
        """
        brief = self.build_brief(opportunity_id)

        templates = self._retriever.list_templates()
        if not templates:
            raise ValueError("模板库为空，无法匹配")

        matcher = TemplateMatcher(templates)
        matches = matcher.match_templates(brief=brief, top_k=len(templates))

        if preferred_template_id:
            primary = next((m for m in matches if m.template_id == preferred_template_id), None)
            if primary is None:
                primary = matches[0] if matches else None
        else:
            primary = matches[0] if matches else None

        if primary is None:
            raise ValueError("无可用模板匹配结果")

        match_result = TemplateMatchResult(
            opportunity_id=brief.opportunity_id,
            brief_id=brief.brief_id,
            primary_template=TemplateMatchEntry(
                template_id=primary.template_id,
                template_name=primary.template_name,
                score=primary.score,
                reason=primary.reason,
            ),
            secondary_templates=[
                TemplateMatchEntry(
                    template_id=m.template_id,
                    template_name=m.template_name,
                    score=m.score,
                    reason=m.reason,
                )
                for m in matches[1:4]
            ],
            rejected_templates=[
                TemplateMatchEntry(
                    template_id=m.template_id,
                    template_name=m.template_name,
                    score=m.score,
                    reason=m.reason,
                )
                for m in matches
                if m.score <= 0
            ],
        )

        selected_tpl = self._retriever.get_template(primary.template_id)
        if selected_tpl is None:
            raise ValueError(f"模板 {primary.template_id} 加载失败")

        strategy = self._strategy_gen.generate(brief, match_result, selected_tpl)
        note_plan = self._plan_compiler.compile(brief, strategy, match_result, selected_tpl)

        result: dict[str, Any] = {
            "brief": brief.model_dump(mode="json"),
            "match_result": match_result.model_dump(mode="json"),
            "strategy": strategy.model_dump(mode="json"),
            "note_plan": note_plan.model_dump(mode="json"),
        }

        if with_generation:
            result["generated"] = self._run_generation(note_plan, strategy)

        return result

    def _run_generation(
        self,
        plan: NewNotePlan,
        strategy: RewriteStrategy,
    ) -> dict[str, Any]:
        title_result = self._title_gen.generate(plan, strategy)
        body_result = self._body_gen.generate(plan, strategy)
        image_result = self._image_gen.generate(plan, strategy)
        return {
            "titles": title_result.model_dump(mode="json"),
            "body": body_result.model_dump(mode="json"),
            "image_briefs": image_result.model_dump(mode="json"),
        }
