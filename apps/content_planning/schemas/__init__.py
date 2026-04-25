"""content_planning schemas - 内容策划编译链的全部数据模型。"""

from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    ImageSlotBrief,
    TitleCandidate,
    TitleGenerationResult,
)
from apps.content_planning.schemas.agent_workflow import (
    AgentDiscussionRecord,
    AgentRun,
    AgentSessionRef,
    AgentTask,
    ProposalDecision,
    ProposalDiff,
    ProposalFieldChange,
    StageProposal,
    StageScorecard,
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

# 视觉策略编译器（Phase 1-3）规则生产线对象
from apps.content_planning.schemas.source_document import SOPDimension, SourceDocument
from apps.content_planning.schemas.rule_spec import (
    RuleConstraints,
    RuleEvidence,
    RuleLifecycle,
    RuleLifecycleStatus,
    RuleRecommendation,
    RuleReview,
    RuleReviewStatus,
    RuleScoring,
    RuleSpec,
    RuleTrigger,
)
from apps.content_planning.schemas.rule_pack import (
    CHILDREN_DESK_MAT_ARCHETYPES,
    ArchetypeConfig,
    RulePack,
    RulePackMetrics,
)
from apps.content_planning.schemas.context_spec import (
    ContextAudience,
    ContextCompetitor,
    ContextPlatform,
    ContextProduct,
    ContextSpec,
    ContextStoreVisualSystem,
    VisualScene,
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
    "AgentSessionRef",
    "AgentTask",
    "AgentRun",
    "AgentDiscussionRecord",
    "ProposalFieldChange",
    "ProposalDiff",
    "StageProposal",
    "ProposalDecision",
    "StageScorecard",
    # Visual Strategy Compiler
    "SourceDocument",
    "SOPDimension",
    "RuleSpec",
    "RuleTrigger",
    "RuleRecommendation",
    "RuleConstraints",
    "RuleScoring",
    "RuleEvidence",
    "RuleReview",
    "RuleLifecycle",
    "RuleReviewStatus",
    "RuleLifecycleStatus",
    "RulePack",
    "ArchetypeConfig",
    "RulePackMetrics",
    "CHILDREN_DESK_MAT_ARCHETYPES",
    "ContextSpec",
    "ContextProduct",
    "ContextStoreVisualSystem",
    "ContextAudience",
    "ContextCompetitor",
    "ContextPlatform",
    "VisualScene",
]
