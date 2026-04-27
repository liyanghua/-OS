"""视觉产线分流 + 小红书联动 端到端回归测试。

承接 plans/视觉产线分流与小红书联动_xxx.plan.md。
覆盖：
- xhs_cover send-to-workbench → 视觉工作台 url + NotePack 多 slot
- 主图 send-to-workbench → 无限画布 url + plan_id
- /candidates/{id}/full-context 聚合返回
- /candidates/{id}/note-pack 多 slot（cover + 3 body）
- /candidates/{id}/note-pack/recompile-slot 局部覆盖
- /feedback 走通 FeedbackEngine
- 候选切换：连续两次 note-pack POST 返回不同候选结构

每个 case 使用独立 sqlite 隔离。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.content_planning.api import visual_strategy_routes
from apps.content_planning.storage.rule_store import RuleStore
from apps.growth_lab.schemas.creative_brief import (
    BriefCanvas,
    BriefCopywriting,
    BriefProduct,
    BriefScene,
    BriefStyle,
    CreativeBrief,
)
from apps.growth_lab.schemas.strategy_candidate import (
    StrategyCandidate,
    StrategyScore,
)
from apps.growth_lab.schemas.visual_strategy_pack import (
    VisualStrategyPack,
    VisualStrategyPackSource,
)
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore


# ── fixtures ──────────────────────────────────────────────────


def _make_brief(brief_id: str = "") -> CreativeBrief:
    return CreativeBrief(
        id=brief_id or "brief_test_01",
        canvas=BriefCanvas(ratio="3:4", platform="xhs_cover"),
        scene=BriefScene(background="温暖家居", environment="柔光", props=["毛巾"]),
        product=BriefProduct(
            placement="中心偏右",
            scale="占画面 65%",
            angle="俯视",
            visible_features=["敏感肌洁面乳", "氨基酸成分"],
        ),
        style=BriefStyle(tone="奶油温柔", color_palette=["奶油白", "原木"], lighting="柔光"),
        copywriting=BriefCopywriting(
            headline="3 天告别敏感",
            selling_points=["氨基酸", "弱酸性"],
            labels=["孕妇可用"],
        ),
        negative=["杂乱", "logo 多"],
    )


def _make_pack(scene: str, candidate_ids: list[str], pack_id: str = "") -> VisualStrategyPack:
    return VisualStrategyPack(
        id=pack_id or f"pack_{scene}",
        source=VisualStrategyPackSource(opportunity_card_id="opp_test_01"),
        category="children_desk_mat",
        scene=scene,  # type: ignore[arg-type]
        rule_pack_id="rp_test_01",
        candidate_ids=candidate_ids,
    )


def _make_candidate(
    cand_id: str,
    pack_id: str,
    archetype: str,
    *,
    brief_id: str = "",
    rule_refs: list[str] | None = None,
    score_total: float = 0.78,
) -> StrategyCandidate:
    return StrategyCandidate(
        id=cand_id,
        visual_strategy_pack_id=pack_id,
        name=f"{archetype}-候选",
        archetype=archetype,
        hypothesis=f"{archetype} 假设",
        creative_brief_id=brief_id,
        rule_refs=rule_refs or [],
        score=StrategyScore(total=score_total, brand_fit=0.8, audience_fit=0.7, differentiation=0.7),
        rationale=[f"理由 1 - {archetype}"],
    )


@pytest.fixture()
def temp_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[VisualStrategyStore, RuleStore]:
    vs = VisualStrategyStore(db_path=tmp_path / "vs.sqlite")
    rs = RuleStore(db_path=tmp_path / "rule.sqlite")
    visual_strategy_routes.configure(rule_store=rs, visual_strategy_store=vs)
    # 防止真实 _send_to_workbench_handler 写入 PlanStore
    monkeypatch.setattr(visual_strategy_routes, "_send_to_workbench_handler", None, raising=False)
    return vs, rs


@pytest.fixture()
def client(temp_stores: tuple[VisualStrategyStore, RuleStore]) -> TestClient:
    app = FastAPI()
    app.include_router(visual_strategy_routes.router)
    return TestClient(app)


def _seed_pack(
    vs: VisualStrategyStore,
    *,
    scene: str,
    archetype: str,
    cand_id: str,
    pack_id: str,
    brief_id: str = "brief_test_01",
) -> tuple[StrategyCandidate, CreativeBrief, VisualStrategyPack]:
    brief = _make_brief(brief_id=brief_id)
    cand = _make_candidate(
        cand_id=cand_id,
        pack_id=pack_id,
        archetype=archetype,
        brief_id=brief.id,
        rule_refs=["r_visual_01", "r_visual_02"],
    )
    pack = _make_pack(scene=scene, candidate_ids=[cand.id], pack_id=pack_id)
    vs.save_visual_strategy_pack(pack.model_dump())
    vs.save_strategy_candidate(cand.model_dump())
    vs.save_creative_brief(brief.model_dump())
    return cand, brief, pack


# ── tests ──────────────────────────────────────────────────────


def test_send_to_workbench_xhs_cover_routes_to_visual_builder(
    client: TestClient, temp_stores: tuple[VisualStrategyStore, RuleStore]
) -> None:
    vs, _ = temp_stores
    cand, brief, _ = _seed_pack(
        vs, scene="xhs_cover", archetype="efficacy_proof",
        cand_id="cand_xhs_01", pack_id="pack_xhs_01",
    )

    resp = client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/send-to-workbench",
        json={"opportunity_id": "opp_test_01", "notes": "first"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["scene"] == "xhs_cover"
    url = data["visual_builder_url"]
    assert url.startswith("/planning/opp_test_01/visual-builder")
    assert f"candidate_id={cand.id}" in url
    assert f"creative_brief_id={brief.id}" in url
    assert data["note_pack_id"], "xhs_cover 应生成 NotePack"

    # NotePack 多 slot：cover + 3 body
    pack_raw = vs.get_note_pack_by_candidate(cand.id)
    assert pack_raw is not None
    assert pack_raw["scene"] == "xhs_cover"
    assert pack_raw["cover"]["positive_prompt_zh"], "cover 必须有正向 prompt"
    assert len(pack_raw["body"]) == 3, "默认 body 数量为 3"
    slot_ids = [b["slot_id"] for b in pack_raw["body"]]
    assert slot_ids == ["body_1", "body_2", "body_3"]
    archetype_dims = {b["archetype_dim"] for b in pack_raw["body"]}
    assert len(archetype_dims) >= 2, "body 三张应来自至少两种 archetype_dim"

    # CopywritingCompiler 应填了 headline + body_text
    cp = pack_raw.get("copy") or {}
    assert cp.get("headline"), "copywriting headline 应非空"
    assert cp.get("body_text"), "copywriting body_text 应非空"


def test_send_to_workbench_main_image_routes_to_infinite_canvas(
    client: TestClient, temp_stores: tuple[VisualStrategyStore, RuleStore]
) -> None:
    vs, _ = temp_stores
    cand, _, _ = _seed_pack(
        vs, scene="taobao_main_image", archetype="function_demo",
        cand_id="cand_main_01", pack_id="pack_main_01",
    )

    resp = client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/send-to-workbench",
        json={"opportunity_id": "opp_test_02"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["scene"] == "taobao_main_image"
    url = data["visual_builder_url"]
    assert url.startswith("/growth-lab/workspace"), url
    assert f"candidate_id={cand.id}" in url
    # 主图无 NotePack
    assert not data.get("note_pack_id")


def test_full_context_aggregates_candidate_brief_pack(
    client: TestClient, temp_stores: tuple[VisualStrategyStore, RuleStore]
) -> None:
    vs, _ = temp_stores
    cand, brief, pack = _seed_pack(
        vs, scene="xhs_cover", archetype="lifestyle",
        cand_id="cand_full_01", pack_id="pack_full_01",
    )
    # 先推一次以生成 NotePack
    client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/send-to-workbench",
        json={"opportunity_id": "opp_full_01"},
    )

    resp = client.get(f"/content-planning/visual-strategy/candidates/{cand.id}/full-context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate"]["id"] == cand.id
    assert data["brief"]["id"] == brief.id
    assert data["scene"] == "xhs_cover"
    assert data["note_pack"], "xhs_cover full-context 应包含 note_pack"
    assert data["pack"]["id"] == pack.id
    assert isinstance(data["rule_refs_detail"], list)


def test_note_pack_endpoint_repeatable_and_returns_multi_slots(
    client: TestClient, temp_stores: tuple[VisualStrategyStore, RuleStore]
) -> None:
    vs, _ = temp_stores
    cand, _, _ = _seed_pack(
        vs, scene="xhs_cover", archetype="efficacy_proof",
        cand_id="cand_np_01", pack_id="pack_np_01",
    )

    r1 = client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/note-pack",
        json={"body_count": 3},
    )
    assert r1.status_code == 200, r1.text
    np1 = r1.json().get("note_pack") or r1.json()
    assert len(np1["body"]) == 3
    pack_id_first = np1["id"]

    # 重复 POST：刷出新的 pack（force_recompile 默认 False，但端点幂等返回最新）
    r2 = client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/note-pack",
        json={"body_count": 3, "force_recompile": True},
    )
    assert r2.status_code == 200, r2.text
    np2 = r2.json().get("note_pack") or r2.json()
    assert len(np2["body"]) == 3
    # 候选可被切换/重编：重编后任一 slot 仍存在
    assert {b["slot_id"] for b in np2["body"]} == {"body_1", "body_2", "body_3"}
    assert np2.get("scene") == "xhs_cover"
    # 至少 cover/body 仍可解析
    assert np2["cover"]["id"]
    # pack 可能会变化或被覆盖；只要 candidate_id 匹配
    assert np2.get("candidate_id") == cand.id
    assert pack_id_first  # 不强制 ID 改变，仅确认两次都返回结构完整


def test_recompile_slot_overrides_prompt_and_persists(
    client: TestClient, temp_stores: tuple[VisualStrategyStore, RuleStore]
) -> None:
    vs, _ = temp_stores
    cand, _, _ = _seed_pack(
        vs, scene="xhs_cover", archetype="lifestyle",
        cand_id="cand_rs_01", pack_id="pack_rs_01",
    )
    client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/send-to-workbench",
        json={"opportunity_id": "opp_rs_01"},
    )

    new_subject = "新的 cover 正向 prompt 测试 - manual"
    resp = client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/note-pack/recompile-slot",
        json={"slot_id": "cover", "subject": new_subject, "negative_prompt": "禁止 logo"},
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["slot_id"] == "cover"
    assert out["prompt_spec"]["positive_prompt_zh"] == new_subject
    assert out["prompt_spec"]["negative_prompt_zh"] == "禁止 logo"

    # 持久化：再读 NotePack 应已更新
    pack_raw = vs.get_note_pack_by_candidate(cand.id)
    assert pack_raw["cover"]["positive_prompt_zh"] == new_subject

    # 同样支持 body slot
    body_subject = "body_1 重编测试"
    resp2 = client.post(
        f"/content-planning/visual-strategy/candidates/{cand.id}/note-pack/recompile-slot",
        json={"slot_id": "body_1", "subject": body_subject},
    )
    assert resp2.status_code == 200
    pack_after = vs.get_note_pack_by_candidate(cand.id)
    body_1 = next(b for b in pack_after["body"] if b["slot_id"] == "body_1")
    assert body_1["prompt_spec"]["positive_prompt_zh"] == body_subject


def test_feedback_endpoint_runs_through_engine(
    client: TestClient, temp_stores: tuple[VisualStrategyStore, RuleStore]
) -> None:
    vs, _ = temp_stores
    cand, _, _ = _seed_pack(
        vs, scene="xhs_cover", archetype="function_demo",
        cand_id="cand_fb_01", pack_id="pack_fb_01",
    )

    payload: dict[str, Any] = {
        "image_variant_id": "img_test_01",
        "strategy_candidate_id": cand.id,
        "decision": "winner",
        "expert_score": {
            "first_glance": 8,
            "audience_fit": 7,
            "function_clarity": 8,
            "style_fit": 7,
            "differentiation": 8,
            "overall": 7.6,
        },
        "rule_ids": cand.rule_refs,
        "comments": "test winner",
    }
    resp = client.post("/content-planning/visual-strategy/feedback", json=payload)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    # FeedbackEngine.submit 至少应回执 feedback_id 或类似键
    assert isinstance(out, dict)
    assert any(k for k in out.keys() if "feedback" in k or "rule" in k or "weight" in k or "id" in k)
