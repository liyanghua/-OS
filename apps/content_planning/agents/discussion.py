"""DiscussionOrchestrator：多 Agent 阶段讨论协调器。

用户在某阶段提问时，自动唤起多个相关 Agent 讨论，
每个 Agent 看到用户问题 + 当前对象 + Brief 快照（可写字段白名单），
最终由总调度综合结论，并产出结构化 Advisory Session 字段。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Literal, cast

from pydantic import BaseModel, Field

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.agents.base import AgentContext, AgentMessage, AgentResult, RequestContextBundle
from apps.content_planning.agents.memory import AgentMemory, MemoryEntry

logger = logging.getLogger(__name__)


STAGE_DISCUSSION_ROLES: dict[str, list[str]] = {
    "card": ["trend_analyst", "brief_synthesizer"],
    "brief": ["trend_analyst", "brief_synthesizer", "strategy_director"],
    "match": ["template_planner", "strategy_director", "visual_director"],
    "strategy": ["strategy_director", "visual_director", "brief_synthesizer"],
    "content": ["visual_director", "asset_producer", "strategy_director"],
    "plan": ["strategy_director", "visual_director", "asset_producer"],
    "asset": ["asset_producer", "visual_director", "strategy_director"],
}

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "trend_analyst": "趋势分析师",
    "brief_synthesizer": "Brief 编译师",
    "template_planner": "模板策划师",
    "strategy_director": "策略总监",
    "visual_director": "视觉总监",
    "asset_producer": "资产制作人",
}

# 与 apply_stage_updates 可编辑 brief 字段对齐；synthesis 仅允许这些 key
BRIEF_PROPOSED_UPDATE_KEYS: frozenset[str] = frozenset(
    {
        "target_user",
        "target_scene",
        "content_goal",
        "primary_value",
        "visual_style_direction",
        "avoid_directions",
        "template_hints",
        "core_motive",
        "price_positioning",
        "target_audience",
        "why_worth_doing",
        "competitive_angle",
    }
)

_TREND_HINT_TERMS = ("趋势", "热点", "时机", "最近", "平台变化", "为什么现在")

CouncilDecisionType = Literal["advisory", "conflicted", "insufficient_context", "applyable"]


@dataclass
class CouncilSynthesisBundle:
    """结构化合成结果（Advisory Session 核心字段）。"""

    consensus: str
    proposed_updates: dict[str, Any]
    agreements: list[str]
    disagreements: list[str]
    open_questions: list[str]
    recommended_next_steps: list[str]
    alternatives: list[dict[str, str]]
    model_decision_hint: str = ""  # applyable | advisory | exploratory


class DiscussionRound(BaseModel):
    """多 Agent 讨论记录。"""
    round_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    opportunity_id: str = ""
    stage: str = ""
    topic: str = ""
    participants: list[str] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    failed_participants: list[str] = Field(default_factory=list)
    consensus: str | None = None
    proposed_updates: dict[str, Any] = Field(default_factory=dict)
    overall_score: float = 0.0
    status: Literal["discussing", "concluded", "cancelled"] = "discussing"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Advisory Session 扩展
    council_decision_type: str = ""  # advisory | conflicted | insufficient_context | applyable
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, str]] = Field(default_factory=list)
    model_decision_hint: str = ""


def filter_brief_proposed_updates(raw: dict[str, Any]) -> dict[str, Any]:
    """仅保留 Brief 可应用字段，避免模型幻觉 key。"""
    return {k: v for k, v in raw.items() if k in BRIEF_PROPOSED_UPDATE_KEYS}


def reconcile_council_decision_type(
    *,
    diff_rows: list[dict[str, Any]],
    disagreements: list[str],
    open_questions: list[str],
    model_decision_hint: str = "",
) -> CouncilDecisionType:
    """结合字段 diff 与结构化产出，得到 UI 三态 + applyable。"""
    has_material = False
    for r in diff_rows:
        if r.get("blocked"):
            continue
        if r.get("before") != r.get("after"):
            has_material = True
    if has_material:
        return "applyable"
    if open_questions:
        return "insufficient_context"
    if disagreements:
        return "conflicted"
    if model_decision_hint == "exploratory":
        return "advisory"
    return "advisory"


def compute_applyability(diff_rows: list[dict[str, Any]]) -> Literal["direct", "partial", "none"]:
    if not diff_rows:
        return "none"
    any_unblocked = any(not r.get("blocked") for r in diff_rows)
    any_blocked = any(r.get("blocked") for r in diff_rows)
    if not any_unblocked:
        return "none"
    if any_blocked and any(not r.get("blocked") for r in diff_rows):
        return "partial"
    return "direct"


class DiscussionOrchestrator:
    """Orchestrate multi-agent discussions for a given stage and question."""

    def __init__(self):
        self._memory = AgentMemory()

    def discuss(
        self,
        opportunity_id: str,
        stage: str,
        user_question: str,
        context: AgentContext | None = None,
        on_message: Any = None,
        on_phase: Callable[[str, dict[str, Any]], None] | None = None,
        mode: Literal["fast", "deep"] = "deep",
    ) -> DiscussionRound:
        """Run a multi-agent discussion round."""
        participants = self._resolve_participants(stage, user_question, context, mode=mode)

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

        if on_phase:
            on_phase("collecting_opinions", {"label_zh": "收集专家观点"})

        object_context = self._resolve_object_context(stage, context)
        memory_context = self._resolve_memory_context(opportunity_id, context)

        opinion_results = self._collect_agent_opinions(
            participants=participants,
            user_question=user_question,
            stage=stage,
            object_context=object_context,
            memory_context=memory_context,
        )

        prior_statements: list[str] = []
        for result in opinion_results:
            agent_role = str(result["agent_role"])
            agent_name = str(result["agent_name"])
            if result["status"] == "ok":
                agent_response = str(result["response"])
                meta = dict(result.get("metadata") or {})
                meta.setdefault("agent_name", agent_name)
                meta.setdefault("stage", stage)
                msg = AgentMessage(
                    role="agent",
                    content=agent_response,
                    agent_role=agent_role,
                    metadata=meta,
                )
                discussion.messages.append(msg)
                prior_statements.append(f"[{agent_name}]: {agent_response}")
            else:
                discussion.failed_participants.append(agent_role)
                msg = AgentMessage(
                    role="agent",
                    content="（未成功获取该 Agent 观点，已跳过）",
                    agent_role=agent_role,
                    metadata={
                        "agent_name": agent_name,
                        "stage": stage,
                        "status": "failed",
                        "error": str(result.get("error", "")),
                    },
                )
                discussion.messages.append(msg)
            if on_message:
                on_message(msg)

        if on_phase:
            on_phase("synthesizing_consensus", {"label_zh": "综合共识与可应用提案"})

        if prior_statements:
            bundle = self._synthesize_consensus(user_question, stage, prior_statements, object_context)
            consensus = bundle.consensus
            proposed_updates = bundle.proposed_updates
            if stage == "brief":
                proposed_updates = filter_brief_proposed_updates(proposed_updates)
            discussion.agreements = bundle.agreements
            discussion.disagreements = bundle.disagreements
            discussion.open_questions = bundle.open_questions
            discussion.recommended_next_steps = bundle.recommended_next_steps
            discussion.alternatives = bundle.alternatives
            discussion.model_decision_hint = bundle.model_decision_hint
        else:
            consensus = "本轮讨论暂未拿到有效专家观点，建议稍后重试。"
            proposed_updates = {}
            bundle = CouncilSynthesisBundle(
                consensus=consensus,
                proposed_updates={},
                agreements=[],
                disagreements=[],
                open_questions=["是否提供更具体的业务目标或场景？"],
                recommended_next_steps=["补充问题细节后再次发起 Council"],
                alternatives=[],
            )
            discussion.open_questions = bundle.open_questions
            discussion.recommended_next_steps = bundle.recommended_next_steps

        discussion.consensus = consensus
        discussion.proposed_updates = proposed_updates
        discussion.status = "concluded"

        consensus_msg = AgentMessage(
            role="system",
            content=f"[共识] {consensus}",
            agent_role="lead_agent",
            metadata={
                "type": "consensus",
                "proposed_updates": proposed_updates,
                "agreements": discussion.agreements,
                "disagreements": discussion.disagreements,
                "open_questions": discussion.open_questions,
                "recommended_next_steps": discussion.recommended_next_steps,
                "alternatives": discussion.alternatives,
            },
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
                tags=[stage, "discussion", "partial" if discussion.failed_participants else "full"],
            )
        )

        if on_phase:
            on_phase("session_ready", {"label_zh": "会话产出已就绪"})

        return discussion

    def _collect_agent_opinions(
        self,
        *,
        participants: list[str],
        user_question: str,
        stage: str,
        object_context: str,
        memory_context: str,
    ) -> list[dict[str, Any]]:
        if not participants:
            return []

        def _run_one(agent_role: str, agent_name: str) -> dict[str, Any]:
            try:
                response, meta = self._get_agent_opinion_structured(
                    agent_role=agent_role,
                    agent_name=agent_name,
                    user_question=user_question,
                    stage=stage,
                    object_context=object_context,
                    memory_context=memory_context,
                    prior_statements=[],
                )
                return {
                    "agent_role": agent_role,
                    "agent_name": agent_name,
                    "status": "ok",
                    "response": response,
                    "metadata": meta,
                }
            except Exception as exc:
                logger.warning("discussion specialist failed: %s", agent_role, exc_info=True)
                return {
                    "agent_role": agent_role,
                    "agent_name": agent_name,
                    "status": "failed",
                    "error": str(exc),
                    "response": "",
                    "metadata": {},
                }

        results: list[dict[str, Any] | None] = [None] * len(participants)
        max_workers = min(max(len(participants), 1), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    _run_one,
                    agent_role,
                    AGENT_DISPLAY_NAMES.get(agent_role, agent_role),
                ): index
                for index, agent_role in enumerate(participants)
            }
            for future in as_completed(future_map):
                index = future_map[future]
                results[index] = future.result()
        return [cast(dict[str, Any], result) for result in results if result is not None]

    def _resolve_participants(
        self,
        stage: str,
        user_question: str,
        context: AgentContext | None,
        *,
        mode: Literal["fast", "deep"] = "deep",
    ) -> list[str]:
        participants = list(STAGE_DISCUSSION_ROLES.get(stage, ["trend_analyst", "brief_synthesizer"]))
        if mode == "fast":
            return participants[:1]
        if stage != "strategy":
            return participants

        wants_trend = any(term in user_question for term in _TREND_HINT_TERMS)
        if not wants_trend and context and context.extra:
            card = context.extra.get("card")
            if card is not None:
                if hasattr(card, "model_dump"):
                    card = card.model_dump(mode="json")
                try:
                    card_text = json.dumps(card, ensure_ascii=False, default=str)
                except Exception:
                    card_text = str(card)
                wants_trend = any(term in card_text for term in _TREND_HINT_TERMS)
        if wants_trend and "trend_analyst" not in participants:
            participants.append("trend_analyst")
        return participants

    def _get_agent_opinion_structured(
        self,
        *,
        agent_role: str,
        agent_name: str,
        user_question: str,
        stage: str,
        object_context: str,
        memory_context: str,
        prior_statements: list[str],
    ) -> tuple[str, dict[str, Any]]:
        """返回 (展示正文, metadata：stance/claim/...)。"""
        if not llm_router.is_any_available():
            text = self._rule_based_opinion(agent_role, user_question, stage)
            return text, {
                "stance": "neutral",
                "claim": text[:80],
                "agent_name": agent_name,
                "stage": stage,
            }

        prior_text = "\n".join(prior_statements) if prior_statements else "你是第一个发言的。"

        system = f"""你是「{agent_name}」，专业内容策划 Agent。
