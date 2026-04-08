"""策略总监 Agent：生成改写策略并支持多版本与局部重写。"""

from __future__ import annotations

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.strategy_generator import RewriteStrategyGenerator


class StrategyDirectorAgent(BaseAgent):
    agent_id = "agent_strategy_director"
    agent_name = "策略总监"
    agent_role = "strategy_director"

    def __init__(self) -> None:
        super().__init__()
        self._generator = RewriteStrategyGenerator()

    def run(self, context: AgentContext) -> AgentResult:
        brief = context.brief
        match_result = context.match_result
        template = context.template

        if not all([brief, match_result, template]):
            return self._make_result(explanation="缺少 Brief/匹配结果/模板，无法生成策略", confidence=0.0)

        strategy = self._generator.generate(brief, match_result, template)

        chips = [
            AgentChip(label="更偏种草", action="regenerate", params={"tone_hint": "种草收藏"}),
            AgentChip(label="更偏转化", action="regenerate", params={"tone_hint": "转化"}),
            AgentChip(label="更适合礼赠", action="regenerate", params={"tone_hint": "礼赠"}),
            AgentChip(label="更平价改造", action="regenerate", params={"tone_hint": "平价改造"}),
        ]

        explanation_parts = [f"已生成策略 v{strategy.strategy_version}"]
        if strategy.comparison_note:
            explanation_parts.append(f"与规则版本差异：{strategy.comparison_note}")
        explanation_parts.append(f"定位：{strategy.positioning_statement}")

        return self._make_result(
            output_object=strategy,
            explanation="；".join(explanation_parts),
            confidence=0.75,
            suggestions=chips,
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation
