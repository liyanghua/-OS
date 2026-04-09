"""DiscussionOrchestrator：多 Agent 阶段讨论协调器。

用户在某阶段提问时，自动唤起多个相关 Agent 讨论，
每个 Agent 看到用户问题 + 当前对象 + 前面 Agent 发言，
最终由总调度综合结论。
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.agents.base import AgentContext, AgentMessage, AgentResult
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry

logger = logging.getLogger(__name__)


STAGE_DISCUSSION_ROLES: dict[str, list[str]] = {
    "card": ["trend_analyst", "brief_synthesizer"],
    "brief": ["trend_analyst", "brief_synthesizer", "strategy_director"],
    "match": ["template_planner", "strategy_director", "visual_director"],
    "strategy": ["strategy_director", "visual_director", "brief_synthesizer"],
    "content": ["visual_director", "asset_producer", "strategy_director"],
}

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "trend_analyst": "趋势分析师",
    "brief_synthesizer": "Brief 编译师",
    "template_planner": "模板策划师",
    "strategy_director": "策略总监",
    "visual_director": "视觉总监",
    "asset_producer": "资产制作人",
}


class DiscussionRound(BaseModel):
    """多 Agent 讨论记录。"""
    round_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage: str = ""
    topic: str = ""
    participants: list[str] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    consensus: str | None = None
    proposed_updates: dict[str, Any] = Field(default_factory=dict)
    overall_score: float = 0.0
    status: Literal["discussing", "concluded", "cancelled"] = "discussing"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiscussionOrchestrator:
    """Orchestrate multi-agent discussions for a given stage and question."""

    def __init__(self):
        self._memory = AgentMemory()

    def discuss(self, opportunity_id: str, stage: str, user_question: str,
                context: AgentContext | None = None,
                on_message: Any = None) -> DiscussionRound:
        """Run a multi-agent discussion round.

        Args:
            opportunity_id: The opportunity being discussed
            stage: Current pipeline stage (card/brief/match/strategy/content)
            user_question: The user's question
            context: Optional agent context with current objects
            on_message: Optional callback(AgentMessage) for real-time streaming
        """
        participants = STAGE_DISCUSSION_ROLES.get(stage, ["trend_analyst", "brief_synthesizer"])

        discussion = DiscussionRound(
            opportunity_id=opportunity_id,
            stage=stage,
            topic=user_question,
            participants=participants,
        )

        user_msg = AgentMessage(
            role="user",
            content=user_question,
            metadata={"stage": stage},
        )
        discussion.messages.append(user_msg)
        if on_message:
            on_message(user_msg)

        object_context = self._build_object_context(stage, context)
        memory_context = self._get_memory_context(opportunity_id)

        prior_statements: list[str] = []

        for agent_role in participants:
            agent_name = AGENT_DISPLAY_NAMES.get(agent_role, agent_role)

            agent_response = self._get_agent_opinion(
                agent_role=agent_role,
                agent_name=agent_name,
                user_question=user_question,
                stage=stage,
                object_context=object_context,
                memory_context=memory_context,
                prior_statements=prior_statements,
            )

            msg = AgentMessage(
                role="agent",
                content=agent_response,
                agent_role=agent_role,
                metadata={"agent_name": agent_name, "stage": stage},
            )
            discussion.messages.append(msg)
            prior_statements.append(f"[{agent_name}]: {agent_response}")
            if on_message:
                on_message(msg)

        consensus, proposed_updates = self._synthesize_consensus(
            user_question, stage, prior_statements, object_context
        )
        discussion.consensus = consensus
        discussion.proposed_updates = proposed_updates
        discussion.status = "concluded"

        consensus_msg = AgentMessage(
            role="system",
            content=f"[共识] {consensus}",
            agent_role="lead_agent",
            metadata={"type": "consensus", "proposed_updates": proposed_updates},
        )
        discussion.messages.append(consensus_msg)
        if on_message:
            on_message(consensus_msg)

        self._memory.store(
            MemoryEntry(
                opportunity_id=opportunity_id,
                category="discussion_consensus",
                content=f"[{stage}] Q: {user_question[:100]} → {consensus[:200]}",
                source_agent="discussion_orchestrator",
                relevance_score=0.8,
                tags=[stage, "discussion"],
            )
        )

        return discussion

    def _get_agent_opinion(self, *, agent_role: str, agent_name: str,
                           user_question: str, stage: str,
                           object_context: str, memory_context: str,
                           prior_statements: list[str]) -> str:
        """Get a single agent's opinion on the topic."""
        if not llm_router.is_any_available():
            return self._rule_based_opinion(agent_role, user_question, stage)

        prior_text = "\n".join(prior_statements) if prior_statements else "你是第一个发言的。"

        system = f"""你是「{agent_name}」，一个专业的内容策划 Agent。
当前讨论阶段：{stage}
你的职责是基于你的专业视角（{agent_role}），针对用户的问题给出有建设性的观点。
请参考前面 Agent 的发言，避免重复，补充新角度。回答要简洁专业（3-5句话）。"""

        user_msg = f"""用户问题：{user_question}

当前对象状态：
{object_context}

相关记忆：
{memory_context}

前面 Agent 发言：
{prior_text}

请给出你的专业观点："""

        resp = llm_router.chat([
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user_msg),
        ], temperature=0.4, max_tokens=600)

        return resp.content if resp.content else self._rule_based_opinion(agent_role, user_question, stage)

    def _rule_based_opinion(self, agent_role: str, question: str, stage: str) -> str:
        """Fallback rule-based opinion when LLM is unavailable."""
        opinions = {
            "trend_analyst": f"从趋势角度看，「{question[:30]}」需要结合当前市场热点和竞品动态来分析。建议关注数据支撑度。",
            "brief_synthesizer": f"从策划角度看，这个问题的核心在于目标用户和场景的匹配度。建议明确用户画像后再推进。",
            "template_planner": f"从模板角度看，需要确保选择的模板风格与内容方向一致。建议对比 Top-3 候选的差异。",
            "strategy_director": f"从策略角度看，关键是找到差异化的内容角度。建议围绕核心卖点构建独特叙事。",
            "visual_director": f"从视觉角度看，图片方案要与内容调性统一。建议减少广告感，增强场景真实感。",
            "asset_producer": f"从产出角度看，需要确保标题有吸引力、正文有种草力。建议准备 2-3 个标题变体。",
        }
        return opinions.get(agent_role, f"作为 {agent_role}，我建议从专业角度审视此问题。")

    def _synthesize_consensus(self, question: str, stage: str,
                              statements: list[str], object_context: str) -> tuple[str, dict]:
        """Synthesize a consensus from all agent statements."""
        if not llm_router.is_any_available():
            summary = "综合各方意见：" + "；".join(s.split("]: ", 1)[-1][:50] for s in statements)
            return summary, {}

        all_text = "\n".join(statements)
        resp = llm_router.chat_json([
            LLMMessage(role="system", content="""你是内容策划总调度。请综合所有 Agent 观点，给出：
1. 共识结论（consensus）
2. 建议更新的字段（proposed_updates，dict 格式，key 为字段名，value 为建议值）

返回 JSON：{"consensus": "...", "proposed_updates": {"field": "value", ...}}"""),
            LLMMessage(role="user", content=f"阶段：{stage}\n问题：{question}\n对象状态：{object_context}\n\n各 Agent 观点：\n{all_text}"),
        ], temperature=0.3, max_tokens=800)

        consensus = resp.get("consensus", "综合各方意见后，建议进一步细化方向。")
        updates = resp.get("proposed_updates", {})
        if not isinstance(updates, dict):
            updates = {}
        return consensus, updates

    def _build_object_context(self, stage: str, context: AgentContext | None) -> str:
        """Build a text summary of current objects for discussion context."""
        if context is None:
            return "无对象上下文"
        parts = []
        if context.brief:
            b = context.brief
            title = getattr(b, 'opportunity_title', '') if hasattr(b, 'opportunity_title') else (b.get('opportunity_title', '') if isinstance(b, dict) else '')
            if title:
                parts.append(f"Brief标题: {title}")
        if context.strategy:
            parts.append("策略: 已生成")
        if context.plan:
            parts.append("NotePlan: 已生成")
        if context.match_result:
            parts.append("模板匹配: 已完成")
        return "\n".join(parts) if parts else "暂无对象"

    def _get_memory_context(self, opportunity_id: str) -> str:
        """Retrieve relevant memories for discussion context."""
        entries = self._memory.recall(opportunity_id=opportunity_id, limit=5)
        if not entries:
            return "无历史记忆"
        return "\n".join(f"- [{e.category}] {e.content[:80]}" for e in entries)
