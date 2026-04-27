"""ViewModel 层：把后端复杂数据模型映射为前端友好的精简结构。

所有函数接收 dict（而非 Pydantic model），通过 .get() 安全取值，
缺失字段不会抛异常。
"""

from __future__ import annotations

from typing import Any


def build_planning_context(card: dict[str, Any]) -> dict[str, Any]:
    """从机会卡提取前端所需的核心上下文。"""
    return {
        "title": card.get("title", ""),
        "opportunity_type": card.get("opportunity_type", ""),
        "confidence": card.get("confidence", 0),
        "insight_statement": card.get("insight_statement", ""),
    }


def build_brief_summary(brief: dict[str, Any]) -> dict[str, Any]:
    """从 OpportunityBrief 的 20+ 字段提炼为 4 张语义卡片。"""
    return {
        "what": {
            "label": "机会概述",
            "items": [
                brief.get("opportunity_title", ""),
                brief.get("opportunity_summary", ""),
            ],
        },
        "why": {
            "label": "值得做的理由",
            "items": [
                brief.get("why_worth_doing", ""),
                brief.get("competitive_angle", ""),
                brief.get("engagement_proof", ""),
            ],
        },
        "direction": {
            "label": "内容方向",
            "items": [
                brief.get("suggested_direction", ""),
                brief.get("primary_value", ""),
                *brief.get("secondary_values", []),
                *brief.get("visual_style_direction", []),
            ],
        },
        "avoid": {
            "label": "规避事项",
            "items": [
                *brief.get("avoid_directions", []),
                *brief.get("constraints", []),
            ],
        },
    }


def build_template_candidates(match_result: dict[str, Any]) -> dict[str, Any]:
    """提取主模板 + 前 2 个备选模板的关键信息。"""
    primary = match_result.get("primary_template") or {}
    secondaries = match_result.get("secondary_templates") or []

    def _pick(entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": entry.get("template_name", ""),
            "score": entry.get("score", 0.0),
            "reason": entry.get("reason", ""),
            "matched_dimensions": entry.get("matched_dimensions") or {},
        }

    return {
        "primary": _pick(primary),
        "secondaries": [_pick(s) for s in secondaries[:2]],
    }


def build_strategy_summary(strategy: dict[str, Any]) -> dict[str, Any]:
    """从 RewriteStrategy 提炼为 4 个可渲染的 block。"""
    return {
        "title_strategy": {
            "label": "标题策略",
            "items": strategy.get("title_strategy") or [],
        },
        "body_strategy": {
            "label": "正文策略",
            "items": strategy.get("body_strategy") or [],
        },
        "image_strategy": {
            "label": "图片策略",
            "items": strategy.get("image_strategy") or [],
        },
        "tone_and_risk": {
            "label": "调性与风险",
            "items": [
                strategy.get("tone_of_voice", ""),
                strategy.get("cta_strategy", ""),
                *strategy.get("risk_notes", []),
            ],
        },
    }


def build_plan_board(
    note_plan: dict[str, Any],
    generated: dict[str, Any],
) -> dict[str, Any]:
    """整合 note_plan + 生成结果为看板视图。"""

    # --- titles ---
    titles_obj = generated.get("titles") or {}
    raw_titles: list[dict[str, Any]] = titles_obj.get("titles") or []
    titles = [
        {
            "title_text": t.get("title_text", ""),
            "axis": t.get("axis", ""),
        }
        for t in raw_titles[:5]
    ]

    # --- body_summary ---
    body_plan = note_plan.get("body_plan") or {}
    outline_raw: list[str] = body_plan.get("body_outline") or []
    outline_text = " / ".join(outline_raw)
    if len(outline_text) > 200:
        outline_text = outline_text[:200] + "…"

    body_summary = {
        "opening_hook": body_plan.get("opening_hook", ""),
        "body_outline": outline_text,
        "cta_direction": body_plan.get("cta_direction", ""),
    }

    # --- image_slots ---
    image_plan = note_plan.get("image_plan") or {}
    raw_slots: list[dict[str, Any]] = image_plan.get("image_slots") or []
    image_slots = [
        {
            "slot_index": slot.get("slot_index", idx),
            "role": slot.get("role", ""),
            "subject": slot.get("subject", slot.get("intent", "")),
        }
        for idx, slot in enumerate(raw_slots[:5])
    ]

    # --- publish_notes ---
    publish_notes: list[str] = note_plan.get("publish_notes") or []

    return {
        "titles": titles,
        "body_summary": body_summary,
        "image_slots": image_slots,
        "publish_notes": publish_notes,
    }


