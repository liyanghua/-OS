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
