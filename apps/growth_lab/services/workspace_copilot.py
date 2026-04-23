"""WorkspaceCopilot — 视觉工作台右栏 AI 对话/建议/提案后端。

提供三个原子能力：
1. suggest_actions(node) → 建议动作（基于节点 role/status/variants 给出 3-5 条）
2. propose_edit(node, user_prompt) → 对话 → 执行提案（结构化）
3. explain_lineage(node) → "为什么长这样"溯源（intent/模板/品牌/竞品 四来源摘要）

所有 LLM 调用复用 apps/content_planning/adapters/llm_router.llm_router.achat。
LLM 不可用时给出规则降级。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


_ACTION_SYSTEM_PROMPT = """\
你是视觉工作台的执行助理，帮助商家快速迭代主图/详情/视频节点。
根据节点信息给出 3-5 条"可点即执行"的建议动作。每条动作必须是简短命令式中文，
JSON 数组，每条格式：{"label": "动作名（≤14字）", "intent": "执行意图（给 LLM 的短指令）", "type": "generate|refine|copy_rewrite|replace_scene"}
严格只输出 JSON，不要 code fence、不要解释。
"""

_PROPOSE_SYSTEM_PROMPT = """\
你是视觉工作台的编辑协作 AI。根据节点上下文、对象列表和用户指令，给出一个"结构化执行提案"。
输出严格 JSON：
{
  "summary": "一句话总结（≤30字）",
  "prompt_delta": "对原 prompt 的增量/改写（给图像生成的目标描述）",
  "copy_delta": "对 copy 的调整或空字符串",
  "target_objects": ["要修改的对象 label 列表，命中 node.objects 中 label"],
  "steps": ["分步骤动作列表，≤4 步，每步 ≤20 字"],
  "risks": ["风险/副作用列表，≤3 条"]
}
只输出 JSON，不要 code fence，不要解释。
若用户指令涉及的对象是 locked/不可编辑，不要放进 target_objects。
"""


_PROPOSE_SYSTEM_PROMPT_V2 = """\
你是视觉工作台的编辑协作 AI。根据完整的 EditContextPack、解析好的 ResolvedEditReference 和用户指令，
给出一个"结构化执行提案 v2"，可直接驱动 img2img / 文案改写。

输出严格 JSON（对应 ProposalV2）：
{
  "summary": "一句话总结，说明这轮会改什么、为什么（≤40字）",
  "interpretation_basis": ["理解依据列表，≤4 条；如：用户在画布选择了 hero_product；当前 slot_role=pain_contrast"],
  "resolved_reference": {
    "scope": "scene|object|region|multi_object",
    "primary_targets": ["object_id 列表"],
    "secondary_targets": ["object_id 列表"],
    "resolution_confidence": 0.0,
    "needs_clarification": false,
    "clarification_question": null
  },
  "target_objects": ["最终要改动的 object_id 列表，排除 locked"],
  "locked_objects": ["明确跳过的 object_id 列表"],
  "preserve_rules": ["必须保留的要点列表，≤4 条；如：保持 logo 位置 / 保持 slot_role=pain_contrast"],
  "steps": [
    {
      "action_type": "regenerate_object|restyle_object|rewrite_copy|reposition|replace_background|global_refine",
      "target_object_ids": ["object_id 列表"],
      "params": {"prompt": "给图像模型的短描述", "copy_text": "可选"},
      "strength": "subtle|moderate|strong",
      "reason": "为什么这步"
    }
  ],
  "risks": ["风险/副作用，≤3 条"],
  "requires_confirmation": true,
  "keep_slot_role": true,
  "prompt_delta": "兼容旧前端的 prompt 增量（把 steps 合并成一句）",
  "copy_delta": "兼容旧前端的文案增量"
}

约束：
- 若 ResolvedEditReference.needs_clarification=true 或 resolution_confidence<0.5，不要输出 steps；
  把 summary 写成"需要明确指代对象"，target_objects 留空，requires_confirmation=true。
