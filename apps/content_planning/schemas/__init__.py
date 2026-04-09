"""content_planning schemas - 内容策划编译链的全部数据模型。"""

from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    ImageSlotBrief,
    TitleCandidate,
    TitleGenerationResult,
)
from apps.content_planning.schemas.evaluation import (
    DimensionScore,
    PipelineEvaluation,
    PipelineMetrics,
    StageEvaluation,
)
from apps.content_planning.schemas.note_plan import (
    BodyPlan,
    NewNotePlan,
    TitlePlan,
)
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.schemas.template_match_result import (
    TemplateMatchEntry,
    TemplateMatchResult,
)

__all__ = [
    "OpportunityBrief",
    "RewriteStrategy",
    "TitlePlan",
    "BodyPlan",
    "NewNotePlan",
    "TitleCandidate",
    "TitleGenerationResult",
    "BodyGenerationResult",
    "ImageSlotBrief",
    "ImageBriefGenerationResult",
    "TemplateMatchEntry",
    "TemplateMatchResult",
    "DimensionScore",
    "StageEvaluation",
    "PipelineMetrics",
    "PipelineEvaluation",
]
