"""category_adapter — 把骨架模板按 intent 按新品类重参数化。

入：skeletonize() 后的 ScriptTemplate + IntentContext
出：一个新的 ScriptTemplate（source_kind="adapted"），已填入新品类的 visual_spec /
copy_spec / prompt_blocks / global_style.visual_keywords / strategy_pack 等细节。

实现：
1. 优先走 LLM：把"骨架 + intent"打包成一次 JSON 输出请求，一次拿到所有 slot 的
   视觉/文案/prompt_blocks，以及整体的 visual_keywords / color_system /
   primary_message。
2. LLM 不可用或输出不合规时降级：用 intent 的字段做字面拼接（"{product} 的 {role}"
   这类兜底，保证能继续跑通）。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any

from apps.growth_lab.schemas.visual_workspace import (
    IntentContext,
    ScriptTemplate,
    TemplateSlot,
)

logger = logging.getLogger(__name__)


_ADAPT_SYSTEM_PROMPT = """\
你是主图策划的品类适配器。你会收到：
1. 一个"骨架模板"——它定义了 5 张主图的叙事结构、构图与角色（但文案和场景是空的）
2. 一个"新品类意图"——商品名、目标人群、必呈现卖点、要规避的点

你的任务是：**只按新品类重填具体文案/场景/关键词**，严格保留骨架的 card 顺序、
card_type、role、composition、aspect_ratio 等结构不变。

输出严格 JSON（不要 code fence、不要解释），schema：
{
  "overall": {
    "visual_keywords": ["..."],
    "avoid_keywords": ["..."],
    "primary_message": "...",
    "tone": "...",
    "color_primary": "...",
    "color_secondary": ""
  },
  "slots": [
    {
      "index": 1,
      "visual_spec": "新品类下这张卡片该展示的场景/主体/布景（40-90 字）",
      "copy_spec": "主标题；副标题；卖点",
      "headline": "≤15 字主标题",
      "subheadline": "",
      "selling_points": ["..."],
      "positive_prompt_blocks": ["画面块1", "画面块2"],
      "negative_prompt_blocks": ["要规避的画面词1", "..."]
    }
    // ...每个骨架 slot 一份
  ]
}

要求：
- 所有文本使用简体中文
- 不能出现原洁面乳/原品类的词汇
- positive_prompt_blocks 每条 15-30 字，写画面，不写口号
- 卖点数量控制在 2-3 条
- slots 按 index 1..N 完整覆盖骨架的每个 slot
"""


def _skeleton_payload(skel: ScriptTemplate) -> dict[str, Any]:
    slots_payload = []
    for s in skel.slots:
        slots_payload.append({
            "index": s.index,
            "role": s.role,
            "aspect_ratio": s.aspect_ratio,
            "card_type": (s.extra or {}).get("card_type", ""),
            "message_role": (s.extra or {}).get("message_role", ""),
            "prompt_intent": (s.extra or {}).get("prompt_intent", ""),
            "objective": (s.extra or {}).get("objective", ""),
            "composition": (s.extra or {}).get("composition", {}),
            "background_complexity": (s.extra or {}).get("background", {}).get("complexity", ""),
            "lighting_style": (s.extra or {}).get("lighting", {}).get("style", ""),
            "selling_point_roles": s.selling_points or [],
        })
    return {
        "card_count": len(skel.slots),
        "slots": slots_payload,
        "review_dimensions": [
            d for d in ((skel.review_spec or {}).get("checklist") or [])
        ],
    }


def _intent_payload(intent: IntentContext) -> dict[str, Any]:
    return {
        "product_name": intent.product_name,
        "audience": intent.audience,
        "must_have": intent.must_have,
        "avoid": intent.avoid,
        "style_refs": intent.style_refs,
        "scenario_refs": intent.scenario_refs,
    }


def _safe_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
    return {}


def _run_async(coro):
    """兼容同步上下文调用异步 LLM。"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return asyncio.run(coro)
    if loop.is_running():
        # 在 FastAPI 已运行的 loop 下，使用 nest_asyncio 的替代：起新线程跑
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(asyncio.run, coro)
            return fut.result()
    return loop.run_until_complete(coro)


async def _call_llm(skel: ScriptTemplate, intent: IntentContext) -> dict[str, Any]:
    try:
        from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
    except ImportError:
        return {}

    user = {
        "skeleton": _skeleton_payload(skel),
        "intent": _intent_payload(intent),
    }
    try:
        resp = await llm_router.achat(
            [
                LLMMessage(role="system", content=_ADAPT_SYSTEM_PROMPT),
                LLMMessage(role="user", content=json.dumps(user, ensure_ascii=False)),
            ],
            temperature=0.5, max_tokens=2400,
        )
        obj = _safe_json(resp.content or "")
        if obj.get("slots"):
            return obj
    except Exception as exc:
        logger.warning("[category_adapter] LLM 调用失败: %s", exc)
    return {}


