#!/usr/bin/env python3
"""端到端验收脚本：从真实 promoted 机会卡走完完整链路。

用法：
    python -m apps.content_planning.scripts.run_e2e_acceptance [opportunity_id]

如果不传 opportunity_id，自动取第一个 promoted 卡。
"""

from __future__ import annotations

import json
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow


def _banner(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def _section(title: str, ok: bool = True) -> None:
    icon = "PASS" if ok else "FAIL"
    print(f"\n  [{icon}] {title}")


def _dump(obj: dict, indent: int = 4, max_keys: int = 12) -> str:
    keys = list(obj.keys())[:max_keys]
    subset = {k: obj[k] for k in keys}
    raw = json.dumps(subset, ensure_ascii=False, indent=indent, default=str)
    if len(raw) > 1200:
        raw = raw[:1200] + "\n    ... (truncated)"
    return raw


def run_acceptance(opportunity_id: str | None = None) -> bool:
    adapter = IntelHubAdapter()
    flow = OpportunityToPlanFlow(adapter=adapter)

    _banner("内容策划工作台 端到端验收")
    print(f"  时间: {datetime.now(UTC).isoformat()}")

    # Step 0: find promoted card
    if opportunity_id is None:
        promoted = adapter.get_promoted_cards()
        if not promoted:
            print("\n  [SKIP] 无 promoted 机会卡，验收跳过")
            print("  提示：请先通过 UI 对机会卡提交检视并升级")
            return False
        card = promoted[0]
        opportunity_id = card.opportunity_id
        print(f"  自动选取第一张 promoted 卡: {opportunity_id}")
        print(f"  共有 {len(promoted)} 张 promoted 卡可用")
    else:
        card = adapter.get_card(opportunity_id)
        if card is None:
            print(f"\n  [FAIL] 机会卡 {opportunity_id} 不存在")
            return False

    print(f"  卡片: {card.title}")
    print(f"  状态: {card.opportunity_status}")

    passed = True
    results = {}

    # Step 1: Generate Brief
    _banner("Step 1: Generate OpportunityBrief")
    try:
        brief = flow.build_brief(opportunity_id)
        results["brief"] = brief.model_dump(mode="json")
        _section(f"Brief 生成成功 (brief_id={brief.brief_id})")
        print(f"    content_goal: {brief.content_goal}")
        print(f"    target_scene: {brief.target_scene}")
        print(f"    primary_value: {brief.primary_value}")
        print(f"    brief_status: {brief.brief_status}")
    except Exception as exc:
        _section(f"Brief 生成失败: {exc}", ok=False)
        passed = False
        return passed

    # Step 2: Match Templates
    _banner("Step 2: Match Templates")
    try:
        match_result = flow.match_templates(opportunity_id)
        results["match_result"] = match_result.model_dump(mode="json")
        _section(f"模板匹配成功 (primary={match_result.primary_template.template_name})")
        print(f"    primary score: {match_result.primary_template.score:.3f}")
        for sec in match_result.secondary_templates[:2]:
            print(f"    secondary: {sec.template_name} ({sec.score:.3f})")
    except Exception as exc:
        _section(f"模板匹配失败: {exc}", ok=False)
        passed = False
        return passed

    # Step 3: Generate Strategy
    _banner("Step 3: Generate RewriteStrategy")
    try:
        strategy = flow.build_strategy(opportunity_id)
        results["strategy"] = strategy.model_dump(mode="json")
        _section(f"策略生成成功 (strategy_id={strategy.strategy_id})")
        print(f"    positioning: {strategy.positioning_statement[:80]}")
        print(f"    hook: {strategy.new_hook}")
        print(f"    tone: {strategy.tone_of_voice}")
        print(f"    hook_strategy: {strategy.hook_strategy[:60]}")
        print(f"    cta_strategy: {strategy.cta_strategy[:60]}")
        print(f"    strategy_status: {strategy.strategy_status}")
    except Exception as exc:
        _section(f"策略生成失败: {exc}", ok=False)
        passed = False
        return passed

    # Step 4: Build Plan
    _banner("Step 4: Build NewNotePlan")
    try:
        plan = flow.build_plan(opportunity_id)
        results["note_plan"] = plan.model_dump(mode="json")
        _section(f"策划方案生成成功 (plan_id={plan.plan_id})")
        print(f"    title axes: {plan.title_plan.title_axes if plan.title_plan else 'N/A'}")
        print(f"    body hook: {plan.body_plan.opening_hook[:60] if plan.body_plan else 'N/A'}")
        if plan.image_plan:
            print(f"    image slots: {len(plan.image_plan.image_slots)}")
    except Exception as exc:
        _section(f"策划方案失败: {exc}", ok=False)
        passed = False
        return passed

    # Step 5: Generate Content
    _banner("Step 5: Generate Content (titles/body/image briefs)")
    try:
        titles = flow.regenerate_titles(opportunity_id)
        results["titles"] = titles.model_dump(mode="json")
        _section(f"标题生成成功 (mode={titles.mode}, count={len(titles.titles)})")
        for t in titles.titles[:3]:
            print(f"    - {t.title_text}")
    except Exception as exc:
        _section(f"标题生成失败: {exc}", ok=False)
        passed = False

    try:
        body = flow.regenerate_body(opportunity_id)
        results["body"] = body.model_dump(mode="json")
        _section(f"正文生成成功 (mode={body.mode})")
        if body.opening_hook:
            print(f"    opening: {body.opening_hook[:80]}")
    except Exception as exc:
        _section(f"正文生成失败: {exc}", ok=False)
        passed = False

    try:
        imgs = flow.regenerate_image_briefs(opportunity_id)
        results["image_briefs"] = imgs.model_dump(mode="json")
        _section(f"图片指令生成成功 (mode={imgs.mode}, slots={len(imgs.slot_briefs)})")
    except Exception as exc:
        _section(f"图片指令生成失败: {exc}", ok=False)
        passed = False

    # Step 6: Lineage Check
    _banner("Step 6: Lineage Verification")
    lineage_ok = True
    session = flow.get_session_data(opportunity_id)
    np = session.get("note_plan", {})
    if np.get("opportunity_id") != opportunity_id:
        print(f"    [WARN] note_plan.opportunity_id 不匹配")
        lineage_ok = False
    if np.get("brief_id") and np.get("brief_id") == results.get("brief", {}).get("brief_id"):
        print(f"    brief_id 一致: {np.get('brief_id')}")
    if np.get("strategy_id") and np.get("strategy_id") == results.get("strategy", {}).get("strategy_id"):
        print(f"    strategy_id 一致: {np.get('strategy_id')}")
    if np.get("template_id"):
        print(f"    template_id: {np.get('template_id')}")
    _section("回溯链路", ok=lineage_ok)

    # Summary
    _banner("验收结果")
    if passed:
        print("  ALL PASSED - 全链路验收通过")
    else:
        print("  PARTIAL FAIL - 部分步骤失败，请检查上方详情")

    # Export
    export_dir = ROOT / "data" / "exports" / "content_planning"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"e2e_{opportunity_id[:12]}.json"
    export_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\n  完整结果导出: {export_path.relative_to(ROOT)}")

    return passed


if __name__ == "__main__":
    oid = sys.argv[1] if len(sys.argv) > 1 else None
    ok = run_acceptance(oid)
    sys.exit(0 if ok else 1)
