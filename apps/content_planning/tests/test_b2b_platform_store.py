from __future__ import annotations

from pathlib import Path

import pytest

from apps.b2b_platform.storage import B2BPlatformStore


def test_platform_store_bootstrap_and_workspace_snapshot(tmp_path: Path) -> None:
    store = B2BPlatformStore(tmp_path / "b2b.sqlite")

    bootstrap = store.bootstrap_workspace(
        organization_name="Acme Group",
        workspace_name="Acme Beauty",
        brand_name="Acme Table",
        campaign_name="Spring Launch",
        admin_user_id="u_admin",
        admin_display_name="Admin",
    )

    auth = store.authenticate(
        workspace_id=bootstrap.workspace.workspace_id,
        user_id="u_admin",
        api_token=bootstrap.admin_membership.api_token,
    )
    assert auth.role == "admin"

    connector = store.create_connector(
        workspace_id=bootstrap.workspace.workspace_id,
        actor_user_id="u_admin",
        platform="xiaohongshu",
        connector_type="mediacrawler_xhs",
        config={"source": "cookie-session"},
    )
    assert connector.platform == "xiaohongshu"

    queued = store.queue_opportunity(
        workspace_id=bootstrap.workspace.workspace_id,
        brand_id=bootstrap.brand.brand_id,
        campaign_id=bootstrap.campaign.campaign_id,
        opportunity_id="opp_001",
        actor_user_id="u_admin",
        queue_status="promoted",
    )
    assert queued.opportunity_id == "opp_001"

    approval = store.record_approval(
        workspace_id=bootstrap.workspace.workspace_id,
        object_type="brief",
        object_id="brief_001",
        object_version=1,
        decision="approved",
        reviewer_id="u_admin",
        reviewer_role="admin",
        notes="Ready for brand review",
    )
    assert approval.decision == "approved"

    store.record_usage(
        workspace_id=bootstrap.workspace.workspace_id,
        brand_id=bootstrap.brand.brand_id,
        campaign_id=bootstrap.campaign.campaign_id,
        event_type="brief_generated",
        units=1,
        object_type="brief",
        object_id="brief_001",
        actor_user_id="u_admin",
    )
    store.record_usage(
        workspace_id=bootstrap.workspace.workspace_id,
        brand_id=bootstrap.brand.brand_id,
        campaign_id=bootstrap.campaign.campaign_id,
        event_type="asset_bundle_exported",
        units=2,
        object_type="asset_bundle",
        object_id="bundle_001",
        actor_user_id="u_admin",
    )

    snapshot = store.workspace_snapshot(bootstrap.workspace.workspace_id)
    assert snapshot["organization"]["organization_id"] == bootstrap.organization.organization_id
    assert len(snapshot["brands"]) == 1
    assert len(snapshot["campaigns"]) == 1
    assert len(snapshot["connectors"]) == 1
    assert len(snapshot["opportunity_queue"]) == 1
    assert snapshot["usage_summary"]["total_units"] == 3
    assert snapshot["usage_summary"]["by_event_type"]["asset_bundle_exported"] == 2


def test_platform_store_enforces_api_token(tmp_path: Path) -> None:
    store = B2BPlatformStore(tmp_path / "b2b.sqlite")
    bootstrap = store.bootstrap_workspace(
        organization_name="Acme Group",
        workspace_name="Acme Beauty",
        brand_name="Acme Table",
        campaign_name="Spring Launch",
        admin_user_id="u_admin",
        admin_display_name="Admin",
    )

    with pytest.raises(PermissionError):
        store.authenticate(
            workspace_id=bootstrap.workspace.workspace_id,
            user_id="u_admin",
            api_token="bad-token",
        )
