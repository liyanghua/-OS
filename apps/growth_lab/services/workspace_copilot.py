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
你是视觉工作台的编辑协作 AI。根据节点上下文和用户指令，给出一个"结构化执行提案"。
输出严格 JSON：{"summary": "一句话总结（≤30字）", "prompt_delta": "对原 prompt 的增量/改写", "copy_delta": "对 copy 的调整或空字符串", "risk": "风险提醒或空字符串"}
只输出 JSON，不要 code fence。
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
        if not user_prompt:
            return {"summary": "", "prompt_delta": "", "copy_delta": "", "risk": ""}
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return {
                "summary": f"按指令：{user_prompt[:30]}",
                "prompt_delta": user_prompt,
                "copy_delta": "",
                "risk": "LLM 不可用，已降级为纯文本注入",
            }

        context = json.dumps({
            "node": {
                "role": node.get("role", ""),
                "visual_spec": node.get("visual_spec", ""),
                "copy_spec": node.get("copy_spec", ""),
                "result_type": node.get("result_type", ""),
            },
            "intent": intent or {},
            "user_instruction": user_prompt,
        }, ensure_ascii=False)
        try:
            resp = await llm_router.achat(
                [LLMMessage(role="system", content=_PROPOSE_SYSTEM_PROMPT),
                 LLMMessage(role="user", content=context)],
                temperature=0.3, max_tokens=500,
            )
            obj = _safe_json_obj(resp.content)
            if obj.get("summary") or obj.get("prompt_delta"):
                return {
                    "summary": str(obj.get("summary", ""))[:60],
                    "prompt_delta": str(obj.get("prompt_delta", ""))[:500],
                    "copy_delta": str(obj.get("copy_delta", ""))[:200],
                    "risk": str(obj.get("risk", ""))[:120],
                }
        except Exception as exc:
            logger.warning("[Copilot] propose_edit 失败 %s", exc)

        return {
            "summary": f"按指令调整：{user_prompt[:24]}",
            "prompt_delta": user_prompt,
            "copy_delta": "",
            "risk": "LLM 解析失败，已回退到原始指令注入",
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
