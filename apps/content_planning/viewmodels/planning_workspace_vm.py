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


def build_workspace_vm(
    card: dict[str, Any],
    brief: dict[str, Any],
    match_result: dict[str, Any],
    strategy: dict[str, Any],
    note_plan: dict[str, Any],
    generated: dict[str, Any],
) -> dict[str, Any]:
    """组装完整的策划工作台 ViewModel。"""
    return {
        "context": build_planning_context(card),
        "brief_summary": build_brief_summary(brief),
        "template_candidates": build_template_candidates(match_result),
        "strategy_summary": build_strategy_summary(strategy),
        "plan_board": build_plan_board(note_plan, generated),
    }
