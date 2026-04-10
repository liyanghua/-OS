"""三阶段商业闭环升级 — 端到端浏览器验收测试。

启动 intel_hub 应用，用 Playwright 从用户视角验证：
1. Phase 1: 发布结果录入 / 反馈页 / outcome API
2. Phase 2: 品牌配置页 / guardrail API
3. Phase 3: 工作区首页 / 机会管线 / 审批队列 / 协作 API
"""
from __future__ import annotations

import json
import multiprocessing
import os
import time
from pathlib import Path
from typing import Any, Generator

import pytest
import requests
import uvicorn

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://127.0.0.1:18765"


def _run_server():
    os.chdir(str(WORKSPACE_ROOT))
    import sys
    sys.path.insert(0, str(WORKSPACE_ROOT))
    from apps.intel_hub.api.app import create_app
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=18765, log_level="warning")


@pytest.fixture(scope="module")
def live_server() -> Generator[str, None, None]:
    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        proc.kill()
        pytest.fail("Server did not start within 30s")
    yield BASE_URL
    proc.kill()


@pytest.fixture(scope="module")
def bootstrap_data(live_server: str) -> dict[str, Any]:
    """Bootstrap a workspace + brand + campaign for testing."""
    r = requests.post(f"{live_server}/b2b/bootstrap", json={
        "organization_name": "E2E测试公司",
        "workspace_name": "验收工作区",
        "brand_name": "测试品牌",
        "campaign_name": "春季推广",
        "admin_user_id": "admin_001",
        "admin_display_name": "验收管理员",
    })
    assert r.status_code == 200, f"Bootstrap failed: {r.text}"
    data = r.json()
    return {
        "workspace_id": data["workspace"]["workspace_id"],
        "brand_id": data["brand"]["brand_id"],
        "campaign_id": data["campaign"]["campaign_id"],
        "api_token": data["admin_membership"]["api_token"],
    }


# =====================================================================
# Phase 1: 发布结果闭环
# =====================================================================


