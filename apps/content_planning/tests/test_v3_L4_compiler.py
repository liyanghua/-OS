"""L4 Compiler OS: HealthChecker, StrategyBlockAnalyzer, AssetBundle."""

from __future__ import annotations

from apps.content_planning.agents.health_checker import HealthChecker
from apps.content_planning.agents.strategy_block_analyzer import (
    BlockAnalysisResult,
    StrategyBlock,
    StrategyBlockAnalyzer,
)
from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.image_execution_brief import ImageExecutionBrief


def test_check_brief_health_well_formed_score_above_half() -> None:
    brief = {
        "target_user": "都市白领",
        "content_goal": "种草转化",
        "primary_value": "高性价比",
        "target_scene": "通勤",
        "visual_style_direction": ["极简"],
        "avoid_directions": ["低价感"],
        "why_now": "换季需求",
    }
    result = HealthChecker().check_brief_health(brief)
    assert result.score > 0.5
    assert "issues" in result.model_dump()


def test_brief_with_target_scene_audience_core_fields_is_healthy() -> None:
    """Brief 含目标场景、受众与核心价值相关字段；与 HealthChecker 必填/可选对齐。"""
    brief = {
        "target_user": "精致宝妈",
        "target_scene": "早餐餐桌",
        "target_audience": "25-35 岁女性",
        "content_goal": "提升品牌认知",
        "primary_value": "氛围感 + 易打理",
        "core_selling_points": "防水、出片",
        "visual_style_direction": ["奶油风"],
        "avoid_directions": ["廉价感"],
        "why_now": "春季上新",
    }
    result = HealthChecker().check_brief_health(brief)
    assert result.is_healthy
    assert not result.has_errors


def test_strategy_block_analyzer_instantiate_and_analyze() -> None:
    analyzer = StrategyBlockAnalyzer()
    block = StrategyBlock(block_name="tone", block_type="tone", content="professional")
    out = analyzer.analyze_block(block)
    assert isinstance(out, BlockAnalysisResult)
    assert out.block_name == "tone"


def test_rewrite_block_returns_string() -> None:
    analyzer = StrategyBlockAnalyzer()
    block = StrategyBlock(block_name="tone", block_type="tone", content="original")
    text = analyzer.rewrite_block(block, instruction="更活泼")
    assert isinstance(text, str)
    assert len(text) >= 0


def test_analyze_locked_block_still_works() -> None:
    analyzer = StrategyBlockAnalyzer()
    block = StrategyBlock(
        block_name="tone",
        block_type="tone",
        content="locked tone",
        locked=True,
    )
    out = analyzer.analyze_block(block)
    assert isinstance(out, BlockAnalysisResult)
    rewritten = analyzer.rewrite_block(block, instruction="改掉")
    assert rewritten == block.content


def test_asset_bundle_required_shape_and_image_briefs_mixed_types() -> None:
    typed = ImageExecutionBrief(
        slot_index=0,
        opportunity_id="opp-1",
        role="hero",
        intent="展示产品",
        subject="产品主体",
        composition="居中",
        visual_brief="柔光",
        copy_hints="标题区留白",
        props=["桌布"],
        text_overlay="新品",
        color_mood="暖色",
        avoid_items=["杂乱背景"],
    )
    bundle = AssetBundle(
        opportunity_id="opp-1",
        plan_id="plan-1",
        title_candidates=[{"text": "标题 A"}],
        body_outline=["段1"],
        body_draft="正文草稿",
        image_execution_briefs=[
            {"slot_index": 0, "role": "dict-slot", "intent": "from dict"},
            typed,
        ],
    )
    assert len(bundle.image_execution_briefs) == 2
    first = bundle.image_execution_briefs[0]
    assert isinstance(first, (dict, ImageExecutionBrief))
    assert isinstance(bundle.image_execution_briefs[1], ImageExecutionBrief)


def test_asset_bundle_typed_brief_preserves_fields() -> None:
    typed = ImageExecutionBrief(
        brief_id="fixed-brief-id",
        slot_index=2,
        opportunity_id="o99",
        plan_id="p99",
        strategy_id="s99",
        template_id="t99",
        role="detail",
        intent="细节特写",
        subject="纹理",
        composition="对角线",
        visual_brief="微距",
        copy_hints="无字",
        props=[],
        text_overlay="",
        color_mood="中性",
        avoid_items=["过曝"],
        status="approved",
    )
    bundle = AssetBundle(
        opportunity_id="o99",
        image_execution_briefs=[typed],
    )
    dumped = bundle.model_dump(mode="json")
    ib = dumped["image_execution_briefs"][0]
    assert ib["brief_id"] == "fixed-brief-id"
    assert ib["slot_index"] == 2
    assert ib["opportunity_id"] == "o99"
    assert ib["plan_id"] == "p99"
    assert ib["strategy_id"] == "s99"
    assert ib["template_id"] == "t99"
    assert ib["role"] == "detail"
    assert ib["intent"] == "细节特写"
    assert ib["status"] == "approved"