- 绝不修改 locked 的对象；把它们放进 locked_objects。
- 保留 slot_role / slot_objective，不要把一张主图风格模板改成与当前 slot_role 冲突的内容。
- 严格只输出 JSON，不要 code fence、不要解释。
"""


def _safe_json_list(text: str) -> list[dict]:
    if not text:
        return []
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        pass
    # 尝试提取第一个 JSON array
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            return [d for d in json.loads(m.group(0)) if isinstance(d, dict)]
        except Exception:
            pass
    return []


_FIELD_LABEL = {
    "output_types": "输出类型",
    "product_name": "产品名",
    "audience": "目标人群",
    "must_have": "核心卖点",
    "style_refs": "风格",
    "avoid": "避免",
}

_OUTPUT_KEYWORDS = [
    ("买家秀", "buyer_show"),
    ("视频分镜", "video_shots"),
    ("分镜", "video_shots"),
    ("视频", "video_shots"),
    ("详情", "detail"),
    ("竞品", "competitor"),
    ("主图", "main_image"),
]
_AUDIENCE_RE = re.compile(
    r"(\d+\s*-?\s*\d*\s*岁|男士|男性|女士|女性|宝妈|宝爸|学生党?|职场|"
    r"新手|敏感肌|油皮|干皮|混油|老人|小孩|儿童|孕妇|银发)"
)
_STYLE_KEYWORDS = [
    "极简", "高端", "复古", "港风", "日系", "韩系", "国潮", "ins 风", "ins风",
    "明亮", "暗调", "高级灰", "莫兰迪", "清新", "森系", "中式", "新中式",
    "蒸汽朋克", "赛博朋克", "胶片", "肌理感", "未来感", "科技感",
]
_LIST_SPLIT_RE = re.compile(r"[，,、;；]+")


def _heuristic_extract(user_text: str, cur: dict, missing: list[str]) -> dict:
    """轻量规则 NLU：把用户上一句按优先级归属到第一个缺失字段（或多字段命中）。

    - 永远保守：只填空字段，不覆盖；返回 dict 只含本轮新抽取到的部分。
    - 即使 LLM 已抽取，仍会跑一次（互补）。
    """
    out: dict = {}
    text = (user_text or "").strip()
    if not text or len(text) > 200:
        return out

    out_types: list[str] = []
    seen: set[str] = set()
    for kw, code in _OUTPUT_KEYWORDS:
        if kw in text and code not in seen:
            out_types.append(code)
            seen.add(code)
    if out_types and not cur.get("output_types"):
        out["output_types"] = out_types

    aud_hits = _AUDIENCE_RE.findall(text)
    if aud_hits and not cur.get("audience"):
        unique_aud: list[str] = []
        for a in aud_hits:
            a = a.strip()
            if a and a not in unique_aud:
                unique_aud.append(a)
        out["audience"] = "、".join(unique_aud[:3])

    style_hits = [s for s in _STYLE_KEYWORDS if s in text]
    if style_hits and not cur.get("style_refs"):
        out["style_refs"] = style_hits[:5]

    if not cur.get("avoid"):
        avoid_items: list[str] = []
        for m in re.finditer(r"(?:不要|避免|别|忌)\s*([\u4e00-\u9fa5A-Za-z0-9，,、；; ]+)", text):
            chunk = m.group(1).strip()
            for piece in _LIST_SPLIT_RE.split(chunk):
                piece = re.sub(r"^(?:不要|避免|别|忌)\s*", "", piece.strip())
                if piece and piece not in avoid_items:
                    avoid_items.append(piece)
        if avoid_items:
            out["avoid"] = avoid_items[:5]

    list_items = [s.strip() for s in _LIST_SPLIT_RE.split(text) if s.strip()]
    output_kw_set = {kw for kw, _ in _OUTPUT_KEYWORDS}
    pure_items = [
        it for it in list_items
        if it not in output_kw_set and not _AUDIENCE_RE.fullmatch(it)
    ]
    if (
        not cur.get("must_have")
        and "must_have" in missing
        and "must_have" not in out
        and len(pure_items) >= 2
        and not out.get("output_types")
    ):
        out["must_have"] = pure_items[:6]

    if not cur.get("product_name") and "product_name" in (missing or []):
        cleaned = text
        for a in aud_hits:
            cleaned = cleaned.replace(a, "")
        for kw in output_kw_set:
            cleaned = cleaned.replace(kw, "")
        for s in style_hits:
            cleaned = cleaned.replace(s, "")
        cleaned = cleaned.strip(" ，,。.!?；;、")
        if "product_name" not in out and cleaned and len(cleaned) <= 30 and not _AUDIENCE_RE.search(cleaned):
            if not _LIST_SPLIT_RE.search(cleaned):
                out["product_name"] = cleaned

    return out


def _safe_json_obj(text: str) -> dict:
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


class WorkspaceCopilot:
    """工作台 AI 控制台后端。"""

    def suggest_actions(self, node: dict, intent: dict | None = None) -> list[dict]:
        """同步规则降级 + 异步 LLM 增强的组合策略；这里直接返回规则建议。"""
        result_type = node.get("result_type", "main_image")
        status = node.get("status", "draft")
        has_variants = bool(node.get("variant_ids") or [])

        actions: list[dict] = []
        if status in {"draft", "failed"}:
            actions.append({
                "label": "生成 1 张变体",
                "intent": f"按当前 visual_spec 生成 1 张 {result_type}",
                "type": "generate",
            })
            actions.append({
                "label": "一次生成 3 张",
                "intent": "按相同 prompt 生成 3 张供比选",
                "type": "generate",
            })
        if has_variants:
            actions.append({
                "label": "保留角色，换场景",
                "intent": "保留人物与产品，把场景替换为居家阳光",
                "type": "replace_scene",
            })
            actions.append({
                "label": "文案更短",
                "intent": "把 copy 缩短到 8 字内，更具冲击力",
                "type": "copy_rewrite",
            })
        if result_type == "main_image":
            actions.append({
                "label": "强化左右对比",
                "intent": "把痛点/效果的对比差异放大，色彩更鲜明",
                "type": "refine",
            })
        elif result_type == "detail_module":
            actions.append({
                "label": "单屏一卖点",
                "intent": "移除次要信息，只保留核心卖点一屏表达",
                "type": "refine",
            })
        elif result_type == "video_shot":
            actions.append({
                "label": "缩短镜头时长",
                "intent": "把镜头压缩到 2 秒内，节奏更快",
                "type": "refine",
            })
        return actions[:5]

    async def suggest_actions_llm(self, node: dict, intent: dict | None = None) -> list[dict]:
        """LLM 增强版；失败自动降级到规则。"""
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return self.suggest_actions(node, intent)

        user = json.dumps({
            "node": {
                "role": node.get("role", ""),
                "visual_spec": node.get("visual_spec", ""),
                "copy_spec": node.get("copy_spec", ""),
                "result_type": node.get("result_type", ""),
                "status": node.get("status", ""),
                "has_variants": bool(node.get("variant_ids") or []),
            },
            "intent": intent or {},
        }, ensure_ascii=False)
        try:
            resp = await llm_router.achat(
                [LLMMessage(role="system", content=_ACTION_SYSTEM_PROMPT),
                 LLMMessage(role="user", content=user)],
                temperature=0.5, max_tokens=600,
            )
            actions = _safe_json_list(resp.content)
            if actions:
                return actions[:5]
        except Exception as exc:
            logger.warning("[Copilot] suggest_actions_llm 失败 %s", exc)
        return self.suggest_actions(node, intent)

    async def propose_edit(
        self, node: dict, user_prompt: str, intent: dict | None = None,
    ) -> dict:
        """把用户自然语言指令转成结构化执行提案。"""
        empty = {
            "summary": "", "prompt_delta": "", "copy_delta": "", "risk": "",
            "target_objects": [], "locked_objects": [], "steps": [], "risks": [],
        }
        if not user_prompt:
            return empty
        # 对象列表（命中的目标 / locked 剔除）
        objects = node.get("objects") or []
        locked_labels = [o.get("label", "") for o in objects if o.get("locked")]
        editable_labels = [o.get("label", "") for o in objects if not o.get("locked")]
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return self._fallback_proposal(user_prompt, editable_labels, locked_labels)

        context = json.dumps({
            "node": {
                "role": node.get("role", ""),
                "visual_spec": node.get("visual_spec", ""),
                "copy_spec": node.get("copy_spec", ""),
                "result_type": node.get("result_type", ""),
                "objects_editable": editable_labels,
                "objects_locked": locked_labels,
            },
            "intent": intent or {},
            "user_instruction": user_prompt,
        }, ensure_ascii=False)
        try:
            resp = await llm_router.achat(
                [LLMMessage(role="system", content=_PROPOSE_SYSTEM_PROMPT),
                 LLMMessage(role="user", content=context)],
                temperature=0.3, max_tokens=600,
            )
            obj = _safe_json_obj(resp.content)
            if obj.get("summary") or obj.get("prompt_delta"):
                target_objs = [str(x)[:40] for x in (obj.get("target_objects") or []) if x][:6]
                # 从 LLM 结果里剔除 locked 对象
                target_objs = [t for t in target_objs if t not in locked_labels]
                steps = [str(s)[:40] for s in (obj.get("steps") or []) if s][:4]
                risks = [str(r)[:60] for r in (obj.get("risks") or []) if r][:3]
                if not risks and obj.get("risk"):
                    risks = [str(obj.get("risk"))[:60]]
                return {
                    "summary": str(obj.get("summary", ""))[:60],
                    "prompt_delta": str(obj.get("prompt_delta", ""))[:500],
                    "copy_delta": str(obj.get("copy_delta", ""))[:200],
                    "risk": (risks[0] if risks else ""),
                    "target_objects": target_objs,
                    "locked_objects": locked_labels,
                    "steps": steps,
                    "risks": risks,
                }
        except Exception as exc:
            logger.warning("[Copilot] propose_edit 失败 %s", exc)

        return self._fallback_proposal(user_prompt, editable_labels, locked_labels)

    @staticmethod
    def _fallback_proposal(user_prompt: str, editable_labels: list[str], locked_labels: list[str]) -> dict:
        hit = [lbl for lbl in editable_labels if lbl and lbl[:2] in user_prompt]
        return {
            "summary": f"按指令调整：{user_prompt[:24]}",
            "prompt_delta": user_prompt,
            "copy_delta": "",
            "risk": "LLM 不可用/解析失败，已回退到原始指令注入",
            "target_objects": hit[:4],
            "locked_objects": locked_labels,
            "steps": [f"改写 prompt：{user_prompt[:28]}"],
            "risks": ["LLM 不可用/解析失败，回退到原始指令注入"],
        }

    async def propose_edit_v2(
        self, pack: Any, resolved: Any, user_prompt: str,
    ) -> dict:
        """基于 EditContextPack + ResolvedEditReference 输出 ProposalV2（兼容旧字段）。"""
        from apps.growth_lab.schemas.visual_workspace import (  # local import 避免循环
            EditContextPack,
            ResolvedEditReference,
        )
        if not isinstance(pack, EditContextPack):
            pack = EditContextPack.model_validate(pack)
        if not isinstance(resolved, ResolvedEditReference):
            resolved = ResolvedEditReference.model_validate(resolved)

        # 澄清分支：直接返回澄清，不出 steps
        if resolved.needs_clarification or resolved.resolution_confidence < 0.5:
            return self._clarification_proposal(pack, resolved, user_prompt)

        locked_ids = list(pack.selection_context.locked_object_ids or [])
        target_ids = [
            oid for oid in list(resolved.primary_targets) + list(resolved.secondary_targets)
            if oid and oid not in locked_ids
        ]
        if not user_prompt:
            return self._scene_fallback_v2(pack, resolved, "", target_ids, locked_ids)

        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return self._scene_fallback_v2(pack, resolved, user_prompt, target_ids, locked_ids)

        context_payload = {
            "pack": pack.model_dump(mode="json"),
            "resolved": resolved.model_dump(mode="json"),
            "user_instruction": user_prompt,
        }
        try:
            resp = await llm_router.achat(
                [
                    LLMMessage(role="system", content=_PROPOSE_SYSTEM_PROMPT_V2),
                    LLMMessage(role="user", content=json.dumps(context_payload, ensure_ascii=False)),
                ],
                temperature=0.25, max_tokens=900,
            )
            obj = _safe_json_obj(resp.content)
            if obj.get("summary") or obj.get("steps"):
                return self._normalize_proposal_v2(obj, pack, resolved, user_prompt, target_ids, locked_ids)
        except Exception as exc:
            logger.warning("[Copilot] propose_edit_v2 失败 %s", exc)
        return self._scene_fallback_v2(pack, resolved, user_prompt, target_ids, locked_ids)

    @staticmethod
    def _clarification_proposal(pack: Any, resolved: Any, user_prompt: str) -> dict:
        q = resolved.clarification_question or "这条指令指代的对象还不明确，能在画布上点一个对象，或告诉我是主体/背景/文案吗？"
        editable = [s.label for s in pack.visual_state.object_summaries if not s.locked][:5]
        return {
            # v2 字段
            "summary": "需要先明确指代对象",
            "interpretation_basis": [f"原指令：{user_prompt[:40]}"] if user_prompt else [],
            "resolved_reference": resolved.model_dump(mode="json"),
            "target_objects": [],
            "locked_objects": list(pack.selection_context.locked_object_ids or []),
            "preserve_rules": [],
            "steps": [],
            "risks": [],
            "requires_confirmation": True,
            "keep_slot_role": True,
            "needs_clarification": True,
            "clarification_question": q,
            "suggested_objects": editable,
            # v1 兼容字段
            "prompt_delta": "",
            "copy_delta": "",
            "risk": "",
        }

    @staticmethod
    def _scene_fallback_v2(
        pack: Any, resolved: Any, user_prompt: str,
        target_ids: list[str], locked_ids: list[str],
    ) -> dict:
        """规则降级：把用户指令作为一次 global_refine 或 regenerate_object 步骤。"""
        from apps.growth_lab.schemas.visual_workspace import ResolvedEditReference  # noqa
        action_type = "regenerate_object" if target_ids else "global_refine"
        short = user_prompt.strip()[:40]
        summary = (
            f"对选中对象执行：{short}" if target_ids else (
                f"按整图调整：{short}" if short else "等待指令"
            )
        )
        steps = [{
            "action_type": action_type,
            "target_object_ids": target_ids,
            "params": {"prompt": user_prompt[:300]},
            "strength": "moderate",
            "reason": "LLM 不可用时的规则降级",
        }] if user_prompt else []
        preserve_rules: list[str] = []
        if pack.template_context and pack.template_context.template_constraints:
            preserve_rules.extend(pack.template_context.template_constraints[:3])
        if pack.strategy_context and pack.strategy_context.brand_rules:
            preserve_rules.extend(pack.strategy_context.brand_rules[:2])
        return {
            "summary": summary,
            "interpretation_basis": [
                f"primary={resolved.primary_targets}",
                f"scope={resolved.scope}",
            ],
            "resolved_reference": resolved.model_dump(mode="json"),
            "target_objects": target_ids,
            "locked_objects": locked_ids,
            "preserve_rules": preserve_rules,
            "steps": steps,
            "risks": [],
            "requires_confirmation": True,
            "keep_slot_role": True,
            "needs_clarification": False,
            "clarification_question": None,
            "prompt_delta": user_prompt[:500],
            "copy_delta": "",
            "risk": "",
        }

    @staticmethod
    def _normalize_proposal_v2(
        obj: dict, pack: Any, resolved: Any, user_prompt: str,
        target_ids: list[str], locked_ids: list[str],
    ) -> dict:
        # steps 规范化
        steps_out: list[dict] = []
        for s in (obj.get("steps") or [])[:6]:
            if not isinstance(s, dict):
                continue
            steps_out.append({
                "action_type": str(s.get("action_type") or "global_refine")[:40],
                "target_object_ids": [str(x) for x in (s.get("target_object_ids") or []) if x][:6],
                "params": s.get("params") or {},
                "strength": s.get("strength") or "moderate",
                "reason": str(s.get("reason") or "")[:120],
            })
        llm_target = [t for t in (obj.get("target_objects") or []) if t and t not in locked_ids]
        final_targets = llm_target[:6] or target_ids
        return {
            "summary": str(obj.get("summary", "")).strip()[:80],
            "interpretation_basis": [str(x)[:120] for x in (obj.get("interpretation_basis") or [])][:4],
            "resolved_reference": obj.get("resolved_reference") or resolved.model_dump(mode="json"),
            "target_objects": final_targets,
            "locked_objects": list({*locked_ids, *(obj.get("locked_objects") or [])}),
            "preserve_rules": [str(x)[:120] for x in (obj.get("preserve_rules") or [])][:4],
            "steps": steps_out,
            "risks": [str(x)[:120] for x in (obj.get("risks") or [])][:3],
            "requires_confirmation": bool(obj.get("requires_confirmation", True)),
            "keep_slot_role": bool(obj.get("keep_slot_role", True)),
            "needs_clarification": False,
            "clarification_question": None,
            # v1 兼容
            "prompt_delta": str(obj.get("prompt_delta") or user_prompt or "")[:500],
            "copy_delta": str(obj.get("copy_delta") or "")[:200],
            "risk": "",
        }

    async def onboarding_chat(
        self,
        history: list[dict] | None = None,
        draft_intent: dict | None = None,
    ) -> dict:
        """对话式收集意图 → 渐进补齐字段，满足阈值即 ready_to_compile。

        入参：
            history: [{role, content}, ...]  前端累积对话
            draft_intent: {product_name, audience, output_types, style_refs,
                           must_have, avoid, ...}
        返回（OnboardingResult dict）：
            {draft_intent, next_question, assistant_message,
             ready_to_compile, missing_fields, suggestions}
        """
        from apps.growth_lab.schemas.visual_workspace import IntentContext  # 局部 import

        hist = list(history or [])
        cur = dict(draft_intent or {})
        # 字段优先级（从高到低）
        field_priority = [
            ("output_types", "想先产出哪种素材？主图 / 详情 / 视频分镜 / 买家秀 / 竞品对标（可多选）"),
            ("product_name", "产品或品牌是什么？（例：JOYRUQO 氨基酸洁面乳）"),
            ("audience", "目标人群是谁？（例：25-30 岁敏感肌女性 / 职场男性 / 宝妈…）"),
            ("must_have", "必须呈现的核心卖点有哪些？（逗号分隔）"),
            ("style_refs", "希望整体风格是什么？（例：极简高端 / 日系清新 / 港风复古）"),
        ]

        def _missing_key_fields() -> list[str]:
            out: list[str] = []
            for key, _ in field_priority:
                v = cur.get(key)
                if not v:
                    out.append(key)
                elif isinstance(v, list) and not v:
                    out.append(key)
            return out

        # 先尝试让 LLM 抽取 / 反问
        assistant_msg = ""
        next_q: str | None = None
        suggestions: list[str] = []
        llm_ok = False
        obj: dict = {}
        raw_resp = ""
        last_user_text = ""
        for turn in reversed(hist):
            if (turn or {}).get("role") == "user":
                last_user_text = str(turn.get("content") or "").strip()
                break

        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router

            system = (
                "你是视觉工作台的 onboarding agent，帮操盘手用对话补齐一次编译所需意图。\n"
                "强制规则：\n"
                "1) 必须先把 history 最后一条 user 消息抽取并归属到 draft_intent 对应字段，再决定 next_question；\n"
                "   - 输出类型关键词：'主图'→main_image，'详情'→detail，'视频/分镜'→video_shots，'买家秀'→buyer_show，'竞品'→competitor；\n"
                "   - 含数字+岁 / 男士 / 女士 / 宝妈 / 学生 / 职场 等 → audience；\n"
                "   - 含'极简/日系/港风/复古/高端/暗调/明亮' 等 → style_refs；\n"
                "   - '不要 / 避免 / 别' 后的内容 → avoid；\n"
                "   - 短名词短语（≤30 字、无人群词）→ product_name；\n"
                "   - 用顿号/逗号/分号切分得到列表。\n"
                "2) 已存在的字段不要清空也不要覆盖；只补齐空值。\n"
                "3) next_question 永远问当前 missing_fields 的第一个；若已 ready 则置 null。\n"
                "4) ready_to_compile：output_types 非空 且 product_name/audience/must_have 中至少 2 项有值。\n"
                "5) 输出严格单个 JSON 对象，不要 code fence、不要解释、不要前后缀文本。\n"
                "JSON schema：\n"
                "{\n"
                "  \"draft_intent\": {\"product_name\": str, \"audience\": str, \"output_types\": [str],\n"
                "                    \"style_refs\": [str], \"must_have\": [str], \"avoid\": [str]},\n"
                "  \"assistant_message\": \"一句话回应（10-30 字）\",\n"
                "  \"next_question\": \"问 missing 第一个字段，或 null\",\n"
                "  \"ready_to_compile\": bool,\n"
                "  \"missing_fields\": [str],\n"
                "  \"suggestions\": [str]\n"
                "}\n"
                "示例：\n"
                "USER 最后一句='主图，男士洁面乳' 且 draft_intent 为空 →\n"
                "{\"draft_intent\":{\"output_types\":[\"main_image\"],\"product_name\":\"男士洁面乳\"},"
                "\"assistant_message\":\"已记录主图与产品名\",\"next_question\":\"目标人群是谁？\","
                "\"ready_to_compile\":false,\"missing_fields\":[\"audience\",\"must_have\",\"style_refs\"],"
                "\"suggestions\":[\"25-30 岁男士\",\"敏感肌\"]}"
            )
            user_payload = {
                "draft_intent": cur,
                "history": hist[-12:],
                "field_priority": [k for k, _ in field_priority],
                "current_missing": _missing_key_fields(),
                "latest_user_message": last_user_text,
            }
            resp = await llm_router.achat(
                [LLMMessage(role="system", content=system),
                 LLMMessage(role="user", content=json.dumps(user_payload, ensure_ascii=False))],
                temperature=0.2, max_tokens=600,
            )
            raw_resp = (resp.content or "")[:400]
            obj = _safe_json_obj(resp.content)
            if obj:
                di = obj.get("draft_intent") or {}
                if isinstance(di, dict):
                    for k, v in di.items():
                        if v and not cur.get(k):
                            cur[k] = v
                assistant_msg = str(obj.get("assistant_message") or "")[:400]
                next_q = obj.get("next_question")
                if next_q is not None:
                    next_q = str(next_q)[:200] or None
                suggestions = [str(s)[:60] for s in (obj.get("suggestions") or [])][:5]
                llm_ok = True
            else:
                logger.info("[Copilot] onboarding LLM 未返回 JSON，raw=%s", raw_resp)
        except ImportError:
            logger.info("[Copilot] onboarding LLM 不可用（ImportError），走规则兜底")
        except Exception as exc:
            logger.warning("[Copilot] onboarding_chat LLM 失败 %s", exc)

        # 规则 NLU 兜底：哪怕 LLM 抽取了部分字段，也再跑一次启发式补缺
        extracted = _heuristic_extract(last_user_text, cur, _missing_key_fields())
        if extracted:
            for k, v in extracted.items():
                if not cur.get(k):
                    cur[k] = v
                elif isinstance(cur.get(k), list) and isinstance(v, list):
                    merged = list(cur[k])
                    for item in v:
                        if item and item not in merged:
                            merged.append(item)
                    cur[k] = merged

        missing = _missing_key_fields()
        # 兜底问句：LLM 没给或与缺失不符时，按优先级补一个
        if not next_q:
            for key, prompt in field_priority:
                if key in missing:
                    next_q = prompt
                    break
        if not assistant_msg:
            if extracted:
                labels = "、".join(_FIELD_LABEL.get(k, k) for k in extracted.keys())
                assistant_msg = f"收到，已记录{labels}。"
            elif last_user_text:
                assistant_msg = "收到～继续补充下面这条就好。"
            else:
                assistant_msg = "我们一步步来。"

        # ready 判定：output_types 必须有；且 product/audience/must_have 至少补了 2 项
        has_outputs = bool(cur.get("output_types"))
        filled_soft = sum(1 for k in ("product_name", "audience", "must_have") if cur.get(k))
        ready = bool(obj.get("ready_to_compile")) if llm_ok and obj else False
        if not ready:
            ready = has_outputs and filled_soft >= 2

        # 标准化 IntentContext
        try:
            normalized = IntentContext.model_validate(cur).model_dump(mode="json")
        except Exception:
            normalized = cur

        return {
            "draft_intent": normalized,
            "assistant_message": assistant_msg,
            "next_question": None if ready else next_q,
            "ready_to_compile": ready,
            "missing_fields": missing,
            "suggestions": suggestions,
        }

    def explain_lineage(self, node: dict) -> list[dict]:
        """四来源溯源（intent / template / brand / competitor），供右栏高亮。"""
        items: list[dict] = []
        for ref in node.get("intent_ref_fields", []) or []:
            items.append({"source": "意图", "content": ref})
        if node.get("template_slot_ref"):
            items.append({"source": "模板", "content": node["template_slot_ref"]})
        for r in (node.get("brand_rule_refs") or [])[:4]:
            items.append({"source": "品牌", "content": r})
        for ref in (node.get("competitor_ref_ids") or [])[:3]:
            items.append({"source": "竞品", "content": ref})
        return items


_instance: WorkspaceCopilot | None = None


def get_workspace_copilot() -> WorkspaceCopilot:
    global _instance
    if _instance is None:
        _instance = WorkspaceCopilot()
    return _instance
