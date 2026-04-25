"""RulePack — 类目级规则包。

承接 docs/SOP_to_content_plan.md 第 6.3 节，但做出关键调整：
StrategyArchetype 不再是硬编码 enum，改由 RulePack 自带
`default_strategy_archetypes: list[ArchetypeConfig]`，让每类目
可以定义自己数量与命名的 archetype。这是"扩品类、扩场景、
沉淀行业 know-how"的关键扩展位。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ArchetypeConfig(BaseModel):
    """单个策略原型——RulePack 自带的"6 类策略"模板。

    儿童桌垫默认有 safe_eye_care / child_engagement / warm_low_age /
    premium_texture / function_demo / differentiation_breakthrough；
    其它类目可以定义自己的 archetype slug 与中文名。
    """

    slug: str = ""
    name: str = ""
    hypothesis: str = ""
    target_audience: list[str] = Field(default_factory=list)
    preferred_keywords: dict[str, list[str]] = Field(default_factory=dict)
    avoid_keywords: list[str] = Field(default_factory=list)


class RulePackMetrics(BaseModel):
    rule_count: int = 0
    approved_rule_count: int = 0
    avg_confidence: float = 0.0


class RulePack(BaseModel):
    """类目级别的规则包——StrategyCompiler 的输入。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    category: str = ""
    name: str = ""
    version: str = "v1"
    description: str = ""
    dimensions: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    default_strategy_archetypes: list[ArchetypeConfig] = Field(default_factory=list)
    status: Literal["draft", "active", "archived"] = "draft"
    metrics: RulePackMetrics = Field(default_factory=RulePackMetrics)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# 儿童桌垫的默认 archetype 定义（v1 内置；后续类目可在 RulePack 创建时覆盖）
CHILDREN_DESK_MAT_ARCHETYPES: list[ArchetypeConfig] = [
    ArchetypeConfig(
        slug="safe_eye_care",
        name="安全护眼型",
        hypothesis="宝妈优先点击安全、护眼、干净、有质感的主图",
        target_audience=["宝妈", "幼儿园-小学家长"],
        preferred_keywords={
            "function_selling_point": ["食品级", "护眼", "无异味", "柔光"],
            "pattern_style": ["清新森系", "局部印花", "明亮通透"],
            "people_interaction": ["无人物", "专注书写"],
        },
        avoid_keywords=["满印卡通", "强促销"],
    ),
    ArchetypeConfig(
        slug="child_engagement",
        name="儿童代入型",
        hypothesis="儿童使用者代入感强，画面里有同龄人书写互动",
        target_audience=["7岁以上儿童", "小学高年级"],
        preferred_keywords={
            "people_interaction": ["儿童专注书写", "同龄人代入"],
            "pattern_style": ["轻童趣", "温和图案"],
        },
        avoid_keywords=["成人监督", "家长出镜"],
    ),
    ArchetypeConfig(
        slug="warm_low_age",
        name="低龄温馨型",
        hypothesis="6 岁以下宝妈决策，画面温馨可爱、有家长陪伴感",
        target_audience=["3-6 岁宝妈"],
        preferred_keywords={
            "people_interaction": ["低龄画画", "家长陪伴"],
            "pattern_style": ["温馨可爱", "马卡龙色"],
        },
        avoid_keywords=["纯功能演示", "冷调高级感"],
    ),
    ArchetypeConfig(
        slug="premium_texture",
        name="高端质感型",
        hypothesis="差异化高端店铺，强调材质与极简画面",
        target_audience=["高客单宝妈", "品质偏好用户"],
        preferred_keywords={
            "visual_core": ["极简", "高级感", "纯色背景"],
            "function_selling_point": ["食品级硅胶", "材质升级"],
        },
        avoid_keywords=["低价促销", "杂乱"],
    ),
    ArchetypeConfig(
        slug="function_demo",
        name="功能演示型",
        hypothesis="易清洁、防水、防卷边等功能场景演示",
        target_audience=["实用偏好用户"],
        preferred_keywords={
            "function_selling_point": ["防水", "一擦即净", "防卷边", "耐磨"],
            "pattern_style": ["真实清晰", "功能演示"],
            "people_interaction": ["无人物"],
        },
        avoid_keywords=["夸张对比", "过度摆拍"],
    ),
    ArchetypeConfig(
        slug="differentiation_breakthrough",
        name="差异突围型",
        hypothesis="同行多用满印卡通，我用森系叶子留白突破同质化",
        target_audience=["品味宝妈"],
        preferred_keywords={
            "differentiation": ["森系场景", "局部留白", "类目专属"],
            "pattern_style": ["局部印花", "森系叶子"],
        },
        avoid_keywords=["满印卡通", "高饱和", "同质化纯色背景"],
    ),
]
