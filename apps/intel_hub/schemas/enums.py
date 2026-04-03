from __future__ import annotations

from enum import StrEnum


class WatchlistType(StrEnum):
    COMPETITOR = "competitor"
    CATEGORY = "category"
    PLATFORM_POLICY = "platform_policy"
    SCENE = "scene"
    STYLE = "style"
    NEED = "need"
    RISK_FACTOR = "risk_factor"
    MATERIAL = "material"
    CONTENT_PATTERN = "content_pattern"
    VISUAL_PATTERN = "visual_pattern"
    AUDIENCE = "audience"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_FOLLOWUP = "needs_followup"

    @classmethod
    def _missing_(cls, value: object) -> ReviewStatus | None:
        if not isinstance(value, str):
            return None
        legacy_mapping = {
            "pending_review": cls.PENDING,
            "human_reviewed": cls.ACCEPTED,
            "dismissed": cls.REJECTED,
        }
        return legacy_mapping.get(value.strip().lower())


class CardKind(StrEnum):
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    INSIGHT = "insight"
    VISUAL_PATTERN = "visual_pattern"
    DEMAND_SPEC = "demand_spec"


class OpportunityType(StrEnum):
    TREND = "trend"
    DEMAND = "demand"
    CONTENT = "content"
    PRODUCT = "product"
    VISUAL = "visual"


class RiskType(StrEnum):
    PRODUCT = "product"
    VISUAL = "visual"
    CONTENT = "content"
    PERCEPTION = "perception"
    CONVERSION = "conversion"


class InsightType(StrEnum):
    AUDIENCE = "audience"
    SCENE = "scene"
    STYLE = "style"
    EXPRESSION = "expression"
    CONVERSION = "conversion"


class TargetRole(StrEnum):
    CEO = "ceo"
    MARKETING_DIRECTOR = "marketing_director"
    PRODUCT_DIRECTOR = "product_director"
    VISUAL_DIRECTOR = "visual_director"


class CommentSignalType(StrEnum):
    PURCHASE_INTENT = "purchase_intent"
    POSITIVE_FEEDBACK = "positive_feedback"
    NEGATIVE_FEEDBACK = "negative_feedback"
    QUESTION = "question"
    COMPARISON = "comparison"
    UNMET_NEED = "unmet_need"
    TRUST_GAP = "trust_gap"


class ReviewDecisionSource(StrEnum):
    MANUAL = "manual"
    SYSTEM = "system"
