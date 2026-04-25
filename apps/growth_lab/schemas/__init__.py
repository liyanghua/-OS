"""growth_lab schemas — 裂变系统核心对象模型。"""

from apps.growth_lab.schemas.trend_opportunity import TrendOpportunity
from apps.growth_lab.schemas.selling_point_spec import (
    ExpertAnnotation,
    PlatformExpressionSpec,
    SellingPointSpec,
)
from apps.growth_lab.schemas.main_image_variant import (
    ImageVariantSpec,
    MainImageVariant,
    VariantVariable,
)
from apps.growth_lab.schemas.first3s_variant import (
    ClipAssemblyPlan,
    First3sVariant,
    HookPattern,
    HookScript,
)
from apps.growth_lab.schemas.test_task import (
    AmplificationPlan,
    ResultSnapshot,
    TestTask,
)
from apps.growth_lab.schemas.asset_performance import (
    AssetPerformanceCard,
    PatternTemplate,
    ReuseRecommendation,
)

# 视觉策略编译器（Phase 1-3）策略产物对象
from apps.growth_lab.schemas.visual_strategy_pack import (
    VisualStrategyPack,
    VisualStrategyPackSource,
    VisualStrategyScene,
)
from apps.growth_lab.schemas.strategy_candidate import (
    StrategyCandidate,
    StrategyScore,
    StrategySelectedVariables,
)
from apps.growth_lab.schemas.creative_brief import (
    BriefCanvas,
    BriefCopywriting,
    BriefPeople,
    BriefProduct,
    BriefScene,
    BriefStyle,
    CreativeBrief,
)
from apps.growth_lab.schemas.prompt_spec import (
    PromptGenerationParams,
    PromptProvider,
    PromptSpec,
)
from apps.growth_lab.schemas.feedback_record import (
    BusinessMetrics,
    ExpertScore,
    FeedbackDecision,
    FeedbackRecord,
    RuleWeightHistory,
)

__all__ = [
    "TrendOpportunity",
    "SellingPointSpec",
    "PlatformExpressionSpec",
    "ExpertAnnotation",
    "MainImageVariant",
    "VariantVariable",
    "ImageVariantSpec",
    "First3sVariant",
    "HookPattern",
    "HookScript",
    "ClipAssemblyPlan",
    "TestTask",
    "ResultSnapshot",
    "AmplificationPlan",
    "AssetPerformanceCard",
    "PatternTemplate",
    "ReuseRecommendation",
    # Visual Strategy Compiler
    "VisualStrategyPack",
    "VisualStrategyPackSource",
    "VisualStrategyScene",
    "StrategyCandidate",
    "StrategyScore",
    "StrategySelectedVariables",
    "CreativeBrief",
    "BriefCanvas",
    "BriefScene",
    "BriefProduct",
    "BriefStyle",
    "BriefPeople",
    "BriefCopywriting",
    "PromptSpec",
    "PromptProvider",
    "PromptGenerationParams",
    "FeedbackRecord",
    "ExpertScore",
    "BusinessMetrics",
    "FeedbackDecision",
    "RuleWeightHistory",
]
