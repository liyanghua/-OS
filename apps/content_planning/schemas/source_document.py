"""SourceDocument — 专家 SOP 原始 MD 文档对象。

承接 docs/SOP_to_content_plan.md 第 6.1 节。
按 `assets/SOP/{category_slug}/*.md` 目录约定入库，
文件名前缀编号映射六大维度：
01=visual_core, 02=people_interaction, 03=function_selling_point,
04=pattern_style, 05=marketing_info, 06=differentiation。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

SOPDimension = Literal[
    "visual_core",
    "people_interaction",
    "function_selling_point",
    "pattern_style",
    "marketing_info",
    "differentiation",
]


class SourceDocument(BaseModel):
    """专家 SOP MD 文件——RuleSpec 抽取的源头。"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    category: str = ""
    title: str = ""
    file_name: str = ""
    file_path: str = ""
    dimension: SOPDimension = "visual_core"
    raw_markdown: str = ""
    version: str = "v1"
    status: Literal["uploaded", "parsed", "archived"] = "uploaded"
    parsed_row_count: int = 0
    extracted_rule_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
