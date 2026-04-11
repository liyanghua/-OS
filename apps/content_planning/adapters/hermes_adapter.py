"""Hermes Adapter：借鉴 Hermes Agent 的 Learning Loop / 轨迹压缩 / Sub-Agent 并行。

参考 third_party/hermes-agent/ 的以下核心理念：
- Learning Loop：从经验自动提取/改进 Skill
- Memory Nudge：Agent 主动提醒固化有价值的决策
- Trajectory Compression：保首尾、摘要中间，控制上下文窗口
- Sub-Agent Isolation：子代理独立工具集、深度限制、不共享父 memory
"""
from __future__ import annotations

import json
import logging
from typing import Any

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry
from apps.content_planning.agents.skill_registry import SkillDefinition, skill_registry

logger = logging.getLogger(__name__)


class HermesAdapter:
    """Adapts Hermes Agent concepts for our content planning Agent layer."""

    def __init__(self):
        self._memory = AgentMemory()

    def compress_trajectory(self, messages: list[dict], max_tokens: int = 4000) -> list[dict]:
        """Compress conversation trajectory, keeping head/tail and summarizing middle.

        Strategy: keep first 2 messages, last 3 messages, summarize the rest via LLM.
        If total is <= 7 messages, return as-is.
        """
        if len(messages) <= 7:
            return messages

        head = messages[:2]
        tail = messages[-3:]
        middle = messages[2:-3]

        if not llm_router.is_any_available() or not middle:
            mid_summary = "; ".join(
                f"[{m.get('role', '?')}] {m.get('content', '')[:50]}..." for m in middle[:5]
            )
            compressed = [{"role": "system", "content": f"[对话摘要] {mid_summary}"}]
            return head + compressed + tail

        middle_text = "\n".join(
            f"[{m.get('role', '?')}]: {m.get('content', '')}" for m in middle
        )
        resp = llm_router.chat([
            LLMMessage(role="system", content="请将以下对话历史压缩为简洁摘要（保留关键决策和结论）："),
            LLMMessage(role="user", content=middle_text),
        ], temperature=0.2, max_tokens=500)

        summary = resp.content if resp.content else middle_text[:200]
        compressed_msg = {"role": "system", "content": f"[对话摘要] {summary}"}
        return head + [compressed_msg] + tail

    def extract_skill_from_experience(self, discussion_round: dict) -> SkillDefinition | None:
        """Learning loop: extract a reusable skill from a high-quality discussion."""
        overall_score = discussion_round.get("overall_score", 0.0)
        if overall_score < 0.7:
            return None

        topic = discussion_round.get("topic", "")
        consensus = discussion_round.get("consensus", "")
        stage = discussion_round.get("stage", "")
        participants = discussion_round.get("participants", [])

        if not (topic and consensus):
            return None

        if not llm_router.is_any_available():
            skill = SkillDefinition(
                skill_id=f"learned_{discussion_round.get('round_id', 'x')[:8]}",
                skill_name=f"经验技能: {topic[:30]}",
                description=f"从讨论中提取: {consensus[:100]}",
                trigger_keywords=[w for w in topic.split()[:3] if len(w) > 1],
                agent_role=participants[0] if participants else "trend_analyst",
                workflow_steps=["回顾讨论共识", "应用到当前场景"],
                category="learned",
                enabled=True,
            )
            skill_registry.register(skill)
            return skill

        resp = llm_router.chat_json([
            LLMMessage(role="system", content="从以下成功的 Agent 讨论中提取可复用技能。返回 JSON：{\"skill_name\": \"...\", \"description\": \"...\", \"trigger_keywords\": [...], \"workflow_steps\": [...]}"),
            LLMMessage(role="user", content=f"话题：{topic}\n共识：{consensus}\n阶段：{stage}\n参与者：{', '.join(participants)}"),
        ], temperature=0.2, max_tokens=500)

        if not resp or "skill_name" not in resp:
            return None

        skill = SkillDefinition(
            skill_id=f"learned_{discussion_round.get('round_id', 'x')[:8]}",
            skill_name=resp.get("skill_name", ""),
            description=resp.get("description", ""),
            trigger_keywords=resp.get("trigger_keywords", []),
            agent_role=participants[0] if participants else "trend_analyst",
            workflow_steps=resp.get("workflow_steps", []),
            category="learned",
            enabled=True,
        )
        skill_registry.register(skill)
        return skill

    def memory_nudge(self, opportunity_id: str, context: str) -> str | None:
        """Suggest the user persist a valuable decision rationale."""
        if not llm_router.is_any_available():
            return None

        resp = llm_router.chat([
            LLMMessage(role="system", content="你是内容策划 AI 助手。判断以下决策过程中是否有值得记录的经验。如有，给出简短建议（一句话）。如无，返回空字符串。"),
            LLMMessage(role="user", content=context),
        ], temperature=0.2, max_tokens=200)

        nudge = resp.content.strip() if resp.content else ""
        if nudge and len(nudge) > 5:
            self._memory.store(MemoryEntry(
                opportunity_id=opportunity_id,
                category="nudge",
                content=nudge,
                source_agent="hermes_adapter",
            ))
            return nudge
        return None

    def write_lesson(self, opportunity_id: str, stage: str, lesson: str, score: float) -> None:
        """Write a lesson learned to memory from a low-scoring action."""
        if score >= 0.5:
            return
        self._memory.store(MemoryEntry(
            opportunity_id=opportunity_id,
            category="lesson_learned",
            content=f"[{stage}] {lesson}",
            source_agent="hermes_learning_loop",
            relevance_score=1.0 - score,
            tags=[stage, "lesson"],
        ))

    # ── Learning Loop Hooks (V2) ──

    def on_proposal_adopted(
        self,
        opportunity_id: str,
        stage: str,
        consensus: str,
        proposed_updates: dict[str, Any],
        *,
        brand_id: str = "",
    ) -> None:
        """When a Council proposal is adopted, extract strategy pattern → project memory."""
        pattern_content = f"[adopted|{stage}] {consensus[:300]}"
        if proposed_updates:
            keys = list(proposed_updates.keys())[:5]
            pattern_content += f" | fields: {', '.join(keys)}"
        self._memory.store_project_consensus(
            opportunity_id, pattern_content, stage, brand_id=brand_id,
        )
        self._memory.store(MemoryEntry(
            opportunity_id=opportunity_id,
            brand_id=brand_id,
            category="adopted_strategy_pattern",
            content=pattern_content,
            source_agent="learning_loop",
            relevance_score=0.9,
            tags=[stage, "adopted"],
        ))
        logger.info("Learning loop: adopted proposal stored for opp=%s stage=%s", opportunity_id, stage)

    def on_low_score(
        self,
        opportunity_id: str,
        stage: str,
        score: float,
        dimension_details: list[dict[str, Any]] | None = None,
        *,
        brand_id: str = "",
    ) -> None:
        """When stage score < threshold, auto-write lesson_learned to project memory."""
        if score >= 0.4:
            return
        lesson = f"环节 {stage} 评分较低 ({score:.2f})，需优化。"
        if dimension_details:
            worst = min(dimension_details, key=lambda d: d.get("score", 1.0))
            lesson += f" 最弱维度: {worst.get('name_zh', worst.get('name', '?'))}"
        self._memory.store(MemoryEntry(
            opportunity_id=opportunity_id,
            brand_id=brand_id,
            category="lesson_learned",
            content=f"[scoring] {lesson}",
            source_agent="learning_loop",
            relevance_score=1.0 - score,
            tags=[stage, "low_score"],
        ))
        self._memory.store(MemoryEntry(
            opportunity_id=opportunity_id,
            brand_id=brand_id,
            category="scoring_shortfall",
            content=lesson,
            source_agent="learning_loop",
            relevance_score=score,
            tags=[dimension_details[0].get("name", stage) if dimension_details else stage],
        ))

    def track_skill_execution(self, skill_id: str, success: bool) -> None:
        """Track skill execution success/failure; flag low-success skills for prompt updates."""
        skill = skill_registry.get(skill_id)
        if skill is None:
            return
        if success:
            skill.success_count += 1
        else:
            skill.fail_count += 1
        if skill.success_rate < 0.3 and (skill.success_count + skill.fail_count) >= 5:
            logger.warning(
                "Skill %s has low success rate %.1f%% — flagging for prompt version update",
                skill_id, skill.success_rate * 100,
            )
            skill.last_updated = "needs_prompt_update"