当前阶段：{stage}。请基于当前 Brief 快照与用户问题给出观点。
必须先输出 JSON，格式严格如下（不要 Markdown）：
{{"stance":"support|neutral|oppose|supplement","claim":"一句话立场","detail":"3-5句专业展开"}}
stance 含义：support 赞同主方向 / oppose 反对或风险 / supplement 补充条件 / neutral 中立。"""

        user_msg = f"""用户问题：{user_question}

【对象与 Brief 上下文】
{object_context}

相关记忆：
{memory_context}

其他专家发言摘要：
{prior_text}

仅输出 JSON。"""

        try:
            resp = llm_router.chat_json(
                [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=user_msg),
                ],
                temperature=0.35,
                max_tokens=700,
            )
        except Exception:
            logger.warning("agent opinion chat_json failed for %s", agent_role, exc_info=True)
            text = self._rule_based_opinion(agent_role, user_question, stage)
            return text, {
                "stance": "neutral",
                "claim": text[:80],
                "agent_name": agent_name,
                "stage": stage,
            }

        stance = str(resp.get("stance") or "neutral")
        claim = str(resp.get("claim") or "").strip()
        detail = str(resp.get("detail") or "").strip()
        if not detail:
            detail = self._rule_based_opinion(agent_role, user_question, stage)
        if not claim:
            claim = detail[:80]
        display = detail
        meta = {
            "stance": stance,
            "claim": claim,
            "agent_name": agent_name,
            "stage": stage,
        }
        return display, meta

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

    def _synthesize_consensus(
        self, question: str, stage: str, statements: list[str], object_context: str
    ) -> CouncilSynthesisBundle:
        """综合共识 + 结构化产出 + 白名单字段更新建议。"""
        if not llm_router.is_any_available():
            summary = "综合各方意见：" + "；".join(s.split("]: ", 1)[-1][:50] for s in statements)
            return CouncilSynthesisBundle(
                consensus=summary,
                proposed_updates={},
                agreements=[summary[:120]],
                disagreements=[],
                open_questions=[],
                recommended_next_steps=["在模型可用时重新发起以生成可应用字段建议"],
                alternatives=[],
                model_decision_hint="advisory",
            )

        all_text = "\n".join(statements)
        whitelist_note = ""
        if stage == "brief":
            whitelist_note = (
                f"proposed_updates 的 key 必须来自：{', '.join(sorted(BRIEF_PROPOSED_UPDATE_KEYS))}。"
            )
        sys = f"""你是内容策划总调度（Advisory Session）。请综合所有 Agent 观点，输出 JSON：