def build_visual_strategy_summary(
    visual_strategy: dict[str, Any] | None,
) -> dict[str, Any]:
    """把路由层反查到的 VisualStrategyPack + StrategyCandidate 列表
    映射成模板友好的精简结构。

    入参形如：
        {
            "has_pack": bool,
            "pack": {...} | None,
            "candidates": [{...}, ...],
            "default_category": str,
            "default_scene": str,
        }
    """
    visual_strategy = visual_strategy or {}
    pack = visual_strategy.get("pack") or {}
    candidates = visual_strategy.get("candidates") or []

    def _pick(c: dict[str, Any]) -> dict[str, Any]:
        score = c.get("score") or {}
        return {
            "id": c.get("id", ""),
            "name": c.get("name", "") or c.get("archetype", ""),
            "archetype": c.get("archetype", ""),
            "hypothesis": c.get("hypothesis", ""),
            "score_total": float(score.get("total", 0.0) or 0.0),
            "score_brand_fit": float(score.get("brand_fit", 0.0) or 0.0),
            "score_audience_fit": float(score.get("audience_fit", 0.0) or 0.0),
            "score_differentiation": float(score.get("differentiation", 0.0) or 0.0),
            "rule_refs_count": len(c.get("rule_refs") or []),
            "risks_count": len(c.get("risks") or []),
            "status": c.get("status", "generated"),
            "creative_brief_id": c.get("creative_brief_id", ""),
            "prompt_spec_id": c.get("prompt_spec_id", ""),
        }

    return {
        "has_pack": bool(visual_strategy.get("has_pack") and pack),
        "pack_id": pack.get("id", ""),
        "scene": pack.get("scene", "") or visual_strategy.get("default_scene", ""),
        "pack_status": pack.get("status", ""),
        "default_category": visual_strategy.get("default_category", ""),
        "default_scene": visual_strategy.get("default_scene", "taobao_main_image"),
        "candidate_count": len(candidates),
        "top_candidates": [_pick(c) for c in candidates],
    }


