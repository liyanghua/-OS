"""TestTask / ResultSnapshot / AmplificationPlan — 测试放大板核心对象。

把创意版本对象转成经营动作对象：测试 -> 看结果 -> 停/放大/再裂变。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TestTask(BaseModel):
    """测试任务——版本上架测试的管理单元。"""

    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_variant_id: str = ""
    variant_type: Literal["main_image", "first3s"] = "main_image"

    platform: str = ""
    store_id: str = ""
    link_id: str = ""
    sku_id: str = ""

    test_window_days: int = 7
    metrics_to_watch: list[str] = Field(
        default_factory=lambda: ["ctr", "traffic", "refund_rate"],
    )
    baseline_refs: list[str] = Field(default_factory=list)
    decision_rule: str = ""
    owner: str = ""

    # B2B 上下文
    workspace_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""

    status: Literal[
        "draft", "active", "observing", "stopped",
        "amplified", "re_variant",
    ] = "draft"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResultSnapshot(BaseModel):
    """结果快照——测试任务在某个时间点的业务指标。"""

    snapshot_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_id: str = ""
    date: str = ""

    ctr: float | None = None
    traffic: int | None = None
    conversion_rate: float | None = None
    refund_rate: float | None = None
    save_rate: float | None = None
    comments_signal: str = ""
    overall_result: Literal[
        "excellent", "good", "neutral", "poor", "pending",
    ] = "pending"
    baseline_delta: dict[str, float] = Field(default_factory=dict)

    notes: str = ""
    raw_data: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AmplificationPlan(BaseModel):
    """放大计划——基于测试结果的下一步行动方案。"""

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    based_on_task_id: str = ""

    amplification_type: Literal[
        "original_link_scale",
        "same_product_variant",
        "cross_platform_migration",
        "new_hook_variant",
    ] = "original_link_scale"

    recommended_actions: list[str] = Field(default_factory=list)
    next_variant_ids: list[str] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"] = "medium"
    expected_risk: str = ""

    # B2B 上下文
    workspace_id: str = ""
    brand_id: str = ""

    status: Literal[
        "proposed", "approved", "executing", "completed", "cancelled",
    ] = "proposed"

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