- consensus: 共识段落（中文）
- proposed_updates: 对象，仅含可落地字段的改写建议；若无把握则 {{}}
- agreements: 字符串数组，共识要点
- disagreements: 字符串数组，分歧点（无则 []）
- open_questions: 仍需用户补充的信息（无则 []）
- recommended_next_steps: 下一步建议（2-4 条）
- alternatives: [{{"label":"方向名","summary":"说明"}}] 可选多方向
- decision_type: 之一：applyable | advisory | exploratory
  （applyable 表示预期可直接改字段；advisory 有共识但偏策略不宜直接落字段；exploratory 信息不足）
{whitelist_note}"""

        try:
            resp = llm_router.chat_json(
                [
                    LLMMessage(role="system", content=sys),
                    LLMMessage(
                        role="user",
                        content=f"阶段：{stage}\n问题：{question}\n对象与快照：\n{object_context}\n\n各 Agent 观点：\n{all_text}",
                    ),
                ],
                temperature=0.3,
                max_tokens=1200,
            )
        except Exception:
            logger.warning("council synthesis chat_json failed, using fallback", exc_info=True)
            summary = "综合各方意见：" + "；".join(s.split("]: ", 1)[-1][:80] for s in statements)
            return CouncilSynthesisBundle(
                consensus=summary,
                proposed_updates={},
                agreements=[summary[:120]],
                disagreements=[],
                open_questions=[],
                recommended_next_steps=["请重试或检查模型配置"],
                alternatives=[],
                model_decision_hint="advisory",
            )

        consensus = str(resp.get("consensus") or "综合各方意见后，建议进一步细化方向。")
        updates = resp.get("proposed_updates", {})
        if not isinstance(updates, dict):
            updates = {}

        def _str_list(key: str) -> list[str]:
            raw = resp.get(key) or []
            if not isinstance(raw, list):
                return []
            return [str(x) for x in raw if str(x).strip()]

        alts_raw = resp.get("alternatives") or []
        alternatives: list[dict[str, str]] = []
        if isinstance(alts_raw, list):
            for item in alts_raw:
                if isinstance(item, dict):
                    alternatives.append(
                        {
                            "label": str(item.get("label") or "")[:80],
                            "summary": str(item.get("summary") or "")[:500],
                        }
                    )

        return CouncilSynthesisBundle(
            consensus=consensus,
            proposed_updates=updates,
            agreements=_str_list("agreements") or ([consensus[:160]] if consensus else []),
            disagreements=_str_list("disagreements"),
            open_questions=_str_list("open_questions"),
            recommended_next_steps=_str_list("recommended_next_steps"),
            alternatives=alternatives,
            model_decision_hint=str(resp.get("decision_type") or "advisory"),
        )

    def _build_object_context(self, stage: str, context: AgentContext | None) -> str:
        """Build a text summary of current objects for discussion context."""
        if context is None:
            return "无对象上下文"
        parts = []
        if context.brief:
            b = context.brief
            title = getattr(b, "opportunity_title", "") if hasattr(b, "opportunity_title") else (
                b.get("opportunity_title", "") if isinstance(b, dict) else ""
            )
            if title:
                parts.append(f"Brief标题: {title}")
        if context.strategy:
            parts.append("策略: 已生成")
        if context.plan:
            parts.append("NotePlan: 已生成")
        if context.match_result:
            parts.append("模板匹配: 已完成")
        return "\n".join(parts) if parts else "暂无对象"

    def _request_context_bundle(self, context: AgentContext | None) -> RequestContextBundle | None:
        if context is None:
            return None
        raw = context.extra.get("request_context_bundle")
        if raw is None:
            return None
        if isinstance(raw, RequestContextBundle):
            return raw
        if isinstance(raw, dict):
            try:
                return RequestContextBundle.model_validate(raw)
            except Exception:
                return None
        return None

    def _resolve_object_context(self, stage: str, context: AgentContext | None) -> str:
        bundle = self._request_context_bundle(context)
        base = ""
        if bundle is not None and bundle.object_summary:
            base = bundle.object_summary
        else:
            base = self._build_object_context(stage, context)

        extras: list[str] = []
        if bundle is not None:
            if bundle.council_brief_snapshot:
                extras.append("【Brief 可写字段快照 JSON】\n" + bundle.council_brief_snapshot)
            if bundle.council_locked_fields_hint:
                extras.append(bundle.council_locked_fields_hint)
        if extras:
            return base + "\n\n" + "\n\n".join(extras)
        return base

    def _get_memory_context(self, opportunity_id: str) -> str:
        """Retrieve relevant memories for discussion context."""
        entries = self._memory.recall(opportunity_id=opportunity_id, limit=5)
        if not entries:
            return "无历史记忆"
        return "\n".join(f"- [{e.category}] {e.content[:80]}" for e in entries)

    def _resolve_memory_context(self, opportunity_id: str, context: AgentContext | None) -> str:
        bundle = self._request_context_bundle(context)
        if bundle is not None and bundle.memory_context:
            return bundle.memory_context
        return self._get_memory_context(opportunity_id)
