from __future__ import annotations

from enum import StrEnum


class WatchlistType(StrEnum):
    COMPETITOR = "competitor"
    CATEGORY = "category"
    PLATFORM_POLICY = "platform_policy"


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


class ReviewDecisionSource(StrEnum):
    MANUAL = "manual"
    SYSTEM = "system"
