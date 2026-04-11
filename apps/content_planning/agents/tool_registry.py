"""Unified Tool Registry: Hermes-style ToolEntry + OpenAI schema export + dispatch.

All Agent capabilities (services, adapters, external tools) register here.
LLM receives `to_openai_schema()` as the `tools` parameter; tool_calls come back
and are dispatched via `handle_tool_call()`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolEntry(BaseModel):
    """A registered tool that can be called by Agents or LLMs."""
    name: str
    description: str = ""
    parameters_schema: dict[str, Any] = Field(default_factory=lambda: {
        "type": "object", "properties": {}, "required": [],
    })
    handler: Any = None  # Callable[[dict], Any] -- Pydantic can't validate Callable well
    toolset: str = "default"
    check_fn: Any = None  # Optional availability check
    is_async: bool = False

    model_config = {"arbitrary_types_allowed": True}


class ToolResult(BaseModel):
    """Result of a tool execution."""
    tool_name: str = ""
    output: Any = None
    error: str = ""
    elapsed_ms: int = 0


class ToolRegistry:
    """Central registry for all tools available to Agents."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(self, tool: ToolEntry) -> None:
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (toolset=%s)", tool.name, tool.toolset)

    def register_function(
        self,
        name: str,
        handler: Callable,
        *,
        description: str = "",
        parameters: dict[str, Any] | None = None,
        toolset: str = "default",
        is_async: bool = False,
    ) -> ToolEntry:
        """Convenience: register a plain function as a tool."""
        entry = ToolEntry(
            name=name,
            description=description or (handler.__doc__ or "").strip().split("\n")[0],
            parameters_schema=parameters or {"type": "object", "properties": {}, "required": []},
            handler=handler,
            toolset=toolset,
            is_async=is_async,
        )
        self.register(entry)
        return entry

    def get(self, name: str) -> ToolEntry | None:
        return self._tools.get(name)

    def list_tools(self, *, toolset: str | None = None) -> list[ToolEntry]:
        tools = list(self._tools.values())
        if toolset:
            tools = [t for t in tools if t.toolset == toolset]
        return [t for t in tools if self._is_available(t)]

    def to_openai_schema(self, *, toolset: str | None = None) -> list[dict[str, Any]]:
        """Export tools in OpenAI function-calling format for LLM consumption."""
        schema = []
        for tool in self.list_tools(toolset=toolset):
            schema.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            })
        return schema

    def handle_tool_call(self, name: str, arguments: dict[str, Any] | str) -> Any:
        """Dispatch a tool call by name. Returns result or raises."""
        import time
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        if not self._is_available(tool):
            raise RuntimeError(f"Tool not available: {name}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        t0 = time.perf_counter()
        try:
            result = tool.handler(**arguments) if callable(tool.handler) else None
            elapsed = int((time.perf_counter() - t0) * 1000)
            return ToolResult(tool_name=name, output=result, elapsed_ms=elapsed)
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.warning("Tool %s failed: %s", name, exc, exc_info=True)
            return ToolResult(tool_name=name, error=str(exc), elapsed_ms=elapsed)

    async def ahandle_tool_call(self, name: str, arguments: dict[str, Any] | str) -> Any:
        """Async dispatch. If tool is async, await it; otherwise run in executor."""
        import asyncio
        import time
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        t0 = time.perf_counter()
        try:
            if tool.is_async and callable(tool.handler):
                result = await tool.handler(**arguments)
            elif callable(tool.handler):
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: tool.handler(**arguments))
            else:
                result = None
            elapsed = int((time.perf_counter() - t0) * 1000)
            return ToolResult(tool_name=name, output=result, elapsed_ms=elapsed)
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            return ToolResult(tool_name=name, error=str(exc), elapsed_ms=elapsed)

    def reset(self) -> None:
        self._tools.clear()

    def _is_available(self, tool: ToolEntry) -> bool:
        if tool.check_fn is None:
            return True
        try:
            return bool(tool.check_fn())
        except Exception:
            return False


# Singleton
tool_registry = ToolRegistry()


