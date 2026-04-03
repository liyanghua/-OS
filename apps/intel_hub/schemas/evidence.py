"""轻量级证据引用 —— 用于 XHS 三维结构化流水线的来源追溯。

与 evidence_ref.py 中的重型 EvidenceRef 区分：
本模块专注于"这条信号是从笔记的哪个字段、哪段文字中提取的"。
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class XHSEvidenceRef(BaseModel):
    """单条证据引用，追溯到笔记具体字段和片段。"""

    evidence_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_kind: Literal["title", "body", "tag", "image", "comment"] = "body"
    source_ref: str = ""
    snippet: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
