"""Strategy Block Analyzer: Block-level AI operations on strategy objects.

Supports: analyze single block, rewrite block, lock block, compare blocks.
Used by Planning Workspace right-panel AI Inspector when a strategy block is selected.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.schemas.action_spec import ActionSpec

logger = logging.getLogger(__name__)


class StrategyBlock(BaseModel):
    """Single strategy block for block-level operations."""
    block_name: str = ""
    block_type: str = ""  # positioning, hook, tone, scene, cta
    content: str = ""
    locked: bool = False


class BlockAnalysisResult(BaseModel):
    """Analysis result for a single strategy block."""
    block_name: str = ""
    strength: str = ""
    weakness: str = ""
    improvement_suggestions: list[str] = Field(default_factory=list)
    consistency_with_brief: float = 0.0
    actions: list[ActionSpec] = Field(default_factory=list)


class StrategyBlockAnalyzer:
    """Block-level operations on strategy content."""

    def analyze_block(
        self,
        block: StrategyBlock,
        brief_context: str = "",
        opportunity_id: str = "",
    ) -> BlockAnalysisResult:
        """Analyze a single strategy block for quality and consistency."""
        if not block.content:
            return BlockAnalysisResult(
                block_name=block.block_name,
                weakness="内容为空",
                actions=[ActionSpec(
                    action_type="regenerate",
                    target_object="strategy",
                    target_field=block.block_name,
                    label=f"生成 {block.block_name}",
                    api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                )],
            )

        if not llm_router.is_any_available():
            return BlockAnalysisResult(
                block_name=block.block_name,
                strength="内容已填写",
                weakness="无法进行 AI 分析（模型不可用）",
                consistency_with_brief=0.5,
            )

        try:
            resp = llm_router.chat_json(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            "你是策略分析专家。分析以下策略块的质量。返回 JSON："
                            '{"strength":"...","weakness":"...","suggestions":["..."],"brief_consistency":0.0-1.0}'
                        ),
                    ),
                    LLMMessage(
                        role="user",
                        content=f"策略块名称：{block.block_name}\n内容：{block.content}\n\nBrief 上下文：{brief_context[:500]}",
                    ),
                ],
                temperature=0.3,
                max_tokens=800,
            )
        except Exception:
            logger.debug("Block analysis failed", exc_info=True)
            return BlockAnalysisResult(block_name=block.block_name, weakness="分析失败")

        actions: list[ActionSpec] = []
        consistency = float(resp.get("brief_consistency", 0.5))
        if consistency < 0.5:
            actions.append(ActionSpec(
                action_type="refine",
                target_object="strategy",
                target_field=block.block_name,
                label=f"优化 {block.block_name} — 与 Brief 一致性较低",
                api_endpoint=f"/content-planning/run-agent/{opportunity_id}",
                priority=8,
            ))

        return BlockAnalysisResult(
            block_name=block.block_name,
            strength=str(resp.get("strength", "")),
            weakness=str(resp.get("weakness", "")),
            improvement_suggestions=resp.get("suggestions", []),
            consistency_with_brief=consistency,
            actions=actions,
        )

    def rewrite_block(
        self,
        block: StrategyBlock,
        instruction: str = "",
        brief_context: str = "",
    ) -> str:
        """Rewrite a strategy block with optional instruction."""
        if block.locked:
            return block.content

        if not llm_router.is_any_available():
            return block.content

        prompt = f"重写以下策略块内容"
        if instruction:
            prompt += f"，要求：{instruction}"

        try:
            resp = llm_router.chat(
                [
                    LLMMessage(role="system", content=f"{prompt}。只输出重写后的内容文本。"),
                    LLMMessage(
                        role="user",
                        content=f"块名：{block.block_name}\n当前内容：{block.content}\n\nBrief 上下文：{brief_context[:500]}",
                    ),
                ],
                temperature=0.5,
                max_tokens=1000,
            )
            return resp.content.strip() if resp.content else block.content
        except Exception:
            logger.debug("Block rewrite failed", exc_info=True)
            return block.content
