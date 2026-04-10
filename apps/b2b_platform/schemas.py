from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _api_token() -> str:
    return secrets.token_urlsafe(24)


class Organization(BaseModel):
    organization_id: str = Field(default_factory=lambda: _short_id("org"))
    name: str
    slug: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Workspace(BaseModel):
    workspace_id: str = Field(default_factory=lambda: _short_id("ws"))
    organization_id: str
    name: str
    slug: str
    status: Literal["active", "paused"] = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrandProfile(BaseModel):
    brand_id: str = Field(default_factory=lambda: _short_id("brand"))
    workspace_id: str
    name: str
    category: str = "generic"
    positioning: str = ""
    tone_of_voice: list[str] = Field(default_factory=list)
    product_lines: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    competitor_refs: list[str] = Field(default_factory=list)
    content_goals: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Campaign(BaseModel):
    campaign_id: str = Field(default_factory=lambda: _short_id("camp"))
    workspace_id: str
    brand_id: str
    name: str
    objective: str = "content_growth"
    status: Literal["draft", "active", "paused", "completed"] = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceMembership(BaseModel):
    membership_id: str = Field(default_factory=lambda: _short_id("m"))
    workspace_id: str
    user_id: str
    display_name: str
    role: Literal["admin", "strategist", "editor", "designer", "reviewer", "viewer"] = "viewer"
    api_token: str = Field(default_factory=_api_token)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Connector(BaseModel):
    connector_id: str = Field(default_factory=lambda: _short_id("conn"))
    workspace_id: str
    platform: str
    connector_type: str
    status: Literal["active", "paused", "error"] = "active"
    config: dict[str, Any] = Field(default_factory=dict)
    last_synced_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OpportunityQueueEntry(BaseModel):
    queue_entry_id: str = Field(default_factory=lambda: _short_id("queue"))
    workspace_id: str
    brand_id: str
    campaign_id: str
    opportunity_id: str
    queue_status: Literal["new", "reviewed", "promoted", "archived"] = "new"
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalRecord(BaseModel):
    approval_id: str = Field(default_factory=lambda: _short_id("apr"))
    workspace_id: str
    object_type: Literal["brief", "strategy", "plan", "asset_bundle"]
    object_id: str
    object_version: int = 1
    decision: Literal["pending_review", "approved", "changes_requested", "rejected"]
    reviewer_id: str
    reviewer_role: Literal["admin", "strategist", "editor", "designer", "reviewer", "viewer"]
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UsageEvent(BaseModel):
    usage_event_id: str = Field(default_factory=lambda: _short_id("usage"))
    workspace_id: str
    brand_id: str = ""
    campaign_id: str = ""
    event_type: str
    units: int = 1
    object_type: str = ""
    object_id: str = ""
    actor_user_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PublishResult(BaseModel):
    publish_result_id: str = Field(default_factory=lambda: _short_id("pub"))
    workspace_id: str
    brand_id: str = ""
    campaign_id: str = ""
    asset_bundle_id: str
    opportunity_id: str = ""
    brief_version: int = 0
    strategy_version: int = 0
    plan_version: int = 0
    asset_bundle_version: int = 0
    platform: str
    external_ref: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrandGuardrail(BaseModel):
    guardrail_id: str = Field(default_factory=lambda: _short_id("guard"))
    brand_id: str
    workspace_id: str = ""
    forbidden_expressions: list[str] = Field(default_factory=list)
    must_mention_points: list[str] = Field(default_factory=list)
    style_boundaries: list[str] = Field(default_factory=list)
    risk_words: list[str] = Field(default_factory=list)
    platform_guidelines: dict[str, str] = Field(default_factory=dict)
    campaign_objectives: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrandVoice(BaseModel):
    voice_id: str = Field(default_factory=lambda: _short_id("voice"))
    brand_id: str
    workspace_id: str = ""
    tone_spectrum: list[str] = Field(default_factory=list)
    vocabulary_whitelist: list[str] = Field(default_factory=list)
    vocabulary_blacklist: list[str] = Field(default_factory=list)
    example_sentences: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrandProductLine(BaseModel):
    product_line_id: str = Field(default_factory=lambda: _short_id("pl"))
    brand_id: str
    workspace_id: str = ""
    name: str
    category: str = ""
    key_features: list[str] = Field(default_factory=list)
    target_price_range: str = ""
    positioning: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AudienceProfile(BaseModel):
    audience_id: str = Field(default_factory=lambda: _short_id("aud"))
    brand_id: str
    workspace_id: str = ""
    personas: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    decision_factors: list[str] = Field(default_factory=list)
    taboo_topics: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrandObjective(BaseModel):
    objective_id: str = Field(default_factory=lambda: _short_id("obj"))
    brand_id: str
    workspace_id: str = ""
    campaign_id: str = ""
    objective_type: Literal["awareness", "engagement", "conversion", "retention", "other"] = "awareness"
    target_metrics: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObjectAssignment(BaseModel):
    assignment_id: str = Field(default_factory=lambda: _short_id("asgn"))
    workspace_id: str
    object_type: Literal["brief", "strategy", "plan", "asset_bundle"]
    object_id: str
    assignee_user_id: str
    assigned_by: str = ""
    role_hint: str = ""
    status: Literal["active", "completed", "cancelled"] = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObjectComment(BaseModel):
    comment_id: str = Field(default_factory=lambda: _short_id("cmt"))
    workspace_id: str
    object_type: Literal["brief", "strategy", "plan", "asset_bundle"]
    object_id: str
    author_user_id: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceTimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: _short_id("evt"))
    workspace_id: str
    event_type: str
    object_type: str = ""
    object_id: str = ""
    actor_user_id: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: _short_id("areq"))
    workspace_id: str
    object_type: Literal["brief", "strategy", "plan", "asset_bundle"]
    object_id: str
    object_version: int = 1
    requested_by: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["pending", "approved", "rejected", "withdrawn"] = "pending"
    reviewer_id: str = ""
    decision_at: datetime | None = None
    notes: str = ""


class ReadinessChecklist(BaseModel):
    checklist_id: str = Field(default_factory=lambda: _short_id("rdy"))
    workspace_id: str = ""
    object_type: str = "asset_bundle"
    object_id: str = ""
    export_readiness: bool = False
    publish_readiness: bool = False
    approval_gate: bool = False
    brand_fit_passed: bool = False
    guardrail_passed: bool = False
    scorecard_passed: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class B2BBootstrapResult(BaseModel):
    organization: Organization
    workspace: Workspace
    brand: BrandProfile
    campaign: Campaign
    admin_membership: WorkspaceMembership
