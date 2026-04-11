"""Lead Agent v2：tool_calls 驱动路由 + Pipeline/Interactive 双模式。

借鉴 DeerFlow Lead Agent 模式（唯一入口，动态选工具/技能/子 Agent）
+ Hermes Agent Loop（LLM -> tool_calls -> execute -> 汇总）。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from apps.content_planning.agents.base import (
    AgentChip,
    AgentContext,
    AgentResult,
    BaseAgent,
)
from apps.content_planning.agents.intent_router import IntentRouter
from apps.content_planning.agents.memory import AgentMemory
from apps.content_planning.agents.skill_registry import skill_registry

logger = logging.getLogger(__name__)

# Legacy keyword map kept for fast-mode fallback
_ROLE_KEYWORDS: dict[str, list[str]] = {
    "trend_analyst": ["趋势", "分析", "机会", "竞品", "观望", "深入", "值得"],
    "brief_synthesizer": ["brief", "摘要", "方向", "种草", "转化", "目标", "定位"],
    "template_planner": ["模板", "匹配", "风格", "换个", "template"],
    "strategy_director": ["策略", "改写", "调性", "偏", "更", "钩子", "标题"],
    "visual_director": ["图片", "视觉", "场景", "桌布", "封面", "广告感", "图位"],
    "asset_producer": ["资产", "导出", "变体", "发布", "asset", "打包"],
}

_STAGE_AGENT_MAP: dict[str, str] = {
    "opportunity": "trend_analyst",
    "brief": "brief_synthesizer",
    "template": "template_planner",
    "strategy": "strategy_director",
    "plan": "visual_director",
    "asset": "asset_producer",
}


class LeadAgent(BaseAgent):
    """总调度 Agent v2：支持 tool_calls 驱动路由和 Pipeline/Interactive 双模式。"""

    agent_id = "lead_agent_001"
    agent_name = "总调度"
    agent_role = "lead_agent"

    def __init__(self) -> None:
        super().__init__()
        self._deerflow = None
        self._intent_router = IntentRouter()

    def _get_deerflow(self) -> Any:
        if self._deerflow is None:
            try:
                from apps.content_planning.adapters.deerflow_adapter import DeerFlowAdapter
                self._deerflow = DeerFlowAdapter()
            except Exception:
                logger.debug("DeerFlowAdapter not available", exc_info=True)
        return self._deerflow

    def run(self, context: AgentContext) -> AgentResult:
        """Dispatch based on mode: pipeline or interactive."""
        mode = context.config.get("execution_mode", self.execution_mode(context))

        if mode == "pipeline":
            return self._run_pipeline(context)

        return self._run_interactive(context)

    def _run_interactive(self, context: AgentContext) -> AgentResult:
        """Interactive mode: route to best sub-agent via tool_calls or keyword fallback."""
        user_message = context.extra.get("user_message", "")
        current_stage = context.extra.get("current_stage", "")
        hint = context.extra.get("hint", "")
        mode = self.execution_mode(context)

        routing = self._route(user_message or hint, current_stage, context, mode=mode)
        target_role = routing["target"]
        extra_agents = routing.get("extra_agents", [])

        sub_agent = self._instantiate(target_role)
        if sub_agent is None:
            return self._make_result(
                explanation=f"无法确定合适的 Agent 角色: {user_message or hint or current_stage}",
                confidence=0.2,
                suggestions=self._default_suggestions(),
            )

        from apps.content_planning.agents.middleware import MiddlewareChain
        chain = MiddlewareChain.default_chain()
        result = chain.execute(context, target_role, sub_agent.run)

        suggestions = list(result.suggestions)
        for extra_role in extra_agents:
            suggestions.append(AgentChip(
                label=f"也问问 {extra_role}",
                action=extra_role,
            ))
        suggestions.append(
            AgentChip(label="换个角度分析", action="lead_agent", params={"hint": "换个角度"}),
        )

        explanation = f"[{result.agent_name}] {result.explanation}"
        if routing.get("reasoning"):
            explanation = f"{explanation}\n调度理由：{routing['reasoning']}"

        return self._make_result(
            output_object=result.output_object,
            explanation=explanation,
            confidence=result.confidence,
            suggestions=suggestions,
        )

    def _run_pipeline(self, context: AgentContext) -> AgentResult:
        """Pipeline mode: trigger full graph execution."""
        return self._make_result(
            explanation="Pipeline 模式: 请使用 AgentPipelineRunner 触发全链路",
            confidence=0.9,
            output_object={"mode": "pipeline", "opportunity_id": context.opportunity_id},
            suggestions=[AgentChip(label="触发全链路", action="trigger_pipeline",
                                   params={"opportunity_id": context.opportunity_id})],
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation

    # ── Tool-calls driven routing ──

    def _route_with_tools(self, message: str, stage: str, context: AgentContext) -> dict | None:
        """Use LLM with tool_calls to determine routing."""
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
            from apps.content_planning.agents.tool_registry import tool_registry

            if not llm_router.is_any_available():
                return None

            tools_schema = tool_registry.to_openai_schema(toolset="orchestration")
            skill_tools = skill_registry.to_openai_schema()
            all_tools = tools_schema + skill_tools

            if not all_tools:
                return None

            memory_ctx = self.resolve_memory_context(context)
            object_summary = self.resolve_object_summary(context)

            system_prompt = (
                "你是内容策划平台的总调度 Agent。根据用户意图，选择最合适的工具或技能来完成任务。\n"
                f"当前阶段: {stage or '未知'}\n"
                f"已有上下文: brief={'有' if context.brief else '无'}, "
                f"strategy={'有' if context.strategy else '无'}, "
                f"plan={'有' if context.plan else '无'}\n"
            )
            if memory_ctx:
                system_prompt += f"\n历史记忆:\n{memory_ctx}\n"
            if object_summary:
                system_prompt += f"\n对象摘要:\n{object_summary}\n"

            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=message),
            ]

            resp = llm_router.chat(messages, tools=all_tools, fast_mode=True)
            if resp.tool_calls:
                tc = resp.tool_calls[0]
                fn_name = tc.function.get("name", "")
                fn_args = tc.function.get("arguments", "{}")
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except json.JSONDecodeError:
                        fn_args = {}

                if fn_name == "delegate_task":
                    target_role = fn_args.get("agent_role", "")
                    if target_role in _ROLE_KEYWORDS:
                        return {
                            "target": target_role,
                            "extra_agents": [],
                            "reasoning": fn_args.get("task_description", ""),
                            "method": "tool_calls",
                        }

                if fn_name == "trigger_pipeline":
                    return {
                        "target": "pipeline",
                        "extra_agents": [],
                        "reasoning": "LLM 建议触发全链路",
                        "method": "tool_calls",
                    }

                if fn_name.startswith("skill_"):
                    skill_id = fn_name[6:]
                    skill = skill_registry.get(skill_id)
                    if skill and skill.agent_role:
                        return {
                            "target": skill.agent_role,
                            "extra_agents": [],
                            "reasoning": f"匹配到技能: {skill.skill_name}",
                            "method": "tool_calls_skill",
                        }

            return None
        except Exception:
            logger.debug("Tool-calls routing failed", exc_info=True)
            return None

    def _route_llm(self, message: str, stage: str, context: AgentContext) -> dict | None:
        """LLM-driven routing via DeerFlowAdapter (legacy path)."""
        try:
            deerflow = self._get_deerflow()
            if deerflow is None:
                return None

            from apps.content_planning.adapters.llm_router import llm_router
            if not llm_router.is_any_available():
                return None

            memory_ctx = self.resolve_memory_context(
                context,
                fallback=lambda: deerflow.recall_relevant_memory(
                    context.opportunity_id, query=message,
                ),
            )
            object_summary = self.resolve_object_summary(
                context,
                fallback=lambda: deerflow.build_object_summary(context),
            )

            resp = deerflow.route_with_llm(
                user_message=message,
                stage=stage,
                memory_context=memory_ctx,
                object_summary=object_summary,
            )

            agents = resp.get("target_agents", [])
            if not agents:
                return None

            valid_roles = set(_ROLE_KEYWORDS.keys())
            agents = [a for a in agents if a in valid_roles]
            if not agents:
                return None

            return {
                "target": agents[0],
                "extra_agents": agents[1:],
                "reasoning": resp.get("reasoning", ""),
                "method": "llm",
            }
        except Exception:
            logger.debug("LLM routing failed, will use keyword fallback", exc_info=True)
            return None

    def _route_keyword(self, message: str, stage: str, context: AgentContext) -> str:
        """Keyword-based routing (fast fallback)."""
        if message:
            scores: dict[str, int] = {}
            msg_lower = message.lower()
            for role, keywords in _ROLE_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in msg_lower)
                if score > 0:
                    scores[role] = score
            if scores:
                return max(scores, key=scores.get)  # type: ignore[arg-type]

        if message:
            matched_skills = skill_registry.find_by_keyword(message)
            if matched_skills:
                return matched_skills[0].agent_role

        if stage and stage in _STAGE_AGENT_MAP:
            return _STAGE_AGENT_MAP[stage]

        if context.asset_bundle:
            return "asset_producer"
        if context.plan:
            return "visual_director"
        if context.strategy:
            return "strategy_director"
        if context.match_result:
            return "template_planner"
        if context.brief:
            return "brief_synthesizer"
        return "trend_analyst"

    def _route(self, message: str, stage: str, context: AgentContext, *, mode: str = "deep") -> dict:
        """Route with priority: IntentRouter (stage+regex+LLM) > tool_calls > keyword fallback."""
        if mode == "fast" and stage and stage in _STAGE_AGENT_MAP:
            target = _STAGE_AGENT_MAP[stage]
            return {"target": target, "extra_agents": [], "reasoning": "", "method": "fast_stage"}

        intent_result = self._intent_router.route(message, stage, context)
        if intent_result.confidence >= 0.5 and intent_result.target_agent != "council":
            logger.info("Routing via IntentRouter (%s) → %s (conf=%.2f)",
                        intent_result.method, intent_result.target_agent, intent_result.confidence)
            target = intent_result.target_agent
            if target in _ROLE_KEYWORDS or target in _STAGE_AGENT_MAP.values():
                return {
                    "target": target,
                    "extra_agents": [],
                    "reasoning": intent_result.reasoning,
                    "method": f"intent_{intent_result.method}",
                    "intent": intent_result.intent,
                }

        if mode != "fast" and message:
            tool_result = self._route_with_tools(message, stage, context)
            if tool_result:
                logger.info("Routing via tool_calls → %s", tool_result["target"])
                return tool_result

            llm_result = self._route_llm(message, stage, context)
            if llm_result:
                logger.info("Routing via LLM → %s", llm_result["target"])
                return llm_result

        keyword_target = self._route_keyword(message, stage, context)
        logger.info("Routing via keywords → %s", keyword_target)
        return {"target": keyword_target, "extra_agents": [], "reasoning": "", "method": "keyword"}

    def _instantiate(self, role: str) -> BaseAgent | None:
        """Lazy-instantiate a sub-agent by role."""
        try:
            if role == "trend_analyst":
                from apps.content_planning.agents.trend_analyst import TrendAnalystAgent
                return TrendAnalystAgent()
            elif role == "brief_synthesizer":
                from apps.content_planning.agents.brief_synthesizer import BriefSynthesizerAgent
                return BriefSynthesizerAgent()
            elif role == "template_planner":
                from apps.content_planning.agents.template_planner import TemplatePlannerAgent
                return TemplatePlannerAgent()
            elif role == "strategy_director":
                from apps.content_planning.agents.strategy_director import StrategyDirectorAgent
                return StrategyDirectorAgent()
            elif role == "visual_director":
                from apps.content_planning.agents.visual_director import VisualDirectorAgent
                return VisualDirectorAgent()
            elif role == "asset_producer":
                from apps.content_planning.agents.asset_producer import AssetProducerAgent
                return AssetProducerAgent()
        except Exception:
            logger.exception("Failed to instantiate agent: %s", role)
        return None

    def _default_suggestions(self) -> list[AgentChip]:
        return [
            AgentChip(label="趋势分析", action="trend_analyst"),
            AgentChip(label="Brief 编译", action="brief_synthesizer"),
            AgentChip(label="模板匹配", action="template_planner"),
            AgentChip(label="策略生成", action="strategy_director"),
            AgentChip(label="图片规划", action="visual_director"),
            AgentChip(label="资产组包", action="asset_producer"),
        ]
