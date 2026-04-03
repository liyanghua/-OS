"""跨模态校验结果 Schema —— 视觉/文本/评论之间的一致性校验。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from apps.intel_hub.schemas.evidence import XHSEvidenceRef


class CrossModalValidation(BaseModel):
    """跨模态一致性校验结果。

    不做信号提取，只检查三个维度结果之间的一致性：
    - 文本卖点是否被图片支持
    - 文本承诺是否被评论验证/质疑
    - 场景在标题/图片/评论间是否一致
    """

    note_id: str = ""

    selling_claim_visual_support: dict[str, bool | str] = Field(
        default_factory=dict,
        description='例如 {"显高级": true, "防水": false, "出片": "uncertain"}',
    )
    selling_claim_comment_validation: dict[str, bool | str] = Field(
        default_factory=dict,
        description='例如 {"好打理": true, "防水": "uncertain"}',
    )
    scene_alignment: dict[str, bool | str] = Field(
        default_factory=dict,
        description='例如 {"title_scene_matches_visual_scene": true}',
    )

    overall_consistency_score: float | None = None

    unsupported_claims: list[str] = Field(default_factory=list)
    challenged_claims: list[str] = Field(default_factory=list)
    high_confidence_claims: list[str] = Field(default_factory=list)

    evidence_refs: list[XHSEvidenceRef] = Field(default_factory=list)
