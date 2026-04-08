from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from apps.b2b_platform.storage import B2BPlatformStore
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow
from apps.content_planning.storage.plan_store import ContentPlanStore
from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard


def _make_card() -> XHSOpportunityCard:
    return XHSOpportunityCard(
        opportunity_id="opp_b2b_001",
        title="法式奶油风桌布·居家早餐氛围感拉满",
        summary="多篇笔记围绕法式奶油风桌布在早餐场景的搭配，视觉一致性高。",
        opportunity_type="visual",
        scene_refs=["早餐", "下午茶", "居家"],
        style_refs=["法式", "奶油风"],
        need_refs=["提升餐桌颜值"],
        visual_pattern_refs=["暖调"],
        audience_refs=["精致宝妈"],
        value_proposition_refs=["氛围感强"],
        evidence_refs=[XHSEvidenceRef(snippet="这块桌布太出片了")],
        source_note_ids=["note_001"],
        confidence=0.85,
        opportunity_status="promoted",
    )


def test_flow_persists_workspace_context_approval_and_usage(tmp_path: Path) -> None:
    adapter = MagicMock()
    adapter.get_card.return_value = _make_card()
    adapter.get_source_notes.return_value = []
    adapter.get_review_summary.return_value = {"review_count": 2, "avg_quality_score": 8.2}

    platform_store = B2BPlatformStore(tmp_path / "b2b.sqlite")
    bootstrap = platform_store.bootstrap_workspace(
        organization_name="Acme Group",
        workspace_name="Acme Beauty",
        brand_name="Acme Table",
        campaign_name="Spring Launch",
        admin_user_id="u_admin",
        admin_display_name="Admin",
    )
    platform_store.queue_opportunity(
        workspace_id=bootstrap.workspace.workspace_id,
        brand_id=bootstrap.brand.brand_id,
        campaign_id=bootstrap.campaign.campaign_id,
        opportunity_id="opp_b2b_001",
        actor_user_id="u_admin",
        queue_status="promoted",
    )

    flow = OpportunityToPlanFlow(
        adapter=adapter,
        plan_store=ContentPlanStore(tmp_path / "plan.sqlite"),
        platform_store=platform_store,
    )

    flow.bind_workspace_context(
        opportunity_id="opp_b2b_001",
        workspace_id=bootstrap.workspace.workspace_id,
        user_id="u_admin",
        api_token=bootstrap.admin_membership.api_token,
    )

    result = flow.compile_note_plan("opp_b2b_001", with_generation=True)
    bundle = flow.assemble_asset_bundle("opp_b2b_001")

    assert result["brief"]["workspace_id"] == bootstrap.workspace.workspace_id
    assert result["brief"]["brand_id"] == bootstrap.brand.brand_id
    assert result["brief"]["campaign_id"] == bootstrap.campaign.campaign_id
    assert result["strategy"]["workspace_id"] == bootstrap.workspace.workspace_id
    assert result["note_plan"]["workspace_id"] == bootstrap.workspace.workspace_id
    assert bundle.workspace_id == bootstrap.workspace.workspace_id
    assert bundle.brand_id == bootstrap.brand.brand_id
    assert bundle.lineage is not None
    assert bundle.lineage.workspace_id == bootstrap.workspace.workspace_id

    approval = flow.approve_object(
        opportunity_id="opp_b2b_001",
        object_type="brief",
        decision="approved",
        notes="Brand approved",
        workspace_id=bootstrap.workspace.workspace_id,
        user_id="u_admin",
        api_token=bootstrap.admin_membership.api_token,
    )
    assert approval.decision == "approved"

    usage_summary = platform_store.usage_summary(bootstrap.workspace.workspace_id)
    assert usage_summary["by_event_type"]["note_plan_compiled"] == 1
    assert usage_summary["by_event_type"]["asset_bundle_assembled"] == 1

    session = flow.get_session_data("opp_b2b_001")
    assert session["workspace_id"] == bootstrap.workspace.workspace_id
    assert session["brand_id"] == bootstrap.brand.brand_id
    assert session["approval_summary"]["brief"]["latest_decision"] == "approved"
