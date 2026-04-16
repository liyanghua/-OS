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
]
