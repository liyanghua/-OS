"""Skill Registry v2：可执行能力注册 + 自动沉淀。

借鉴 DeerFlow 的 Skill Markdown 工作流 + Hermes 的自动技能创建。
每个 Skill 的 workflow_steps 引用 ToolRegistry 中的工具，可直接执行。
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillStep(BaseModel):
    """A single executable step in a skill workflow."""
    tool_name: str = ""
    description: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    condition: str = ""


class SkillDefinition(BaseModel):
    """Skill 定义 v2: 可执行工作流 + Hermes 式版本追踪。"""
    skill_id: str = ""
    skill_name: str = ""
    description: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    agent_role: str = ""
    workflow_steps: list[str] = Field(default_factory=list)
    executable_steps: list[SkillStep] = Field(default_factory=list)
    prompt_fragment: str = ""
    enabled: bool = True
    category: str = ""
    source: str = "builtin"
    version: int = 1
    success_count: int = 0
    fail_count: int = 0
    last_updated: str = ""

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0


class SkillExecutionResult(BaseModel):
    """Result of running a skill."""
    skill_id: str = ""
    steps_completed: int = 0
    steps_total: int = 0
    outputs: list[Any] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    success: bool = False


class SkillRegistry:
    """管理、发现、执行 Skills。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        self._loaded_from: set[str] = set()

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.skill_id] = skill
        logger.debug("Registered skill: %s (%s)", skill.skill_name, skill.skill_id)

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def list_skills(self, *, enabled_only: bool = True) -> list[SkillDefinition]:
        skills = list(self._skills.values())
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        return skills

    def find_by_keyword(self, text: str) -> list[SkillDefinition]:
        text_lower = text.lower()
        matches = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            for kw in skill.trigger_keywords:
                if kw.lower() in text_lower:
                    matches.append(skill)
                    break
        return matches

    def find_by_agent(self, agent_role: str) -> list[SkillDefinition]:
        return [s for s in self._skills.values() if s.agent_role == agent_role and s.enabled]

    def execute_skill(self, skill_id: str, context: dict[str, Any] | None = None) -> SkillExecutionResult:
        """Execute a skill's workflow steps via ToolRegistry."""
        skill = self.get(skill_id)
        if skill is None:
            return SkillExecutionResult(skill_id=skill_id, errors=["Skill not found"])

        steps = skill.executable_steps
        if not steps:
            return SkillExecutionResult(
                skill_id=skill_id,
                steps_total=len(skill.workflow_steps),
                errors=["No executable steps defined (legacy text-only workflow)"],
            )

        from apps.content_planning.agents.tool_registry import tool_registry

        result = SkillExecutionResult(skill_id=skill_id, steps_total=len(steps))
        for step in steps:
            if step.condition and context:
                if not self._evaluate_condition(step.condition, context):
                    result.outputs.append({"skipped": True, "step": step.description})
                    result.steps_completed += 1
                    continue

            args = dict(step.arguments)
            if context:
                for k, v in args.items():
                    if isinstance(v, str) and v.startswith("$ctx."):
                        key = v[5:]
                        args[k] = context.get(key)

            try:
                tool_result = tool_registry.handle_tool_call(step.tool_name, args)
                result.outputs.append(tool_result)
                result.steps_completed += 1
            except Exception as exc:
                result.errors.append(f"Step '{step.description}' failed: {exc}")
                break

        result.success = result.steps_completed == result.steps_total and not result.errors
        if result.success:
            skill.success_count += 1
        else:
            skill.fail_count += 1
        return result

    async def aexecute_skill(self, skill_id: str, context: dict[str, Any] | None = None) -> SkillExecutionResult:
        """Async version of execute_skill."""
        skill = self.get(skill_id)
        if skill is None:
            return SkillExecutionResult(skill_id=skill_id, errors=["Skill not found"])

        steps = skill.executable_steps
        if not steps:
            return SkillExecutionResult(
                skill_id=skill_id, steps_total=len(skill.workflow_steps),
                errors=["No executable steps defined"],
            )

        from apps.content_planning.agents.tool_registry import tool_registry

        result = SkillExecutionResult(skill_id=skill_id, steps_total=len(steps))
        for step in steps:
            if step.condition and context and not self._evaluate_condition(step.condition, context):
                result.outputs.append({"skipped": True, "step": step.description})
                result.steps_completed += 1
                continue

            args = dict(step.arguments)
            if context:
                for k, v in args.items():
                    if isinstance(v, str) and v.startswith("$ctx."):
                        args[k] = context.get(v[5:])

            try:
                tool_result = await tool_registry.ahandle_tool_call(step.tool_name, args)
                result.outputs.append(tool_result)
                result.steps_completed += 1
            except Exception as exc:
                result.errors.append(f"Step '{step.description}' failed: {exc}")
                break

        result.success = result.steps_completed == result.steps_total and not result.errors
        if result.success:
            skill.success_count += 1
        else:
            skill.fail_count += 1
        return result

    def create_skill_from_result(
        self,
        *,
        agent_role: str,
        task_description: str,
        tool_calls_history: list[dict[str, Any]],
        category: str = "auto_generated",
    ) -> SkillDefinition | None:
        """Hermes-style: auto-create a skill from a successful task's tool call history."""
        if not tool_calls_history:
            return None

        steps = []
        for tc in tool_calls_history:
            fn = tc.get("function", {})
            steps.append(SkillStep(
                tool_name=fn.get("name", ""),
                description=fn.get("name", ""),
                arguments=json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {}),
            ))

        skill_id = f"auto_{uuid.uuid4().hex[:8]}"
        skill = SkillDefinition(
            skill_id=skill_id,
            skill_name=f"[自动] {task_description[:30]}",
            description=f"从 {agent_role} 任务自动沉淀: {task_description[:100]}",
            agent_role=agent_role,
            executable_steps=steps,
            workflow_steps=[s.tool_name for s in steps],
            category=category,
            source="auto_generated",
        )
        self.register(skill)
        logger.info("Auto-created skill: %s from %d tool calls", skill_id, len(steps))
        return skill

    def load_from_yaml(self, yaml_path: str | Path) -> int:
        path = Path(yaml_path)
        if str(path) in self._loaded_from:
            return 0
        if not path.exists():
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            skills_data = data.get("skills", [])
            if isinstance(skills_data, list):
                for item in skills_data:
                    skill = SkillDefinition(**item)
                    self.register(skill)
                self._loaded_from.add(str(path))
                return len(skills_data)
        except Exception:
            logger.debug("Failed to load skills from %s", path, exc_info=True)
        return 0

    def load_from_markdown(self, md_path: str | Path) -> SkillDefinition | None:
        """Load a DeerFlow-style skill from a Markdown file."""
        path = Path(md_path)
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
            lines = text.strip().split("\n")
            name = lines[0].lstrip("#").strip() if lines else path.stem
            description = ""
            steps_section = False
            workflow_steps = []
            for line in lines[1:]:
                stripped = line.strip()
                if stripped.lower().startswith("## steps") or stripped.lower().startswith("## workflow"):
                    steps_section = True
                    continue
                if stripped.startswith("## "):
                    steps_section = False
                    continue
                if steps_section and stripped.startswith("- "):
                    workflow_steps.append(stripped[2:])
                elif not steps_section and stripped and not description:
                    description = stripped

            skill = SkillDefinition(
                skill_id=f"md_{path.stem}",
                skill_name=name,
                description=description,
                workflow_steps=workflow_steps,
                source="markdown",
            )
            self.register(skill)
            return skill
        except Exception:
            logger.debug("Failed to load skill from %s", path, exc_info=True)
            return None

    def load_defaults(self) -> int:
        defaults = [
            SkillDefinition(
                skill_id="trend_deep_analysis",
                skill_name="深度趋势分析",
                description="对机会卡进行多维度深度分析",
                trigger_keywords=["深入分析", "竞品", "趋势", "深度"],
                agent_role="trend_analyst",
                workflow_steps=["提取关键信号", "对比竞品", "评估窗口", "输出报告"],
                executable_steps=[
                    SkillStep(tool_name="analyze_opportunity", description="提取关键信号", arguments={"card": "$ctx.card"}),
                    SkillStep(tool_name="compare_competitors", description="对比竞品", arguments={"card": "$ctx.card"}),
                    SkillStep(tool_name="evaluate_timing_window", description="评估时间窗口", arguments={"card": "$ctx.card"}),
                ],
                category="analysis",
            ),
            SkillDefinition(
                skill_id="generate_brief_from_promoted",
                skill_name="从已推进机会生成 Brief",
                description="基于已推进的机会卡自动编译 OpportunityBrief",
                trigger_keywords=["生成brief", "编译brief", "从机会生成"],
                agent_role="brief_synthesizer",
                workflow_steps=["加载机会卡", "提取核心信号", "编译Brief", "检查完整度"],
                executable_steps=[
                    SkillStep(tool_name="compile_brief", description="编译 Brief", arguments={"card": "$ctx.card"}),
                    SkillStep(tool_name="evaluate_stage", description="检查 Brief 完整度", arguments={"stage": "brief", "opportunity_id": "$ctx.opportunity_id"}),
                ],
                category="compilation",
            ),
            SkillDefinition(
                skill_id="brief_comparison",
                skill_name="Brief 多版本对比",
                description="对比多个 Brief 版本的差异",
                trigger_keywords=["对比", "版本", "哪个好", "选哪个"],
                agent_role="brief_synthesizer",
                workflow_steps=["加载历史版本", "逐字段对比", "标注差异", "推荐最优版本"],
                executable_steps=[
                    SkillStep(tool_name="load_brief_versions", description="加载历史版本", arguments={"opportunity_id": "$ctx.opportunity_id"}),
                    SkillStep(tool_name="compare_briefs", description="逐字段对比", arguments={"opportunity_id": "$ctx.opportunity_id"}),
                ],
                category="comparison",
            ),
            SkillDefinition(
                skill_id="rematch_templates_for_brief",
                skill_name="重新匹配模板",
                description="基于更新后的 Brief 重新匹配模板",
                trigger_keywords=["重新匹配", "换模板", "不合适"],
                agent_role="template_planner",
                workflow_steps=["加载最新Brief", "重新评分", "返回新Top3"],
                executable_steps=[
                    SkillStep(tool_name="match_templates", description="模板匹配", arguments={"brief": "$ctx.brief"}),
                ],
                category="matching",
            ),
            SkillDefinition(
                skill_id="compare_strategy_blocks",
                skill_name="策略块对比",
                description="对比当前策略中不同 block 的方向",
                trigger_keywords=["对比方案", "两个方向", "辩论", "哪个策略", "对比策略"],
                agent_role="strategy_director",
                workflow_steps=["提取策略块", "生成对比分析", "列出优劣", "推荐选择"],
                executable_steps=[
                    SkillStep(tool_name="generate_strategy", description="生成方向 A", arguments={"brief": "$ctx.brief", "match_result": "$ctx.match_result", "variant": "A"}),
                    SkillStep(tool_name="generate_strategy", description="生成方向 B", arguments={"brief": "$ctx.brief", "match_result": "$ctx.match_result", "variant": "B"}),
                    SkillStep(tool_name="compare_strategies", description="对比两个策略方向", arguments={"opportunity_id": "$ctx.opportunity_id"}),
                ],
                category="planning",
            ),
            SkillDefinition(
                skill_id="regenerate_image_slot",
                skill_name="重新生成图位",
                description="重新生成指定图位的视觉规划",
                trigger_keywords=["重新生成图", "换图", "重做图位"],
                agent_role="visual_director",
                workflow_steps=["定位图位", "重新生成视觉规划", "返回新图位"],
                executable_steps=[
                    SkillStep(tool_name="generate_image_briefs", description="重新生成图位规划", arguments={"plan": "$ctx.plan", "strategy": "$ctx.strategy", "slot_index": "$ctx.slot_index"}),
                ],
                category="visual",
            ),
            SkillDefinition(
                skill_id="visual_style_transfer",
                skill_name="视觉风格迁移",
                description="参考已有高分笔记的视觉风格",
                trigger_keywords=["参考", "风格", "像这个", "类似"],
                agent_role="visual_director",
                workflow_steps=["分析参考图风格", "提取风格特征", "生成迁移建议", "适配到当前场景"],
                executable_steps=[
                    SkillStep(tool_name="analyze_reference_style", description="分析参考风格", arguments={"reference_url": "$ctx.reference_url"}),
                    SkillStep(tool_name="generate_image_briefs", description="生成风格迁移建议", arguments={"plan": "$ctx.plan", "style_reference": "$ctx.style_reference"}),
                ],
                category="visual",
            ),
            SkillDefinition(
                skill_id="compile_asset_bundle",
                skill_name="编译资产包",
                description="从内容计划组装完整资产包",
                trigger_keywords=["组包", "资产包", "导出"],
                agent_role="asset_producer",
                workflow_steps=["收集所有内容元素", "组装资产包", "质量检查"],
                executable_steps=[
                    SkillStep(tool_name="assemble_asset_bundle", description="组装资产包", arguments={"opportunity_id": "$ctx.opportunity_id"}),
                ],
                category="production",
            ),
            SkillDefinition(
                skill_id="batch_variant",
                skill_name="批量变体生成",
                description="从一套资产包快速派生多个变体",
                trigger_keywords=["批量", "变体", "多套", "AB测试"],
                agent_role="asset_producer",
                workflow_steps=["确定变体轴", "生成变体快照", "标注差异", "打包输出"],
                executable_steps=[
                    SkillStep(tool_name="generate_variants", description="生成变体集", arguments={"opportunity_id": "$ctx.opportunity_id", "variant_count": 3}),
                    SkillStep(tool_name="assemble_asset_bundle", description="打包输出", arguments={"opportunity_id": "$ctx.opportunity_id"}),
                ],
                category="production",
            ),
            SkillDefinition(
                skill_id="full_pipeline",
                skill_name="全链路一键策划",
                description="从机会卡到 product-ready 资产的全自动流程",
                trigger_keywords=["一键策划", "全链路", "自动策划"],
                agent_role="lead_agent",
                workflow_steps=["趋势分析", "Brief编译", "模板匹配", "策略生成", "计划编排", "视觉规划", "资产组包"],
                executable_steps=[
                    SkillStep(tool_name="compile_brief", description="编译 Brief", arguments={"card": "$ctx.card"}),
                    SkillStep(tool_name="match_templates", description="模板匹配", arguments={"brief": "$ctx.brief"}),
                    SkillStep(tool_name="generate_strategy", description="策略生成", arguments={"brief": "$ctx.brief", "match_result": "$ctx.match_result"}),
                    SkillStep(tool_name="compile_plan", description="计划编排", arguments={"brief": "$ctx.brief", "strategy": "$ctx.strategy"}),
                    SkillStep(tool_name="generate_image_briefs", description="图片规划", arguments={"plan": "$ctx.plan", "strategy": "$ctx.strategy"}),
                    SkillStep(tool_name="assemble_asset_bundle", description="资产组包", arguments={"opportunity_id": "$ctx.opportunity_id"}),
                ],
                category="orchestration",
            ),
        ]
        for skill in defaults:
            self.register(skill)
        return len(defaults)

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        if condition.endswith("exists"):
            key = condition.replace(" exists", "").strip()
            return key in context
        return True

    def to_openai_schema(self) -> list[dict[str, Any]]:
        """Export skills as OpenAI tool schemas for LLM routing."""
        tools = []
        for skill in self.list_skills():
            tools.append({
                "type": "function",
                "function": {
                    "name": f"skill_{skill.skill_id}",
                    "description": f"{skill.skill_name}: {skill.description}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "context": {"type": "object", "description": "执行上下文"},
                        },
                    },
                },
            })
        return tools

    def reset(self) -> None:
        self._skills.clear()
        self._loaded_from.clear()


# Singleton
skill_registry = SkillRegistry()
skill_registry.load_defaults()
