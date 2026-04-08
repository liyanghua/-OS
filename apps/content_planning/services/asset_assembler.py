"""AssetAssembler：从 GenerationResult 组装 AssetBundle。"""

from __future__ import annotations

import logging

from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    TitleGenerationResult,
)
from apps.content_planning.schemas.lineage import PlanLineage

logger = logging.getLogger(__name__)


class AssetAssembler:
    """从生成结果组装 AssetBundle。"""

    @staticmethod
    def assemble(
        *,
        opportunity_id: str,
        plan_id: str = "",
        template_id: str = "",
        template_name: str = "",
        titles: TitleGenerationResult | None = None,
        body: BodyGenerationResult | None = None,
        image_briefs: ImageBriefGenerationResult | None = None,
        lineage: PlanLineage | None = None,
    ) -> AssetBundle:
        title_candidates = []
        if titles:
            for t in titles.titles:
                title_candidates.append({
                    "title_text": t.title_text,
                    "axis": t.axis,
                    "rationale": t.rationale,
                })

        body_outline: list[str] = []
        body_draft = ""
        if body:
            body_outline = list(body.body_outline)
            body_draft = body.body_draft

        image_execution_briefs = []
        if image_briefs:
            for sb in image_briefs.slot_briefs:
                image_execution_briefs.append(sb.model_dump(mode="json"))

        export_status = "ready" if (title_candidates and body_draft) else "draft"

        return AssetBundle(
            opportunity_id=opportunity_id,
            plan_id=plan_id,
            template_id=template_id,
            template_name=template_name,
            title_candidates=title_candidates,
            body_outline=body_outline,
            body_draft=body_draft,
            image_execution_briefs=image_execution_briefs,
            export_status=export_status,
            lineage=lineage,
        )