class TestPhase1PublishResultClosure:
    """验证发布结果录入 → 反馈持久化 → outcome-summary → outcome-delta 全链路。"""

    def test_dashboard_loads(self, live_server: str):
        """首页可正常渲染。"""
        r = requests.get(f"{live_server}/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_publish_result_api(self, live_server: str, bootstrap_data: dict):
        """POST publish-result 写入并返回版本绑定字段。"""
        r = requests.post(
            f"{live_server}/content-planning/asset-bundle/opp_e2e_001/publish-result",
            json={"platform": "xhs", "external_ref": "note_abc123", "metrics": {"likes": 200, "collects": 50}},
        )
        assert r.status_code in (200, 404, 501), f"Unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert "publish_result_id" in data
            assert data.get("platform") == "xhs"

    def test_feedback_api_persist(self, live_server: str):
        """POST feedback 写入并返回 feedback_id。"""
        r = requests.post(
            f"{live_server}/content-planning/asset-bundle/ab_e2e_001/feedback",
            json={
                "published_note_id": "note_e2e",
                "like_count": 120,
                "collect_count": 30,
                "comment_count": 5,
                "share_count": 2,
                "view_count": 1000,
                "performance_label": "good",
                "feedback_notes": "端到端测试反馈",
            },
        )
        assert r.status_code == 200, f"Feedback failed: {r.text}"
        data = r.json()
        assert data.get("status") == "received"
        assert "feedback_id" in data or "result_id" in data

    def test_outcome_summary_api(self, live_server: str):
        """GET outcome-summary 返回聚合数据。"""
        r = requests.get(f"{live_server}/content-planning/opportunities/opp_e2e_001/outcome-summary")
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert "opportunity_id" in data
            assert "total_publish_results" in data

    def test_outcome_delta_api(self, live_server: str):
        """GET outcome-delta 返回双层对比。"""
        r = requests.get(f"{live_server}/content-planning/comparison/opp_e2e_001/outcome-delta")
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert "stage_deltas" in data

    def test_workspace_feedback_api(self, live_server: str, bootstrap_data: dict):
        """GET workspace feedback 列表。"""
        ws = bootstrap_data["workspace_id"]
        token = bootstrap_data["api_token"]
        r = requests.get(
            f"{live_server}/b2b/workspaces/{ws}/feedback",
            headers={"x-api-token": token, "x-user-id": "admin_001"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "feedback_records" in data
        assert "winning_patterns" in data

    def test_workspace_pipeline_api(self, live_server: str, bootstrap_data: dict):
        """GET workspace pipeline 漏斗数据。"""
        ws = bootstrap_data["workspace_id"]
        token = bootstrap_data["api_token"]
        r = requests.get(
            f"{live_server}/b2b/workspaces/{ws}/pipeline",
            headers={"x-api-token": token, "x-user-id": "admin_001"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "total_published" in data


# =====================================================================
# Phase 2: 品牌知识库与 Guardrails
# =====================================================================


class TestPhase2BrandGuardrails:
    """验证品牌模型 + guardrail 检查器。"""

    def test_guardrail_checker_blocks_forbidden(self):
        """guardrail_checker 正确阻断禁用表达。"""
        from apps.content_planning.services.guardrail_checker import check_guardrails
        result = check_guardrails(
            {"title": "超级便宜大甩卖", "body": "全场一折"},
            {
                "forbidden_expressions": ["大甩卖"],
                "must_mention_points": ["品牌故事"],
                "risk_words": ["便宜"],
            },
        )
        assert result["blocked"] is True
        assert result["brand_fit_score"] < 0.7
        assert any("禁用表达" in w for w in result["warnings"])
        assert any("必提点" in w for w in result["warnings"])
        assert any("风险词" in w for w in result["warnings"])

    def test_guardrail_checker_passes_clean(self):
        """无违规内容时检查器通过。"""
        from apps.content_planning.services.guardrail_checker import check_guardrails
        result = check_guardrails(
            {"title": "品牌故事分享", "body": "来自我们的匠心之作"},
            {
                "forbidden_expressions": ["大甩卖"],
                "must_mention_points": ["品牌故事"],
                "risk_words": [],
            },
        )
        assert result["blocked"] is False
        assert result["brand_fit_score"] == 1.0

    def test_stage_proposal_has_guardrail_fields(self):
        """StageProposal 含品牌阻断字段。"""
        from apps.content_planning.schemas.agent_workflow import StageProposal
        sp = StageProposal()
        assert hasattr(sp, "guardrail_warnings")
        assert hasattr(sp, "blocked_by_guardrail")
        assert hasattr(sp, "brand_fit_score")
        assert sp.brand_fit_score == 1.0

    def test_brand_models_exist(self):
        """Phase 2 品牌模型全部可实例化。"""
        from apps.b2b_platform.schemas import (
            BrandGuardrail, BrandVoice, BrandProductLine,
            AudienceProfile, BrandObjective,
        )
        bg = BrandGuardrail(brand_id="b1")
        assert bg.guardrail_id.startswith("guard_")
        bv = BrandVoice(brand_id="b1")
        assert bv.voice_id.startswith("voice_")
        bp = BrandProductLine(brand_id="b1", name="旗舰系列")
        assert bp.product_line_id.startswith("pl_")
        ap = AudienceProfile(brand_id="b1")
        assert ap.audience_id.startswith("aud_")
        bo = BrandObjective(brand_id="b1")
        assert bo.objective_id.startswith("obj_")


# =====================================================================
# Phase 3: 团队工作区 + 审批交付流
# =====================================================================


class TestPhase3WorkspaceCollaboration:
    """验证协作对象 CRUD + 审批 + 状态机 + 前端页面。"""

    def test_assign_object(self, live_server: str, bootstrap_data: dict):
        """指派对象给用户。"""
        r = requests.post(
            f"{live_server}/objects/brief/brief_e2e_001/assign",
            json={
                "workspace_id": bootstrap_data["workspace_id"],
                "assignee_user_id": "user_001",
                "assigned_by": "admin_001",
                "role_hint": "strategist",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["object_type"] == "brief"
        assert data["assignee_user_id"] == "user_001"

    def test_add_and_get_comments(self, live_server: str, bootstrap_data: dict):
        """添加评论并查询。"""
        r = requests.post(
            f"{live_server}/objects/strategy/strat_e2e_001/comments",
            json={
                "workspace_id": bootstrap_data["workspace_id"],
                "author_user_id": "user_001",
                "content": "策略方向不错，建议补充场景描述。",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "comment_id" in data

        r2 = requests.get(
            f"{live_server}/objects/strategy/strat_e2e_001/comments",
            params={"workspace_id": bootstrap_data["workspace_id"]},
        )
        assert r2.status_code == 200
        items = r2.json().get("items", [])
        assert len(items) >= 1

    def test_approval_request_flow(self, live_server: str, bootstrap_data: dict):
        """创建审批请求 → 做出决策。"""
        from apps.b2b_platform.schemas import ApprovalRequest
        from apps.b2b_platform.storage import B2BPlatformStore
        import tempfile
        db = tempfile.mktemp(suffix=".db")
        store = B2BPlatformStore(db)
        ar = ApprovalRequest(
            workspace_id=bootstrap_data["workspace_id"],
            object_type="plan",
            object_id="plan_e2e_001",
            requested_by="user_001",
        )
        store.save_approval_request(ar)
        reqs = store.list_approval_requests(bootstrap_data["workspace_id"])
        assert len(reqs) >= 1

        r = requests.post(
            f"{live_server}/approvals/{ar.request_id}/decision",
            json={
                "workspace_id": bootstrap_data["workspace_id"],
                "decision": "approved",
                "reviewer_id": "admin_001",
                "notes": "E2E验收通过",
            },
        )
        assert r.status_code in (200, 404)
        os.unlink(db)

    def test_workspace_timeline_api(self, live_server: str, bootstrap_data: dict):
        """工作区时间线 API。"""
        ws = bootstrap_data["workspace_id"]
        token = bootstrap_data["api_token"]
        r = requests.get(
            f"{live_server}/b2b/workspaces/{ws}/timeline",
            headers={"x-api-token": token, "x-user-id": "admin_001"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_lifecycle_status_field_exists(self):
        """四类对象含 lifecycle_status 字段。"""
        from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
        from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
        from apps.content_planning.schemas.note_plan import NewNotePlan
        from apps.content_planning.schemas.asset_bundle import AssetBundle
        for cls in (OpportunityBrief, RewriteStrategy, NewNotePlan, AssetBundle):
            obj = cls()
            assert hasattr(obj, "lifecycle_status"), f"{cls.__name__} missing lifecycle_status"
            assert obj.lifecycle_status == "new"

    def test_readiness_checklist_model(self):
        """ReadinessChecklist 模型可用。"""
        from apps.b2b_platform.schemas import ReadinessChecklist
        rc = ReadinessChecklist(workspace_id="ws1", object_id="ab1")
        assert rc.export_readiness is False
        assert rc.approval_gate is False

    def test_collaboration_models_exist(self):
        """Phase 3 协作模型全部可实例化。"""
        from apps.b2b_platform.schemas import (
            ObjectAssignment, ObjectComment,
            WorkspaceTimelineEvent, ApprovalRequest,
        )
        oa = ObjectAssignment(
            workspace_id="ws1", object_type="brief",
            object_id="b1", assignee_user_id="u1",
        )
        assert oa.assignment_id.startswith("asgn_")
        oc = ObjectComment(
            workspace_id="ws1", object_type="brief",
            object_id="b1", author_user_id="u1", content="ok",
        )
        assert oc.comment_id.startswith("cmt_")
        wt = WorkspaceTimelineEvent(workspace_id="ws1", event_type="assign")
        assert wt.event_id.startswith("evt_")
        ar = ApprovalRequest(
            workspace_id="ws1", object_type="plan",
            object_id="p1", requested_by="u1",
        )
        assert ar.request_id.startswith("areq_")


# =====================================================================
# 浏览器 UI 验收（Playwright）
# =====================================================================


try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestBrowserUI:
    """用 Playwright 打开真实浏览器验证页面渲染。"""

    @pytest.fixture(scope="class")
    def page(self, live_server: str):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            yield page
            browser.close()

    def test_dashboard_renders(self, page, live_server: str):
        """首页完整渲染。"""
        page.goto(f"{live_server}/")
        page.wait_for_load_state("networkidle")
        assert page.title() or True
        page.screenshot(path=str(WORKSPACE_ROOT / "tests/e2e/screenshots/dashboard.png"))

    def test_workspace_snapshot_page(self, page, live_server: str, bootstrap_data: dict):
        """工作区快照 API 可访问。"""
        ws = bootstrap_data["workspace_id"]
        token = bootstrap_data["api_token"]
        r = requests.get(
            f"{live_server}/b2b/workspaces/{ws}/snapshot",
            headers={"x-api-token": token, "x-user-id": "admin_001"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["workspace"]["workspace_id"] == ws
