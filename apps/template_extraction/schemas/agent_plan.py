"""主图策划 Agent 消费的槽位方案与整套主图计划。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImageSlotPlan(BaseModel):
    """单张主图槽位：角色、意图、视觉 brief 与文案/元素约束。"""

    slot_index: int
    role: str
    intent: str
    visual_brief: str
    copy_hints: list[str] = Field(default_factory=list)
    must_include_elements: list[str] = Field(default_factory=list)
    avoid_elements: list[str] = Field(default_factory=list)
    reference_template_fragment: str = ""


class MainImagePlan(BaseModel):
    """匹配到的模板及多张主图槽位列表。"""

    plan_id: str
    template_id: str
    template_name: str
    template_version: str = ""
    priority_axis: str = ""
    matcher_rationale: str = ""
    global_notes: str = ""
    image_slots: list[ImageSlotPlan] = Field(default_factory=list)
