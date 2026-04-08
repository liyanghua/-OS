import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_output" / "output"
TABLECLOTH_FIXTURE_OUTPUT = ROOT / "data" / "fixtures" / "trendradar_tablecloth" / "output"


class ApiSurfaceTests(unittest.TestCase):
    def test_b2b_platform_bootstrap_queue_and_content_planning_review(self) -> None:
        from fastapi.testclient import TestClient

        from apps.b2b_platform.storage import B2BPlatformStore
        from apps.content_planning.storage.plan_store import ContentPlanStore
        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.schemas.evidence import XHSEvidenceRef
        from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
        from apps.intel_hub.storage.xhs_review_store import XHSReviewStore

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        f"b2b_platform_db_path: {(tmp / 'b2b.sqlite').as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            review_store = XHSReviewStore(tmp / "xhs_review.sqlite")
            card = XHSOpportunityCard(
                opportunity_id="opp_api_b2b_001",
                title="桌布场景机会卡",
                summary="promoted 机会卡",
                opportunity_type="visual",
                scene_refs=["早餐"],
                style_refs=["奶油风"],
                need_refs=["提升颜值"],
                visual_pattern_refs=["暖调"],
                audience_refs=["精致宝妈"],
                value_proposition_refs=["氛围感强"],
                evidence_refs=[XHSEvidenceRef(snippet="桌布很出片")],
                source_note_ids=["note_001"],
                confidence=0.92,
                opportunity_status="promoted",
            )
            cards_json = tmp / "cards.json"
            cards_json.write_text(f"[{card.model_dump_json()}]", encoding="utf-8")
            review_store.sync_cards_from_json(cards_json)

            client = TestClient(
                create_app(
                    runtime_path,
                    review_store=review_store,
                    content_plan_store=ContentPlanStore(tmp / "plan.sqlite"),
                    platform_store=B2BPlatformStore(tmp / "b2b.sqlite"),
                )
            )

            bootstrap = client.post(
                "/b2b/bootstrap",
                json={
                    "organization_name": "Acme Group",
                    "workspace_name": "Acme Beauty",
                    "brand_name": "Acme Table",
                    "campaign_name": "Spring Launch",
                    "admin_user_id": "u_admin",
                    "admin_display_name": "Admin",
                },
            )
            self.assertEqual(bootstrap.status_code, 200)
            payload = bootstrap.json()
            workspace_id = payload["workspace"]["workspace_id"]
            brand_id = payload["brand"]["brand_id"]
            campaign_id = payload["campaign"]["campaign_id"]
            token = payload["admin_membership"]["api_token"]
            headers = {
                "X-Workspace-Id": workspace_id,
                "X-User-Id": "u_admin",
                "X-Api-Token": token,
            }

            queued = client.post(
                f"/b2b/workspaces/{workspace_id}/opportunities/{card.opportunity_id}/queue",
                headers=headers,
                json={"brand_id": brand_id, "campaign_id": campaign_id, "queue_status": "promoted"},
            )
            self.assertEqual(queued.status_code, 200)

            brief = client.post(
                f"/content-planning/xhs-opportunities/{card.opportunity_id}/generate-brief",
                headers=headers,
            )
            self.assertEqual(brief.status_code, 200)
            self.assertEqual(brief.json()["workspace_id"], workspace_id)

            approved = client.post(
                f"/content-planning/xhs-opportunities/{card.opportunity_id}/approve",
                headers=headers,
                json={"object_type": "brief", "decision": "approved", "notes": "Ready"},
            )
            self.assertEqual(approved.status_code, 200)
            self.assertEqual(approved.json()["decision"], "approved")

            usage = client.get(f"/b2b/workspaces/{workspace_id}/usage", headers=headers)
            self.assertEqual(usage.status_code, 200)
            self.assertEqual(usage.json()["by_event_type"]["brief_generated"], 1)

    def test_api_serves_paginated_lists_and_html_dashboard(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            run_pipeline(runtime_path)
            client = TestClient(create_app(runtime_path))

            signals_response = client.get("/signals?page=1&page_size=10")
            self.assertEqual(signals_response.status_code, 200)
            self.assertEqual(signals_response.json()["total"], 3)

            opportunities_response = client.get("/opportunities?page=1&page_size=10")
            self.assertEqual(opportunities_response.status_code, 200)
            self.assertGreaterEqual(opportunities_response.json()["total"], 1)

            risks_response = client.get("/risks?page=1&page_size=10")
            self.assertEqual(risks_response.status_code, 200)
            self.assertGreaterEqual(risks_response.json()["total"], 1)

            watchlists_response = client.get("/watchlists?page=1&page_size=10")
            self.assertEqual(watchlists_response.status_code, 200)
            self.assertGreaterEqual(watchlists_response.json()["total"], 3)

            dashboard_response = client.get("/")
            self.assertEqual(dashboard_response.status_code, 200)
            self.assertIn("Opportunity", dashboard_response.text)
            self.assertIn("evidence", dashboard_response.text.lower())

    def test_api_filters_tablecloth_entity_and_platform(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {TABLECLOTH_FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            run_pipeline(runtime_path)
            client = TestClient(create_app(runtime_path))

            signals_response = client.get("/signals?entity=category_tablecloth&platform=weibo")
            self.assertEqual(signals_response.status_code, 200)
            self.assertGreaterEqual(signals_response.json()["total"], 1)

            opportunities_response = client.get("/opportunities?entity=category_tablecloth&platform=weibo")
            self.assertEqual(opportunities_response.status_code, 200)
            self.assertGreaterEqual(opportunities_response.json()["total"], 1)

    def test_api_supports_review_writeback_and_filtering(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            run_pipeline(runtime_path)
            client = TestClient(create_app(runtime_path))

            opportunity = client.get("/opportunities").json()["items"][0]
            review_response = client.post(
                f"/opportunities/{opportunity['id']}/review",
                json={
                    "review_status": "accepted",
                    "review_notes": "Reviewed by API test",
                    "reviewer": "api_reviewer",
                    "feedback_tags": ["confirmed"],
                },
            )
            self.assertEqual(review_response.status_code, 200)
            self.assertEqual(review_response.json()["review_status"], "accepted")
            self.assertEqual(review_response.json()["reviewer"], "api_reviewer")
            self.assertIsNotNone(review_response.json()["reviewed_at"])

            filtered = client.get("/opportunities?review_status=accepted&reviewer=api_reviewer")
            self.assertEqual(filtered.status_code, 200)
            self.assertEqual(filtered.json()["total"], 1)

            risk = client.get("/risks").json()["items"][0]
            risk_review_response = client.post(
                f"/risks/{risk['id']}/review",
                json={
                    "review_status": "needs_followup",
                    "review_notes": "Need more evidence",
                    "reviewer": "risk_reviewer",
                },
            )
            self.assertEqual(risk_review_response.status_code, 200)
            self.assertEqual(risk_review_response.json()["review_status"], "needs_followup")

    def test_api_rejects_invalid_review_status(self) -> None:
        from fastapi.testclient import TestClient

        from apps.intel_hub.api.app import create_app
        from apps.intel_hub.workflow.refresh_pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            storage_path = tmp / "intel_hub.sqlite"
            runtime_path = tmp / "runtime.yaml"
            runtime_path.write_text(
                "\n".join(
                    [
                        f"trendradar_output_dir: {FIXTURE_OUTPUT.as_posix()}",
                        f"storage_path: {storage_path.as_posix()}",
                        "default_page_size: 20",
                        "fixture_fallback_dir: ''",
                    ]
                ),
                encoding="utf-8",
            )

            run_pipeline(runtime_path)
            client = TestClient(create_app(runtime_path))
            opportunity = client.get("/opportunities").json()["items"][0]

            response = client.post(
                f"/opportunities/{opportunity['id']}/review",
                json={
                    "review_status": "not_valid",
                    "review_notes": "bad",
                    "reviewer": "api_reviewer",
                },
            )

            self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
