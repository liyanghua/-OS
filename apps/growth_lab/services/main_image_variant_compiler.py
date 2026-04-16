"""MainImageVariantCompiler：卖点规格 × 变量矩阵 → 主图裂变版本列表。

将 SellingPointSpec 与变量组合（模特/构图/场景/字卡/色彩/风格）交叉编译，
为每个组合生成 ImageVariantSpec 并封装为 MainImageVariant。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.growth_lab.schemas.main_image_variant import (
    ImageVariantSpec,
    MainImageVariant,
    VariantVariable,
)

logger = logging.getLogger(__name__)

_DIMENSION_PROMPT_MAP: dict[str, str] = {
    "model_face": "模特面部",
    "hair_style": "发型",
    "hair_color": "发色",
    "composition": "构图",
    "close_up_detail": "特写细节",
    "scene_background": "场景背景",
    "benefit_card": "利益点字卡",
    "color_style": "色彩风格",
    "stimulation_level": "刺激强度",
}


class MainImageVariantCompiler:
    """卖点 × 变量矩阵 → MainImageVariant 列表编译器。"""

    def compile_matrix(
        self,
        spec: dict,
        variable_matrix: list[list[dict]],
        *,
        platform: str = "",
        sku_id: str = "",
        workspace_id: str = "",
        brand_id: str = "",
    ) -> list[MainImageVariant]:
        """将 spec（SellingPointSpec dict）与变量矩阵交叉编译。

        variable_matrix 中每个元素是一组 VariantVariable dict 列表，
        代表一个测试组合。
        """
        core_claim = spec.get("core_claim", "")
        supporting = spec.get("supporting_claims", [])
        shelf = spec.get("shelf_expression") or {}
        spec_id = spec.get("spec_id", "")
        source_opp_id = (spec.get("source_opportunity_ids") or [""])[0]

        base_prompt = self._build_base_prompt(core_claim, supporting, shelf)

        variants: list[MainImageVariant] = []
        for combo in variable_matrix:
            parsed_vars = self._parse_variables(combo)
            image_spec = self._build_image_spec(base_prompt, parsed_vars, platform)
            variant = MainImageVariant(
                source_selling_point_id=spec_id,
                source_opportunity_id=source_opp_id,
                platform=platform,
                sku_id=sku_id,
                key_variables=parsed_vars,
                image_variant_spec=image_spec,
                expected_goal=f"验证: {self._combo_label(parsed_vars)}",
                workspace_id=workspace_id,
                brand_id=brand_id,
                status="draft",
            )
            variants.append(variant)

        logger.info(
            "编译完成: %d 个变量组合 → %d 个主图裂变版本",
            len(variable_matrix), len(variants),
        )
        return variants

    # ── 内部方法 ──

    @staticmethod
    def _build_base_prompt(
        core_claim: str,
        supporting: list[str],
        shelf: dict[str, Any],
    ) -> str:
        parts: list[str] = []
        if shelf.get("headline"):
            parts.append(shelf["headline"])
        if core_claim:
            parts.append(core_claim)
        for s in supporting[:2]:
            if s:
                parts.append(s)
        if shelf.get("visual_direction"):
            parts.append(shelf["visual_direction"])
        return ", ".join(p for p in parts if p)

    @staticmethod
    def _parse_variables(combo: list[dict]) -> list[VariantVariable]:
        parsed: list[VariantVariable] = []
        for v in combo:
            try:
                parsed.append(VariantVariable(**v))
            except Exception:
                logger.debug("跳过无法解析的变量: %s", v)
        return parsed

    @staticmethod
    def _build_image_spec(
        base_prompt: str,
        variables: list[VariantVariable],
        platform: str,
    ) -> ImageVariantSpec:
        var_parts: list[str] = []
        style_tags: list[str] = []
        for v in variables:
            if v.value and not v.locked:
                label = _DIMENSION_PROMPT_MAP.get(v.dimension, v.label or v.dimension)
                var_parts.append(f"{label}: {v.value}")
            if v.dimension == "color_style" and v.value:
                style_tags.append(v.value)

        full_prompt = base_prompt
        if var_parts:
            full_prompt = f"{base_prompt}, {', '.join(var_parts)}"

        size = "800*800" if platform in ("taobao", "jd", "shelf") else "1024*1024"

        return ImageVariantSpec(
            variables=variables,
            base_prompt=full_prompt,
            style_tags=style_tags,
            size=size,
        )

    @staticmethod
    def _combo_label(variables: list[VariantVariable]) -> str:
        labels = [
            f"{_DIMENSION_PROMPT_MAP.get(v.dimension, v.dimension)}={v.value}"
            for v in variables
            if v.value and not v.locked
        ]
        return " + ".join(labels[:4]) if labels else "默认组合"