def register_builtin_tools() -> None:
    """Register all built-in content planning services as tools."""
    try:
        from apps.content_planning.services.brief_compiler import BriefCompiler
        _compiler = BriefCompiler()
        tool_registry.register_function(
            "compile_brief",
            lambda card=None, parsed_note=None, review_summary=None: _compiler.compile(card, parsed_note, review_summary),
            description="将机会卡编译为策划 Brief",
            parameters={"type": "object", "properties": {
                "card": {"type": "object", "description": "机会卡数据"},
                "parsed_note": {"type": "object", "description": "解析后的笔记"},
                "review_summary": {"type": "object", "description": "评审摘要"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register compile_brief", exc_info=True)

    try:
        from apps.content_planning.services.strategy_generator import RewriteStrategyGenerator
        _gen = RewriteStrategyGenerator()
        tool_registry.register_function(
            "generate_strategy",
            lambda brief=None, match_result=None, template=None: _gen.generate(brief, match_result, template),
            description="基于 Brief 和模板生成改写策略",
            parameters={"type": "object", "properties": {
                "brief": {"type": "object"},
                "match_result": {"type": "object"},
                "template": {"type": "object"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register generate_strategy", exc_info=True)

    try:
        from apps.content_planning.services.new_note_plan_compiler import NewNotePlanCompiler
        _plan = NewNotePlanCompiler()
        tool_registry.register_function(
            "compile_plan",
            lambda brief=None, strategy=None, match_result=None, template=None: _plan.compile(brief, strategy, match_result, template),
            description="编译内容计划",
            parameters={"type": "object", "properties": {
                "brief": {"type": "object"},
                "strategy": {"type": "object"},
                "match_result": {"type": "object"},
                "template": {"type": "object"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register compile_plan", exc_info=True)

    try:
        from apps.content_planning.services.title_generator import TitleGenerator
        _title = TitleGenerator()
        tool_registry.register_function(
            "generate_titles",
            lambda plan=None, strategy=None: _title.generate(plan, strategy),
            description="为内容计划生成标题候选",
            parameters={"type": "object", "properties": {
                "plan": {"type": "object"},
                "strategy": {"type": "object"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register generate_titles", exc_info=True)

    try:
        from apps.content_planning.services.body_generator import BodyGenerator
        _body = BodyGenerator()
        tool_registry.register_function(
            "generate_body",
            lambda plan=None, strategy=None: _body.generate(plan, strategy),
            description="为内容计划生成正文草稿",
            parameters={"type": "object", "properties": {
                "plan": {"type": "object"},
                "strategy": {"type": "object"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register generate_body", exc_info=True)

    try:
        from apps.content_planning.services.image_brief_generator import ImageBriefGenerator
        _img = ImageBriefGenerator()
        tool_registry.register_function(
            "generate_image_briefs",
            lambda plan=None, strategy=None: _img.generate(plan, strategy),
            description="为内容计划生成图片执行指令",
            parameters={"type": "object", "properties": {
                "plan": {"type": "object"},
                "strategy": {"type": "object"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register generate_image_briefs", exc_info=True)

    try:
        from apps.content_planning.services.asset_assembler import AssetAssembler
        tool_registry.register_function(
            "assemble_asset_bundle",
            lambda opportunity_id="", plan_id="", titles=None, body=None, image_briefs=None: AssetAssembler.assemble(
                opportunity_id=opportunity_id, plan_id=plan_id,
                titles=titles, body=body, image_briefs=image_briefs),
            description="将标题、正文、图片指令组装为资产包",
            parameters={"type": "object", "properties": {
                "opportunity_id": {"type": "string"},
                "plan_id": {"type": "string"},
                "titles": {"type": "object"},
                "body": {"type": "object"},
                "image_briefs": {"type": "object"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register assemble_asset_bundle", exc_info=True)

    try:
        from apps.template_extraction.agent import TemplateMatcher, TemplateRetriever
        _retriever = TemplateRetriever()
        tool_registry.register_function(
            "list_templates",
            lambda: [{"template_id": getattr(t, "template_id", ""), "label": getattr(t, "label", "")} for t in _retriever.list_templates()],
            description="列出可用模板",
            parameters={"type": "object", "properties": {}},
            toolset="template",
        )
        tool_registry.register_function(
            "match_templates",
            lambda brief=None, top_k=6: TemplateMatcher(_retriever.list_templates()).match_templates(brief=brief, top_k=top_k) if brief else [],
            description="为 Brief 匹配最佳模板",
            parameters={"type": "object", "properties": {
                "brief": {"type": "object"},
                "top_k": {"type": "integer", "default": 6},
            }},
            toolset="template",
        )
    except Exception:
        logger.debug("Failed to register template tools", exc_info=True)

    try:
        from apps.content_planning.services.guardrail_checker import GuardrailChecker
        _guard = GuardrailChecker()
        tool_registry.register_function(
            "check_guardrails",
            lambda text="", brand_id="": _guard.check(text, brand_id=brand_id),
            description="检查内容是否违反品牌 Guardrail 规则",
            parameters={"type": "object", "properties": {
                "text": {"type": "string"},
                "brand_id": {"type": "string"},
            }},
            toolset="governance",
        )
    except Exception:
        logger.debug("Failed to register check_guardrails", exc_info=True)

    tool_registry.register_function(
        "delegate_task",
        lambda agent_role="", task_description="", **kwargs: {"delegated": True, "agent_role": agent_role, "task": task_description},
        description="委派任务给指定角色的子 Agent",
        parameters={"type": "object", "properties": {
            "agent_role": {"type": "string", "description": "目标 Agent 角色"},
            "task_description": {"type": "string", "description": "任务描述"},
        }, "required": ["agent_role"]},
        toolset="orchestration",
    )

    tool_registry.register_function(
        "trigger_pipeline",
        lambda opportunity_id="", execution_mode="deep": {"triggered": True, "opportunity_id": opportunity_id},
        description="触发 Agent 全链路策划管线",
        parameters={"type": "object", "properties": {
            "opportunity_id": {"type": "string"},
            "execution_mode": {"type": "string", "default": "deep"},
        }, "required": ["opportunity_id"]},
        toolset="orchestration",
    )

    try:
        from apps.content_planning.services.publish_formatter import XHSPublishFormatter
        _fmt = XHSPublishFormatter()
        tool_registry.register_function(
            "format_for_publish",
            lambda bundle=None, strategy=None: _fmt.format(bundle, strategy).model_dump(mode="json") if bundle else {},
            description="将 AssetBundle 格式化为可发布的小红书内容包",
            parameters={"type": "object", "properties": {
                "bundle": {"type": "object", "description": "AssetBundle 数据"},
                "strategy": {"type": "object", "description": "改写策略"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register format_for_publish", exc_info=True)

    try:
        from apps.content_planning.services.quality_explainer import QualityExplainer
        _exp = QualityExplainer()
        tool_registry.register_function(
            "explain_quality",
            lambda source_note=None, bundle=None, strategy=None, brief=None: _exp.explain(source_note, bundle, strategy, brief).model_dump(mode="json") if bundle else {},
            description="对比源笔记与生成结果，解释改进点与优化建议",
            parameters={"type": "object", "properties": {
                "source_note": {"type": "object"},
                "bundle": {"type": "object"},
                "strategy": {"type": "object"},
                "brief": {"type": "object"},
            }},
            toolset="content_planning",
        )
    except Exception:
        logger.debug("Failed to register explain_quality", exc_info=True)

    try:
        from apps.content_planning.evaluation.stage_evaluator import evaluate_stage
        tool_registry.register_function(
            "evaluate_stage",
            lambda stage="", opportunity_id="", context=None: evaluate_stage(stage, opportunity_id, context or {}).model_dump(mode="json"),
            description="对指定阶段进行质量评估",
            parameters={"type": "object", "properties": {
                "stage": {"type": "string", "description": "阶段名: brief/strategy/plan/asset"},
                "opportunity_id": {"type": "string"},
                "context": {"type": "object"},
            }, "required": ["stage", "opportunity_id"]},
            toolset="evaluation",
        )
    except Exception:
        logger.debug("Failed to register evaluate_stage", exc_info=True)

    logger.info("Registered %d built-in tools", len(tool_registry._tools))
