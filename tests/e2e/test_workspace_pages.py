"""四工作台路由 E2E 验收测试。

使用 httpx 验证新增的四个工作台页面路由可访问且返回正确结构，
同时确认旧路由不受影响。
"""
from __future__ import annotations

import multiprocessing
import os
import time
from pathlib import Path
from typing import Generator

import pytest
import httpx

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:18766"


def _run_server():
    os.chdir(str(WORKSPACE_ROOT))
    import sys
    sys.path.insert(0, str(WORKSPACE_ROOT))
    import uvicorn
    from apps.intel_hub.api.app import create_app
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=18766, log_level="warning")


@pytest.fixture(scope="module")
def live_server() -> Generator[str, None, None]:
    proc = multiprocessing.Process(target=_run_server, daemon=True)
    proc.start()
    for _ in range(30):
        try:
            r = httpx.get(f"{BASE}/", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        proc.kill()
        pytest.fail("Server did not start within 30s")
    yield BASE
    proc.kill()


class TestNewWorkspaceRoutes:
    """验证四工作台新路由可访问且返回正确结构。"""

    def test_opportunity_workspace_returns_200(self, live_server: str):
        """机会台 HTML 页面返回 200 且包含中文关键词。"""
        r = httpx.get(f"{live_server}/opportunity-workspace", headers={"Accept": "text/html"})
        assert r.status_code == 200
        assert "机会" in r.text

    def test_opportunity_workspace_json(self, live_server: str):
        """机会台 JSON 返回包含 items 字段。"""
        r = httpx.get(f"{live_server}/opportunity-workspace", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_planning_workspace_404_without_card(self, live_server: str):
        """策划台访问不存在的 opportunity_id 返回 404。"""
        r = httpx.get(f"{live_server}/planning/nonexistent_id", headers={"Accept": "text/html"})
        assert r.status_code == 404

    def test_result_workspace_returns_200(self, live_server: str):
        """结果台（反馈页）返回 200。"""
        r = httpx.get(f"{live_server}/feedback", headers={"Accept": "text/html"})
        assert r.status_code == 200

    def test_old_routes_still_work(self, live_server: str):
        """旧路由 /xhs-opportunities 仍然可访问。"""
        r = httpx.get(f"{live_server}/xhs-opportunities", headers={"Accept": "text/html"})
        assert r.status_code == 200
        assert "机会" in r.text