def _fallback(skel: ScriptTemplate, intent: IntentContext) -> dict[str, Any]:
    """LLM 不可用时的字面替换降级。"""
    product = intent.product_name or "商品"
    audience = intent.audience or "目标人群"
    must = intent.must_have or []
    avoid = intent.avoid or []
    slots_out = []
    for s in skel.slots:
        role = s.role or f"第{s.index}张"
        obj = (s.extra or {}).get("objective") or ""
        visual = f"{audience}在真实场景中使用{product}；{obj}".strip("；")
        selling = must[:2] if must else []
        slots_out.append({
            "index": s.index,
            "visual_spec": visual,
            "copy_spec": f"主标题：{product} · {role}",
            "headline": f"{product}",
            "subheadline": "",
            "selling_points": selling,
            "positive_prompt_blocks": [
                f"{product} 主视觉，{audience}真实使用场景",
                f"{role}：{obj or '画面突出核心卖点'}",
            ],
            "negative_prompt_blocks": list(avoid[:4]),
        })
    return {
        "overall": {
            "visual_keywords": (intent.style_refs or [])[:5],
            "avoid_keywords": list(avoid),
            "primary_message": product,
            "tone": "",
            "color_primary": "",
            "color_secondary": "",
        },
        "slots": slots_out,
    }


def _apply(skel: ScriptTemplate, intent: IntentContext, payload: dict[str, Any]) -> ScriptTemplate:
    tpl = skel.model_copy(deep=True)
    overall = payload.get("overall") or {}
    slots_payload = payload.get("slots") or []
    by_idx: dict[int, dict[str, Any]] = {
        int(s.get("index", 0)): s for s in slots_payload if isinstance(s, dict)
    }

    # ── 顶层 ──
    if overall:
        tpl.global_style = tpl.global_style or {}
        if overall.get("visual_keywords"):
            tpl.global_style["visual_keywords"] = list(overall["visual_keywords"])[:8]
        if overall.get("avoid_keywords"):
            tpl.global_style["avoid_keywords"] = list(overall["avoid_keywords"])[:8]
        if overall.get("tone"):
            tpl.global_style["tone"] = str(overall["tone"])[:60]
        cs = tpl.global_style.get("color_system") or {}
        if overall.get("color_primary"):
            cs["primary"] = str(overall["color_primary"])[:30]
        if overall.get("color_secondary"):
            cs["secondary"] = str(overall["color_secondary"])[:30]
        tpl.global_style["color_system"] = cs

        # strategy_pack.message_hierarchy
        mh = (tpl.strategy_pack or {}).get("message_hierarchy") or {}
        if overall.get("primary_message"):
            mh["primary_message"] = str(overall["primary_message"])[:40]
        if intent.must_have:
            mh["secondary_messages"] = list(intent.must_have)[:4]
        tpl.strategy_pack = tpl.strategy_pack or {}
        tpl.strategy_pack["message_hierarchy"] = mh

    # business_context 按 intent 回填
    tpl.business_context = {
        "product_name": intent.product_name,
        "target_audience": [intent.audience] if intent.audience else [],
        "must_have": list(intent.must_have),
        "avoid": list(intent.avoid),
    }

    # ── slot 层 ──
    new_slots: list[TemplateSlot] = []
    for slot in tpl.slots:
        payload_slot = by_idx.get(int(slot.index)) or {}
        slot = slot.model_copy(deep=True)
        if payload_slot.get("visual_spec"):
            slot.visual_spec = str(payload_slot["visual_spec"])[:600]
        if payload_slot.get("copy_spec"):
            slot.copy_spec = str(payload_slot["copy_spec"])[:400]
        if payload_slot.get("headline"):
            slot.headline = str(payload_slot["headline"])[:30]
        if payload_slot.get("subheadline"):
            slot.subheadline = str(payload_slot["subheadline"])[:30]
        if payload_slot.get("selling_points"):
            slot.selling_points = [str(x)[:20] for x in payload_slot["selling_points"]][:4]
        if payload_slot.get("positive_prompt_blocks"):
            slot.positive_prompt_blocks = [
                str(x)[:80] for x in payload_slot["positive_prompt_blocks"]
            ][:6]
        if payload_slot.get("negative_prompt_blocks"):
            slot.negative_prompt_blocks = [
                str(x)[:40] for x in payload_slot["negative_prompt_blocks"]
            ][:6]
        new_slots.append(slot)
    tpl.slots = new_slots

    # 标记 adapted
    tpl.source_kind = "adapted"
    raw_id = (skel.template_id or "tpl").removesuffix("__skeleton")
    sig = hashlib.md5(
        f"{raw_id}|{intent.product_name}|{intent.audience}|{','.join(intent.must_have)}".encode("utf-8")
    ).hexdigest()[:6]
    tpl.template_id = f"{raw_id}__adapted_{sig}"
    tpl.name = f"{(skel.name or '主图模板').removesuffix('（骨架）')} · {intent.product_name or '跨品类'}"
    return tpl


def adapt_skeleton(skel: ScriptTemplate, intent: IntentContext) -> ScriptTemplate:
    """把骨架按 intent 重参数化。LLM 优先，失败降级。"""
    payload = _run_async(_call_llm(skel, intent)) if intent.product_name else {}
    if not payload:
        logger.info("[category_adapter] 使用字面降级：product=%s", intent.product_name)
        payload = _fallback(skel, intent)
    return _apply(skel, intent, payload)
