"""IntentRouter: Stage-constrained intent parsing, replacing LeadAgent keyword guessing.

Routing priority: stage constraint → regex intent map → LLM fallback.
Intent categories: analyze / generate / discuss / evaluate.
Each intent maps to a specific Agent + API endpoint.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

IntentType = Literal["analyze", "generate", "discuss", "evaluate"]


@dataclass
class RoutingResult:
    intent: IntentType
    target_agent: str
    api_endpoint: str
    confidence: float
    method: str  # "stage_constraint" | "regex" | "llm_fallback"
    reasoning: str = ""


_STAGE_DEFAULT_AGENTS: dict[str, str] = {
    "opportunity": "trend_analyst",
    "card": "trend_analyst",
    "brief": "brief_synthesizer",
    "match": "template_planner",
    "template": "template_planner",
    "strategy": "strategy_director",
    "plan": "plan_compiler",
    "content": "plan_compiler",
    "visual": "visual_director",
    "asset": "asset_producer",
}

_INTENT_PATTERNS: dict[IntentType, list[re.Pattern[str]]] = {
    "analyze": [
        re.compile(r"分析|趋势|竞品|对比|机会|洞察|观望|深入|研究|调研", re.I),
        re.compile(r"analyz|compare|assess|research", re.I),
    ],
    "generate": [
        re.compile(r"生成|编译|创建|写|制作|出|编写|输出|新的|重新|改写|优化|重做", re.I),
        re.compile(r"generat|creat|writ|compil|produc|regenerat|rewrit", re.I),
    ],
    "discuss": [
        re.compile(r"讨论|委员会|圆桌|多角色|辩论|探讨|意见|看法|Council", re.I),
        re.compile(r"discuss|council|debate|opinion|roundtable", re.I),
    ],
    "evaluate": [
        re.compile(r"评分|打分|评估|质量|检查|审查|健康度|一致性|合规|风险", re.I),
        re.compile(r"score|rate|check|review|health|consistenc|risk|validat|evaluat", re.I),
    ],
}

_INTENT_TO_AGENT_MAP: dict[str, dict[IntentType, str]] = {
    "opportunity": {"analyze": "trend_analyst", "generate": "trend_analyst", "discuss": "council", "evaluate": "trend_analyst"},
    "brief": {"analyze": "brief_synthesizer", "generate": "brief_synthesizer", "discuss": "council", "evaluate": "health_checker"},
    "template": {"analyze": "template_planner", "generate": "template_planner", "discuss": "council", "evaluate": "template_planner"},
    "strategy": {"analyze": "strategy_director", "generate": "strategy_director", "discuss": "council", "evaluate": "health_checker"},
    "plan": {"analyze": "plan_compiler", "generate": "plan_compiler", "discuss": "council", "evaluate": "health_checker"},
    "visual": {"analyze": "visual_director", "generate": "visual_director", "discuss": "council", "evaluate": "visual_director"},
    "asset": {"analyze": "asset_producer", "generate": "asset_producer", "discuss": "council", "evaluate": "judge_agent"},
}

_INTENT_TO_ENDPOINT: dict[IntentType, str] = {
    "analyze": "/content-planning/run-agent/{opportunity_id}",
    "generate": "/content-planning/run-agent/{opportunity_id}",
    "discuss": "/content-planning/discussion/{opportunity_id}",
    "evaluate": "/content-planning/evaluate/{opportunity_id}",
}


class IntentRouter:
    """Stage-constrained intent router: replaces LeadAgent keyword guessing."""

    def route(
        self,
        message: str,
        current_stage: str,
        context: Any = None,
    ) -> RoutingResult:
        """Route user intent with priority: stage → regex → LLM fallback."""
        stage = self._normalize_stage(current_stage)
        intent = self._classify_intent(message)
        agent = self._resolve_agent(stage, intent)
        endpoint = _INTENT_TO_ENDPOINT.get(intent, "/content-planning/chat/{opportunity_id}")

        if not message.strip():
            return RoutingResult(
                intent=intent,
                target_agent=_STAGE_DEFAULT_AGENTS.get(stage, "trend_analyst"),
                api_endpoint=endpoint,
                confidence=0.5,
                method="stage_constraint",
                reasoning=f"无消息，使用阶段 {stage} 默认 Agent",
            )

        regex_confidence = self._regex_confidence(message, intent)
        if regex_confidence > 0.0:
            return RoutingResult(
                intent=intent,
                target_agent=agent,
                api_endpoint=endpoint,
                confidence=min(0.6 + regex_confidence * 0.3, 0.95),
                method="regex",
                reasoning=f"正则匹配意图 {intent} 于阶段 {stage}",
            )

        llm_result = self._llm_classify(message, stage)
        if llm_result is not None:
            return llm_result

        return RoutingResult(
            intent="analyze",
            target_agent=_STAGE_DEFAULT_AGENTS.get(stage, "trend_analyst"),
            api_endpoint=endpoint,
            confidence=0.3,
            method="stage_constraint",
            reasoning=f"回退到阶段 {stage} 默认 Agent",
        )

    def _normalize_stage(self, stage: str) -> str:
        s = stage.lower().strip()
        aliases = {
            "card": "opportunity", "match": "template",
            "content": "plan", "visual": "visual",
        }
        return aliases.get(s, s)

    def _classify_intent(self, message: str) -> IntentType:
        scores: dict[IntentType, int] = {"analyze": 0, "generate": 0, "discuss": 0, "evaluate": 0}
        for intent_type, patterns in _INTENT_PATTERNS.items():
            for pattern in patterns:
                matches = pattern.findall(message)
                scores[intent_type] += len(matches)
        if max(scores.values()) == 0:
            return "analyze"
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def _regex_confidence(self, message: str, intent: IntentType) -> float:
        patterns = _INTENT_PATTERNS.get(intent, [])
        total_matches = sum(len(p.findall(message)) for p in patterns)
        return min(total_matches / 3.0, 1.0)

    def _resolve_agent(self, stage: str, intent: IntentType) -> str:
        stage_map = _INTENT_TO_AGENT_MAP.get(stage, {})
        return stage_map.get(intent, _STAGE_DEFAULT_AGENTS.get(stage, "trend_analyst"))

    def _llm_classify(self, message: str, stage: str) -> RoutingResult | None:
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
            if not llm_router.is_any_available():
                return None
            resp = llm_router.chat_json(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            "你是意图分类器。将用户消息分类为以下之一：analyze/generate/discuss/evaluate。"
                            f"当前工作阶段：{stage}。"
                            '返回 JSON：{{"intent":"...","agent":"...","reasoning":"..."}}'
                        ),
                    ),
                    LLMMessage(role="user", content=message),
                ],
                temperature=0.1,
                max_tokens=200,
            )
            if resp and "intent" in resp:
                intent = resp["intent"]
                if intent not in ("analyze", "generate", "discuss", "evaluate"):
                    intent = "analyze"
                agent = resp.get("agent") or self._resolve_agent(stage, intent)
                return RoutingResult(
                    intent=intent,
                    target_agent=agent,
                    api_endpoint=_INTENT_TO_ENDPOINT.get(intent, ""),
                    confidence=0.8,
                    method="llm_fallback",
                    reasoning=resp.get("reasoning", ""),
                )
        except Exception:
            logger.debug("LLM intent classification failed", exc_info=True)
        return None