def build_context_bar(
    card: dict[str, Any],
    brief: dict[str, Any] | None,
    source_notes: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """单行 ContextBar 数据：标题 / 置信度 / 类型 / lens / 品牌 / 来源笔记数。"""
    brief = brief or {}
    source_notes = source_notes or []
    confidence = card.get("confidence", 0) or 0
    if isinstance(confidence, (int, float)) and confidence <= 1:
        conf_pct = int(round(confidence * 100))
    else:
        try:
            conf_pct = int(round(float(confidence)))
        except (TypeError, ValueError):
            conf_pct = 0
    conf_pct = max(0, min(conf_pct, 100))
    return {
        "title": card.get("title", "") or "(未命名机会)",
        "opportunity_type": card.get("opportunity_type", ""),
        "confidence_pct": conf_pct,
        "lens_id": card.get("lens_id", "") or "",
        "category": card.get("category", "") or "",
        "brand_id": brief.get("brand_id", "") or card.get("brand_id", "") or "",
        "brand_name": brief.get("brand_name", "") or "",
        "source_notes_count": len(source_notes),
    }


_STEP_DEFS: list[tuple[str, str]] = [
    ("brief", "Brief"),
    ("strategy", "Strategy"),
    ("visual", "视觉策略"),
    ("plan", "NotePlan"),
    ("handoff", "接力"),
]


def _step_status(
    *,
    has_data: bool,
    is_stale: bool,
) -> str:
    if is_stale:
        return "stale"
    return "ready" if has_data else "empty"


def _step_summary(key: str, *, has_data: bool, count: int = 0, hint: str = "") -> str:
    if not has_data:
        return hint or "尚未生成"
    if key == "brief":
        return "Brief 已就绪"
    if key == "strategy":
        return f"已产出策略 {count} 块" if count else "策略已就绪"
    if key == "visual":
        return f"已编译 {count} 类候选" if count else "视觉策略已就绪"
    if key == "plan":
        return f"NotePlan 含 {count} 个图位" if count else "NotePlan 已就绪"
    if key == "handoff":
        return "已可推送至视觉工作台"
    return "已就绪"


def build_step_states(
    *,
    brief: dict[str, Any] | None,
    match_result: dict[str, Any] | None,
    strategy: dict[str, Any] | None,
    visual_strategy: dict[str, Any] | None,
    note_plan: dict[str, Any] | None,
    generated: dict[str, Any] | None,
    stale_flags: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """为左主栏 Hero Flow 计算 5 step 的 status + summary + active 标记。

    active 取首个非 ready 的 step；若全部 ready，则 active = "handoff"。
    """
    brief = brief or {}
    match_result = match_result or {}
    strategy = strategy or {}
    visual_strategy = visual_strategy or {}
    note_plan = note_plan or {}
    generated = generated or {}
    stale = stale_flags or {}

    has_brief = bool(brief)
    has_strategy = bool(strategy.get("title_strategy") or strategy.get("body_strategy") or strategy.get("image_strategy"))
    strategy_block_count = sum(
        1
        for k in ("title_strategy", "body_strategy", "image_strategy")
        if strategy.get(k)
    )
    vs_pack_present = bool(visual_strategy.get("has_pack") and visual_strategy.get("pack"))
    vs_count = len(visual_strategy.get("candidates") or [])
    has_plan = bool(note_plan)
    image_slots_count = len((note_plan.get("image_plan") or {}).get("image_slots") or [])

    handoff_ready = bool(generated.get("titles")) and has_plan

    raw = [
        {
            "key": "brief",
            "has_data": has_brief,
            "stale": bool(stale.get("brief")),
            "count": 0,
            "hint": "进入页面时自动构建；缺失可点击右栏 Co-pilot 检视",
        },
        {
            "key": "strategy",
            "has_data": has_strategy,
            "stale": bool(stale.get("strategy") or stale.get("match")),
            "count": strategy_block_count,
            "hint": "Brief 就绪后由 StrategyDirector 产出",
        },
        {
            "key": "visual",
            "has_data": vs_pack_present,
            "stale": False,
            "count": vs_count,
            "hint": "基于专家 RulePack 编译 6 类视觉候选",
        },
        {
            "key": "plan",
            "has_data": has_plan,
            "stale": bool(stale.get("plan") or stale.get("titles") or stale.get("body")),
            "count": image_slots_count,
            "hint": "策略落地为 NotePlan：标题 / 正文 / 图位",
        },
        {
            "key": "handoff",
            "has_data": handoff_ready,
            "stale": False,
            "count": 0,
            "hint": "至少需 NotePlan 与标题就绪",
        },
    ]

    states: list[dict[str, Any]] = []
    for idx, ((key, label), info) in enumerate(zip(_STEP_DEFS, raw, strict=True), start=1):
        status = _step_status(has_data=info["has_data"], is_stale=info["stale"])
        states.append(
            {
                "key": key,
                "idx": idx,
                "label": label,
                "status": status,
                "active": False,
                "summary": _step_summary(
                    key,
                    has_data=info["has_data"],
                    count=info["count"],
                    hint=info["hint"],
                ),
                "count": info["count"],
            }
        )

    active_idx = next(
        (i for i, s in enumerate(states) if s["status"] != "ready"),
        len(states) - 1,
    )
    states[active_idx]["active"] = True
    return states


def build_pulse_initial(
    *,
    review_summary: dict[str, Any] | None,
    pipeline_run_id: str,
    stale_flags: dict[str, Any] | None,
    needs_build: bool,
) -> dict[str, Any]:
    """Co-pilot Pulse tab 的服务端初始数据。"""
    review_summary = review_summary or {}
    stale_flags = stale_flags or {}
    stale_count = sum(1 for v in stale_flags.values() if v)
    return {
        "needs_build": bool(needs_build),
        "stale_count": stale_count,
        "pipeline_run_id": pipeline_run_id or "",
        "review_count": int(review_summary.get("review_count", 0) or 0),
        "avg_quality_score": float(review_summary.get("avg_quality_score", 0.0) or 0.0),
        "approval_status": review_summary.get("approval_status", "") or "",
    }


def build_workspace_vm(
    card: dict[str, Any],
    brief: dict[str, Any],
    match_result: dict[str, Any],
    strategy: dict[str, Any],
    note_plan: dict[str, Any],
    generated: dict[str, Any],
    visual_strategy: dict[str, Any] | None = None,
    *,
    source_notes: list[dict[str, Any]] | None = None,
    stale_flags: dict[str, Any] | None = None,
    review_summary: dict[str, Any] | None = None,
    pipeline_run_id: str = "",
    needs_build: bool = False,
) -> dict[str, Any]:
    """组装完整的策划工作台 ViewModel。"""
    visual_strategy_summary = build_visual_strategy_summary(visual_strategy)
    return {
        "context": build_planning_context(card),
        "brief_summary": build_brief_summary(brief),
        "template_candidates": build_template_candidates(match_result),
        "strategy_summary": build_strategy_summary(strategy),
        "plan_board": build_plan_board(note_plan, generated),
        "visual_strategy": visual_strategy_summary,
        "context_bar": build_context_bar(card, brief, source_notes),
        "step_states": build_step_states(
            brief=brief,
            match_result=match_result,
            strategy=strategy,
            visual_strategy=visual_strategy or {},
            note_plan=note_plan,
            generated=generated,
            stale_flags=stale_flags,
        ),
        "pulse_initial": build_pulse_initial(
            review_summary=review_summary,
            pipeline_run_id=pipeline_run_id,
            stale_flags=stale_flags,
            needs_build=needs_build,
        ),
    }
