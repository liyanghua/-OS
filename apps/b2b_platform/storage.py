from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from apps.b2b_platform.schemas import (
    ApprovalRecord,
    B2BBootstrapResult,
    BrandProfile,
    Campaign,
    Connector,
    OpportunityQueueEntry,
    Organization,
    PublishResult,
    UsageEvent,
    Workspace,
    WorkspaceMembership,
)

ROLE_RANK: dict[str, int] = {
    "viewer": 0,
    "designer": 1,
    "editor": 2,
    "reviewer": 3,
    "strategist": 4,
    "admin": 5,
}


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "workspace"


def _serialize(model: Any) -> str:
    dump_json = getattr(model, "model_dump_json", None)
    if callable(dump_json):
        return dump_json()
    return json.dumps(model, ensure_ascii=False)


class B2BPlatformStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    organization_id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brands (
                    brand_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    brand_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memberships (
                    membership_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    api_token TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memberships_workspace_user
                ON memberships(workspace_id, user_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connectors (
                    connector_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    connector_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunity_queue (
                    queue_entry_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    brand_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    opportunity_id TEXT NOT NULL,
                    queue_status TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_opportunity_queue_workspace_opp
                ON opportunity_queue(workspace_id, opportunity_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_records (
                    approval_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    usage_event_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    units INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS publish_results (
                    publish_result_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    asset_bundle_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def bootstrap_workspace(
        self,
        *,
        organization_name: str,
        workspace_name: str,
        brand_name: str,
        campaign_name: str,
        admin_user_id: str,
        admin_display_name: str,
    ) -> B2BBootstrapResult:
        organization = Organization(name=organization_name, slug=_slugify(organization_name))
        workspace = Workspace(
            organization_id=organization.organization_id,
            name=workspace_name,
            slug=_slugify(workspace_name),
        )
        brand = BrandProfile(workspace_id=workspace.workspace_id, name=brand_name)
        campaign = Campaign(workspace_id=workspace.workspace_id, brand_id=brand.brand_id, name=campaign_name)
        membership = WorkspaceMembership(
            workspace_id=workspace.workspace_id,
            user_id=admin_user_id,
            display_name=admin_display_name,
            role="admin",
        )
        with self._connect() as conn:
            self._upsert(conn, "organizations", "organization_id", organization.organization_id, organization, extra={
                "slug": organization.slug,
            })
            self._upsert(conn, "workspaces", "workspace_id", workspace.workspace_id, workspace, extra={
                "organization_id": workspace.organization_id,
                "slug": workspace.slug,
                "status": workspace.status,
            })
            self._upsert(conn, "brands", "brand_id", brand.brand_id, brand, extra={
                "workspace_id": brand.workspace_id,
                "name": brand.name,
            })
            self._upsert(conn, "campaigns", "campaign_id", campaign.campaign_id, campaign, extra={
                "workspace_id": campaign.workspace_id,
                "brand_id": campaign.brand_id,
                "status": campaign.status,
            })
            self._upsert(conn, "memberships", "membership_id", membership.membership_id, membership, extra={
                "workspace_id": membership.workspace_id,
                "user_id": membership.user_id,
                "role": membership.role,
                "api_token": membership.api_token,
            })
        return B2BBootstrapResult(
            organization=organization,
            workspace=workspace,
            brand=brand,
            campaign=campaign,
            admin_membership=membership,
        )

    def create_brand(
        self,
        *,
        workspace_id: str,
        name: str,
        category: str = "generic",
        positioning: str = "",
        tone_of_voice: list[str] | None = None,
        product_lines: list[str] | None = None,
        forbidden_terms: list[str] | None = None,
        competitor_refs: list[str] | None = None,
        content_goals: list[str] | None = None,
    ) -> BrandProfile:
        brand = BrandProfile(
            workspace_id=workspace_id,
            name=name,
            category=category,
            positioning=positioning,
            tone_of_voice=tone_of_voice or [],
            product_lines=product_lines or [],
            forbidden_terms=forbidden_terms or [],
            competitor_refs=competitor_refs or [],
            content_goals=content_goals or [],
        )
        with self._connect() as conn:
            self._upsert(conn, "brands", "brand_id", brand.brand_id, brand, extra={
                "workspace_id": brand.workspace_id,
                "name": brand.name,
            })
        return brand

    def create_campaign(
        self,
        *,
        workspace_id: str,
        brand_id: str,
        name: str,
        objective: str = "content_growth",
    ) -> Campaign:
        campaign = Campaign(
            workspace_id=workspace_id,
            brand_id=brand_id,
            name=name,
            objective=objective,
        )
        with self._connect() as conn:
            self._upsert(conn, "campaigns", "campaign_id", campaign.campaign_id, campaign, extra={
                "workspace_id": campaign.workspace_id,
                "brand_id": campaign.brand_id,
                "status": campaign.status,
            })
        return campaign

    def create_membership(
        self,
        *,
        workspace_id: str,
        user_id: str,
        display_name: str,
        role: str,
    ) -> WorkspaceMembership:
        membership = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            display_name=display_name,
            role=role,
        )
        with self._connect() as conn:
            self._upsert(conn, "memberships", "membership_id", membership.membership_id, membership, extra={
                "workspace_id": membership.workspace_id,
                "user_id": membership.user_id,
                "role": membership.role,
                "api_token": membership.api_token,
            })
        return membership

    def create_connector(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        platform: str,
        connector_type: str,
        config: dict[str, Any] | None = None,
        status: str = "active",
    ) -> Connector:
        connector = Connector(
            workspace_id=workspace_id,
            platform=platform,
            connector_type=connector_type,
            config=config or {},
            status=status,
        )
        with self._connect() as conn:
            self._upsert(conn, "connectors", "connector_id", connector.connector_id, connector, extra={
                "workspace_id": connector.workspace_id,
                "platform": connector.platform,
                "connector_type": connector.connector_type,
                "status": connector.status,
            })
        return connector

    def queue_opportunity(
        self,
        *,
        workspace_id: str,
        brand_id: str,
        campaign_id: str,
        opportunity_id: str,
        actor_user_id: str,
        queue_status: str = "new",
    ) -> OpportunityQueueEntry:
        entry = OpportunityQueueEntry(
            workspace_id=workspace_id,
            brand_id=brand_id,
            campaign_id=campaign_id,
            opportunity_id=opportunity_id,
            queue_status=queue_status,
            created_by=actor_user_id,
        )
        with self._connect() as conn:
            self._upsert(conn, "opportunity_queue", "queue_entry_id", entry.queue_entry_id, entry, extra={
                "workspace_id": entry.workspace_id,
                "brand_id": entry.brand_id,
                "campaign_id": entry.campaign_id,
                "opportunity_id": entry.opportunity_id,
                "queue_status": entry.queue_status,
                "created_by": entry.created_by,
            }, unique_fields=("workspace_id", "opportunity_id"))
        return self.get_queue_entry(workspace_id, opportunity_id) or entry

    def get_queue_entry(self, workspace_id: str, opportunity_id: str) -> OpportunityQueueEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json FROM opportunity_queue
                WHERE workspace_id = ? AND opportunity_id = ?
                """,
                (workspace_id, opportunity_id),
            ).fetchone()
        if row is None:
            return None
        return OpportunityQueueEntry.model_validate_json(row["payload_json"])

    def authenticate(self, *, workspace_id: str, user_id: str, api_token: str) -> WorkspaceMembership:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json FROM memberships
                WHERE workspace_id = ? AND user_id = ? AND api_token = ?
                """,
                (workspace_id, user_id, api_token),
            ).fetchone()
        if row is None:
            raise PermissionError("invalid workspace credentials")
        return WorkspaceMembership.model_validate_json(row["payload_json"])

    def authorize(
        self,
        *,
        workspace_id: str,
        user_id: str,
        api_token: str,
        allowed_roles: Iterable[str],
    ) -> WorkspaceMembership:
        membership = self.authenticate(workspace_id=workspace_id, user_id=user_id, api_token=api_token)
        if membership.role not in set(allowed_roles):
            raise PermissionError("role not permitted for this action")
        return membership

    def record_approval(
        self,
        *,
        workspace_id: str,
        object_type: str,
        object_id: str,
        object_version: int,
        decision: str,
        reviewer_id: str,
        reviewer_role: str,
        notes: str = "",
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            workspace_id=workspace_id,
            object_type=object_type,
            object_id=object_id,
            object_version=object_version,
            decision=decision,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            notes=notes,
        )
        with self._connect() as conn:
            self._upsert(conn, "approval_records", "approval_id", record.approval_id, record, extra={
                "workspace_id": record.workspace_id,
                "object_type": record.object_type,
                "object_id": record.object_id,
                "decision": record.decision,
                "reviewer_id": record.reviewer_id,
                "created_at": record.created_at.isoformat(),
            })
        return record

    def list_approvals(
        self,
        workspace_id: str,
        *,
        object_type: str | None = None,
        object_id: str | None = None,
    ) -> list[ApprovalRecord]:
        filters = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]
        if object_type:
            filters.append("object_type = ?")
            params.append(object_type)
        if object_id:
            filters.append("object_id = ?")
            params.append(object_id)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json FROM approval_records
                WHERE {' AND '.join(filters)}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [ApprovalRecord.model_validate_json(row["payload_json"]) for row in rows]

    def record_usage(
        self,
        *,
        workspace_id: str,
        brand_id: str = "",
        campaign_id: str = "",
        event_type: str,
        units: int = 1,
        object_type: str = "",
        object_id: str = "",
        actor_user_id: str = "",
    ) -> UsageEvent:
        event = UsageEvent(
            workspace_id=workspace_id,
            brand_id=brand_id,
            campaign_id=campaign_id,
            event_type=event_type,
            units=units,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=actor_user_id,
        )
        with self._connect() as conn:
            self._upsert(conn, "usage_events", "usage_event_id", event.usage_event_id, event, extra={
                "workspace_id": event.workspace_id,
                "event_type": event.event_type,
                "units": event.units,
                "created_at": event.created_at.isoformat(),
            })
        return event

    def usage_summary(self, workspace_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM usage_events WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        events = [UsageEvent.model_validate_json(row["payload_json"]) for row in rows]
        by_event: dict[str, int] = defaultdict(int)
        total_units = 0
        for event in events:
            by_event[event.event_type] += event.units
            total_units += event.units
        return {
            "workspace_id": workspace_id,
            "total_events": len(events),
            "total_units": total_units,
            "by_event_type": dict(by_event),
        }

    def record_publish_result(
        self,
        *,
        workspace_id: str,
        brand_id: str,
        campaign_id: str,
        asset_bundle_id: str,
        platform: str,
        external_ref: str = "",
        metrics: dict[str, Any] | None = None,
    ) -> PublishResult:
        result = PublishResult(
            workspace_id=workspace_id,
            brand_id=brand_id,
            campaign_id=campaign_id,
            asset_bundle_id=asset_bundle_id,
            platform=platform,
            external_ref=external_ref,
            metrics=metrics or {},
        )
        with self._connect() as conn:
            self._upsert(conn, "publish_results", "publish_result_id", result.publish_result_id, result, extra={
                "workspace_id": result.workspace_id,
                "asset_bundle_id": result.asset_bundle_id,
                "platform": result.platform,
                "created_at": result.created_at.isoformat(),
            })
        return result

    def workspace_snapshot(self, workspace_id: str) -> dict[str, Any]:
        workspace = self._get_one("workspaces", "workspace_id", workspace_id, Workspace)
        if workspace is None:
            raise ValueError(f"workspace {workspace_id} not found")
        organization = self._get_one("organizations", "organization_id", workspace.organization_id, Organization)
        brands = self._list_models("brands", "workspace_id", workspace_id, BrandProfile)
        campaigns = self._list_models("campaigns", "workspace_id", workspace_id, Campaign)
        memberships = self._list_models("memberships", "workspace_id", workspace_id, WorkspaceMembership)
        connectors = self._list_models("connectors", "workspace_id", workspace_id, Connector)
        queue = self._list_models("opportunity_queue", "workspace_id", workspace_id, OpportunityQueueEntry)
        approvals = self.list_approvals(workspace_id)
        return {
            "organization": organization.model_dump(mode="json") if organization else {},
            "workspace": workspace.model_dump(mode="json"),
            "brands": [item.model_dump(mode="json") for item in brands],
            "campaigns": [item.model_dump(mode="json") for item in campaigns],
            "memberships": [
                {**item.model_dump(mode="json"), "api_token": item.api_token[:6] + "..."}
                for item in memberships
            ],
            "connectors": [item.model_dump(mode="json") for item in connectors],
            "opportunity_queue": [item.model_dump(mode="json") for item in queue],
            "approvals": [item.model_dump(mode="json") for item in approvals],
            "usage_summary": self.usage_summary(workspace_id),
        }

    def _get_one(self, table: str, key_name: str, key_value: str, model_cls: Any) -> Any | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT payload_json FROM {table} WHERE {key_name} = ?",
                (key_value,),
            ).fetchone()
        if row is None:
            return None
        return model_cls.model_validate_json(row["payload_json"])

    def _list_models(self, table: str, key_name: str, key_value: str, model_cls: Any) -> list[Any]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT payload_json FROM {table} WHERE {key_name} = ?",
                (key_value,),
            ).fetchall()
        return [model_cls.model_validate_json(row["payload_json"]) for row in rows]

    def _upsert(
        self,
        conn: sqlite3.Connection,
        table: str,
        primary_key: str,
        primary_value: str,
        payload: Any,
        *,
        extra: dict[str, Any] | None = None,
        unique_fields: tuple[str, ...] | None = None,
    ) -> None:
        extra = extra or {}
        if unique_fields:
            where = " AND ".join(f"{field} = ?" for field in unique_fields)
            values = [extra[field] for field in unique_fields]
            existing = conn.execute(
                f"SELECT {primary_key} FROM {table} WHERE {where}",
                values,
            ).fetchone()
            if existing is not None:
                primary_value = existing[primary_key]
        columns = [primary_key, *extra.keys(), "payload_json"]
        values = [primary_value, *extra.values(), _serialize(payload)]
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns[1:])
        conn.execute(
            f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT({primary_key}) DO UPDATE SET {updates}
            """,
            values,
        )
