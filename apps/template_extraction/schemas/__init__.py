"""模板提取链路中的 Pydantic 模型导出。"""

from apps.template_extraction.schemas.agent_plan import ImageSlotPlan, MainImagePlan
from apps.template_extraction.schemas.cluster_sample import ClusterSample
from apps.template_extraction.schemas.cover_features import CoverFeaturePack
from apps.template_extraction.schemas.gallery_features import GalleryFeaturePack
from apps.template_extraction.schemas.labeled_note import XHSNoteLabeled
from apps.template_extraction.schemas.labels import (
    BusinessSemanticLabel,
    CoverTaskLabel,
    GalleryTaskLabel,
    LabelResult,
    RiskLabel,
    VisualStructureLabel,
)
from apps.template_extraction.schemas.template import (
    ClusterFeatures,
    CopyRules,
    DerivationRules,
    EvaluationMetrics,
    ProductVisibilityRules,
    SceneRules,
    TableclothMainImageStrategyTemplate,
    VisualRules,
)

__all__ = [
    "BusinessSemanticLabel",
    "ClusterFeatures",
    "ClusterSample",
    "CopyRules",
    "CoverFeaturePack",
    "CoverTaskLabel",
    "DerivationRules",
    "EvaluationMetrics",
    "GalleryFeaturePack",
    "GalleryTaskLabel",
    "ImageSlotPlan",
    "LabelResult",
    "MainImagePlan",
    "ProductVisibilityRules",
    "RiskLabel",
    "SceneRules",
    "TableclothMainImageStrategyTemplate",
    "VisualRules",
    "VisualStructureLabel",
    "XHSNoteLabeled",
]
