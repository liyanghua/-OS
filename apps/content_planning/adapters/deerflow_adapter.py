"""DeerFlow Adapter：借鉴 DeerFlow 的编排/Skills/Memory 模式。"""
from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.agents.memory import AgentMemory
from apps.content_planning.agents.skill_registry import skill_registry

logger = logging.getLogger(__name__)

_ROUTING_SYSTEM_PROMPT = """你是内容策划 AI 总调度。你的任务是分析用户意图，决定委派哪些 Agent 来处理。

可用 Agent：
{agent_descriptions}

当前阶段：{stage}
对象摘要：{object_summary}
相关记忆：{memory_context}
可用技能：{skill_context}

根据用户消息，返回 JSON：
{{
  "target_agents": ["agent_role_1", ...],
  "reasoning": "为什么选择这些 Agent",
  "subtasks": ["子任务1", "子任务2", ...]
}}
只返回 JSON，不要其他内容。"""

AGENT_DESCRIPTIONS = {
    "trend_analyst": "趋势分析师：分析机会卡、评估市场趋势、竞品对比、判断优先级",
    "brief_synthesizer": "Brief 编译师：将机会卡编译成策划 Brief，确定目标用户/场景/方向",
    "template_planner": "模板策划师：为 Brief 匹配最佳内容模板",
    "strategy_director": "策略总监：生成改写策略，确定内容调性和差异化方向",
    "visual_director": "视觉总监：规划图片方案，生成图位执行 Brief",
    "asset_producer": "资产制作人：生成标题/正文/组装资产包",
}


class DeerFlowAdapter:
    """Adapts DeerFlow concepts for our content planning Agent layer."""

    def __init__(self):
        self._memory = AgentMemory()

    def route_with_llm(self, user_message: str, stage: str,
                       available_agents: list[dict] | None = None,
                       memory_context: str = "",
                       object_summary: str = "") -> dict:
        """LLM-driven intent routing."""
        agent_desc = "\n".join(
            f"- {role}: {desc}" for role, desc in AGENT_DESCRIPTIONS.items()
        )

        skills = skill_registry.list_skills()
        skill_ctx = ", ".join(s.skill_name for s in skills[:10]) if skills else "无"

        prompt = _ROUTING_SYSTEM_PROMPT.format(
            agent_descriptions=agent_desc,
            stage=stage or "未知",
            object_summary=object_summary or "无",
            memory_context=memory_context or "无",
            skill_context=skill_ctx,
        )

        resp = llm_router.chat_json([
            LLMMessage(role="system", content=prompt),
            LLMMessage(role="user", content=user_message),
        ], temperature=0.2, max_tokens=500)

        if not resp or "target_agents" not in resp:
            return {"target_agents": [], "reasoning": "LLM routing failed", "subtasks": []}
        return resp

    def synthesize_results(self, results: list[dict]) -> dict:
        """Merge multiple sub-agent results into a coherent output."""
        if not results:
            return {"explanation": "", "confidence": 0.0, "suggestions": []}
        if len(results) == 1:
            return results[0]

        explanations = []
        all_suggestions: list[Any] = []
        total_confidence = 0.0
        for r in results:
            if r.get("explanation"):
                explanations.append(f"[{r.get('agent_role', '?')}] {r['explanation']}")
            all_suggestions.extend(r.get("suggestions", []))
            total_confidence += r.get("confidence", 0.5)

        system = "你是内容策划 AI 总调度。请综合以下多个 Agent 的分析结果，给出统一结论。"
        user_msg = "\n\n".join(explanations)
        resp = llm_router.chat([
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=f"请综合以下分析：\n{user_msg}\n\n给出简洁的综合结论（2-3句话）。"),
        ], temperature=0.3, max_tokens=500)

        synthesis = resp.content if resp.content else "\n".join(explanations)

        return {
            "explanation": synthesis,
            "confidence": total_confidence / len(results),
            "suggestions": all_suggestions[:6],
            "source_agents": [r.get("agent_role", "") for r in results],
        }

    def load_skill_into_prompt(self, skill_id: str) -> str:
        """Progressive skill loading: returns prompt fragment for injection."""
        skill = skill_registry.get(skill_id)
        if skill is None:
            return ""
        parts = [f"[技能: {skill.skill_name}]", skill.description]
        if skill.workflow_steps:
            parts.append("工作流: " + " → ".join(skill.workflow_steps))
        if skill.prompt_fragment:
            parts.append(skill.prompt_fragment)
        return "\n".join(parts)

    def build_object_summary(self, context: Any) -> str:
        """Build a concise object summary for LLM routing context."""
        parts = []
        if hasattr(context, 'brief') and context.brief:
            brief = context.brief
            title = getattr(brief, 'opportunity_title', '') or ''
            if isinstance(brief, dict):
                title = brief.get('opportunity_title', '')
            if title:
                parts.append(f"Brief: {title}")
        if hasattr(context, 'strategy') and context.strategy:
            parts.append("Strategy: 已生成")
        if hasattr(context, 'plan') and context.plan:
            parts.append("Plan: 已生成")
        if hasattr(context, 'asset_bundle') and context.asset_bundle:
            parts.append("AssetBundle: 已组装")
        return "; ".join(parts) if parts else "空"

    def recall_relevant_memory(self, opportunity_id: str, query: str = "", limit: int = 5) -> str:
        """Retrieve relevant memories for context injection."""
        entries = self._memory.recall(opportunity_id=opportunity_id, limit=limit)
        if not entries and query:
            entries = self._memory.search(query, limit=limit)
        if not entries:
            return ""
        return "\n".join(f"- [{e.category}] {e.content[:100]}" for e in entries[:limit])
