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
    platform: str
    external_ref: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class B2BBootstrapResult(BaseModel):
    organization: Organization
    workspace: Workspace
    brand: BrandProfile
    campaign: Campaign
    admin_membership: WorkspaceMembership
