"""VisualPromptCompiler — CreativeBrief → PromptSpec。

承接 docs/SOP_to_content_plan.md 第 11.2-11.3 节。
MVP 仅生成中文 positive / negative；
英文 prompt 与 workflow_json 留空（Phase 4 接入）。
"""

from __future__ import annotations

import logging

from apps.growth_lab.schemas.creative_brief import CreativeBrief
from apps.growth_lab.schemas.prompt_spec import (
    PromptGenerationParams,
    PromptProvider,
    PromptSpec,
)
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore

logger = logging.getLogger(__name__)


_RATIO_TO_DIMS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "3:4": (864, 1152),
    "4:5": (896, 1120),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
}


class VisualPromptCompiler:
    """把 CreativeBrief 翻译为 PromptSpec。"""

    def __init__(self, store: VisualStrategyStore | None = None) -> None:
        self.store = store or VisualStrategyStore()

    def compile(
        self,
        *,
        brief: CreativeBrief | dict,
        provider: PromptProvider = "comfyui",
    ) -> PromptSpec:
        cb = brief if isinstance(brief, CreativeBrief) else CreativeBrief.model_validate(brief)

        positive_zh = self._build_positive_zh(cb)
        negative_zh = self._build_negative_zh(cb)
        gen_params = self._build_generation_params(cb)

        spec = PromptSpec(
            creative_brief_id=cb.id,
            provider=provider,
            positive_prompt_zh=positive_zh,
            negative_prompt_zh=negative_zh,
            positive_prompt_en="",
            negative_prompt_en="",
            generation_params=gen_params,
            workflow_json={},
        )
        self.store.save_prompt_spec(spec.model_dump())
        return spec

    # ── builders ─────────────────────────────────────────────────

    def _build_positive_zh(self, brief: CreativeBrief) -> str:
        parts: list[str] = []

        # 画面比例 + 平台
        parts.append(f"画面比例 {brief.canvas.ratio}，{_platform_label(brief.canvas.platform)}风格")

        # 场景 + 背景
        if brief.scene.background:
            parts.append(f"背景：{brief.scene.background}")
        if brief.scene.environment:
            parts.append(f"环境氛围：{brief.scene.environment}")
        if brief.scene.props:
            parts.append(f"画面元素：{ '、'.join(brief.scene.props) }")

        # 商品
        product_segs: list[str] = []
        if brief.product.placement:
            product_segs.append(f"商品位于{brief.product.placement}")
        if brief.product.scale:
            product_segs.append(brief.product.scale)
        if brief.product.angle:
            product_segs.append(f"{brief.product.angle}视角")
        if brief.product.visible_features:
            product_segs.append(f"突出展示 { '、'.join(brief.product.visible_features) }")
        if product_segs:
            parts.append("，".join(product_segs))

        # 风格
        style_segs: list[str] = []
        if brief.style.tone:
            style_segs.append(f"整体风格 {brief.style.tone}")
        if brief.style.color_palette:
            style_segs.append(f"主色调 { '、'.join(brief.style.color_palette[:4]) }")
        if brief.style.lighting:
            style_segs.append(brief.style.lighting)
        if brief.style.texture:
            style_segs.append(brief.style.texture)
        if style_segs:
            parts.append("，".join(style_segs))

        # 人物
        if brief.people.enabled:
            people_seg = f"画面包含 {brief.people.age} {brief.people.gender or ''}".strip()
            if brief.people.action:
                people_seg += f"，{brief.people.action}"
            if not brief.people.adult_visible:
                people_seg += "，无成年人入镜"
            parts.append(people_seg)
        else:
            parts.append("画面无人物")

        # 文案区
        if brief.copywriting.headline:
            parts.append(f"主文案区域写：「{brief.copywriting.headline}」")
        if brief.copywriting.selling_points:
            parts.append(f"卖点标签：{ '、'.join(brief.copywriting.selling_points[:3]) }")
        if brief.copywriting.labels:
            parts.append(f"差异化标签：{ '、'.join(brief.copywriting.labels[:2]) }")

        # 平台/技术语
        parts.append("高质量电商主图，构图整洁，视觉重点突出")
        return "。".join([p for p in parts if p]) + "。"

    def _build_negative_zh(self, brief: CreativeBrief) -> str:
        if not brief.negative:
            return "低分辨率、模糊、畸变、水印、杂乱"
        return "、".join(brief.negative[:18])

    def _build_generation_params(self, brief: CreativeBrief) -> PromptGenerationParams:
        w, h = _RATIO_TO_DIMS.get(brief.canvas.ratio, (1024, 1024))
        return PromptGenerationParams(
            width=w,
            height=h,
            steps=30,
            cfg_scale=7.0,
            seed=None,
        )


def _platform_label(platform: str) -> str:
    return {
        "taobao_main_image": "淘宝主图",
        "xhs_cover": "小红书封面",
        "detail_first_screen": "详情首屏",
        "video_first_frame": "短视频首帧",
    }.get(platform, "电商视觉")
