"""资产制作人 Agent：生成标题/正文/资产包。"""

from __future__ import annotations

from apps.content_planning.agents.base import AgentChip, AgentContext, AgentResult, BaseAgent
from apps.content_planning.services.asset_assembler import AssetAssembler
from apps.content_planning.services.body_generator import BodyGenerator
from apps.content_planning.services.title_generator import TitleGenerator


class AssetProducerAgent(BaseAgent):
    agent_id = "agent_asset_producer"
    agent_name = "资产制作人"
    agent_role = "asset_producer"

    def __init__(self) -> None:
        super().__init__()
        self._title_gen = TitleGenerator()
        self._body_gen = BodyGenerator()

    def run(self, context: AgentContext) -> AgentResult:
        plan = context.plan
        strategy = context.strategy

        if plan is None or strategy is None:
            return self._make_result(explanation="缺少 NotePlan 或策略", confidence=0.0)

        titles = self._title_gen.generate(plan, strategy)
        body = self._body_gen.generate(plan, strategy)

        bundle = AssetAssembler.assemble(
            opportunity_id=context.opportunity_id,
            plan_id=getattr(plan, "plan_id", ""),
            titles=titles,
            body=body,
            image_briefs=context.image_briefs,
        )

        chips = [
            AgentChip(label="重生成标题", action="regenerate_titles", params={}),
            AgentChip(label="重生成正文", action="regenerate_body", params={}),
            AgentChip(label="更像原生", action="hint_regen", params={"style": "native"}),
            AgentChip(label="更强钩子", action="hint_regen", params={"style": "hook"}),
        ]

        title_count = len(titles.titles)
        body_len = len(body.body_draft)

        return self._make_result(
            output_object=bundle,
            explanation=f"已生成 {title_count} 条标题候选 + {body_len}字正文草稿，资产包状态：{bundle.export_status}",
            confidence=0.7 if bundle.export_status == "ready" else 0.4,
            suggestions=chips,
        )

    def explain(self, result: AgentResult) -> str:
        return result.explanation
