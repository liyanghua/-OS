"""VisualBriefCompiler — StrategyCandidate → CreativeBrief。

承接 docs/SOP_to_content_plan.md 第 11.1 节。
取候选选定的维度变量 + ContextSpec 商品/店铺/平台 信息，
组装成可编辑的生图策划案。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.schemas.context_spec import ContextSpec
from apps.growth_lab.schemas.creative_brief import (
    BriefCanvas,
    BriefCopywriting,
    BriefPeople,
    BriefProduct,
    BriefScene,
    BriefStyle,
    CreativeBrief,
)
from apps.growth_lab.schemas.strategy_candidate import StrategyCandidate
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore

logger = logging.getLogger(__name__)


_RATIO_BY_SCENE: dict[str, str] = {
    "taobao_main_image": "1:1",
    "xhs_cover": "3:4",
    "detail_first_screen": "1:1",
    "video_first_frame": "9:16",
}

_DEFAULT_NEGATIVE: list[str] = [
    "低分辨率", "畸变", "杂乱", "水印", "logo冲突",
    "比例失真", "夸张促销标签", "过度饱和",
]


class VisualBriefCompiler:
    """把单个 StrategyCandidate 编译成 CreativeBrief。"""

    def __init__(self, store: VisualStrategyStore | None = None) -> None:
        self.store = store or VisualStrategyStore()

    def compile(
        self,
        *,
        candidate: StrategyCandidate | dict,
        context: ContextSpec | dict,
        overrides: dict[str, Any] | None = None,
    ) -> CreativeBrief:
        cand = candidate if isinstance(candidate, StrategyCandidate) else StrategyCandidate.model_validate(candidate)
        ctx = context if isinstance(context, ContextSpec) else ContextSpec.model_validate(context)

        canvas = self._build_canvas(ctx)
        scene = self._build_scene(cand, ctx)
        product = self._build_product(cand, ctx)
        style = self._build_style(cand, ctx)
        people = self._build_people(cand)
        copywriting = self._build_copywriting(cand, ctx)
        negative = self._build_negative(cand, ctx)

        brief = CreativeBrief(
            strategy_candidate_id=cand.id,
            canvas=canvas,
            scene=scene,
            product=product,
            style=style,
            people=people,
            copywriting=copywriting,
            negative=negative,
        )

        if overrides:
            self._apply_overrides(brief, overrides)

        self.store.save_creative_brief(brief.model_dump())

        # 回写 candidate 的 brief id
        cand.creative_brief_id = brief.id
        self.store.save_strategy_candidate(cand.model_dump())
        return brief

    # ── builders ─────────────────────────────────────────────────

    def _build_canvas(self, ctx: ContextSpec) -> BriefCanvas:
        ratio = _RATIO_BY_SCENE.get(ctx.scene, "1:1")
        text_area = "right" if ratio == "1:1" else "bottom"
        return BriefCanvas(
            ratio=ratio,  # type: ignore[arg-type]
            platform=ctx.scene,
            text_area=text_area,  # type: ignore[arg-type]
            product_visibility_min=ctx.platform.product_visibility_min,
        )

    def _build_scene(self, cand: StrategyCandidate, ctx: ContextSpec) -> BriefScene:
        visual_block = cand.selected_variables.visual_core or {}
        background = (
            visual_block.get("option_name")
            or visual_block.get("variable_name")
            or "明亮通透的纯色背景"
        )
        environment = ctx.store_visual_system.image_tone or "明亮自然光"
        allowed = ctx.store_visual_system.allowed_elements or []
        forbidden = list({*ctx.store_visual_system.avoid_elements, *_pull_avoid(cand)})
        return BriefScene(
            background=str(background),
            environment=environment,
            props=list(allowed)[:4],
            forbidden_props=list(forbidden),
        )

    def _build_product(self, cand: StrategyCandidate, ctx: ContextSpec) -> BriefProduct:
        fn_block = cand.selected_variables.function_selling_point or {}
        diff_block = cand.selected_variables.differentiation or {}
        visible: list[str] = []
        for block in (fn_block, diff_block):
            for key in ("option_name", "variable_name"):
                v = block.get(key)
                if v:
                    visible.append(str(v))
                    break
        if ctx.product.material:
            visible.append(ctx.product.material)
        return BriefProduct(
            placement="中心偏右" if ctx.scene == "taobao_main_image" else "中心",
            scale="占画面 65-75%" if ctx.scene == "taobao_main_image" else "占画面 55-65%",
            angle="俯视 35°" if "演示" in str(visible) else "正面",
            visible_features=list(dict.fromkeys(visible))[:4],
        )

    def _build_style(self, cand: StrategyCandidate, ctx: ContextSpec) -> BriefStyle:
        pattern_block = cand.selected_variables.pattern_style or {}
        tone = (
            ctx.store_visual_system.style
            or str(pattern_block.get("variable_name") or pattern_block.get("option_name") or "")
            or "森系明亮"
        )
        return BriefStyle(
            tone=tone,
            color_palette=list(ctx.store_visual_system.colors) or ["奶白", "浅灰", "森绿"],
            lighting="自然柔光" if "森" in tone or "明亮" in tone else "棚灯均匀光",
            texture="硅胶细腻颗粒感" if ctx.product.material else "中等质感",
        )

    def _build_people(self, cand: StrategyCandidate) -> BriefPeople:
        people_block = cand.selected_variables.people_interaction or {}
        if not people_block:
            return BriefPeople(enabled=False)
        text = " ".join(str(v) for v in people_block.values() if v)
        if "无人" in text or "无人物" in text:
            return BriefPeople(enabled=False)
        age = "7-12岁" if "小学" in text else ("3-6岁" if "低龄" in text else "学龄儿童")
        gender = "中性"
        action = str(people_block.get("option_name") or people_block.get("variable_name") or "专注书写")
        adult_visible = "家长" in text or "陪伴" in text
        return BriefPeople(
            enabled=True,
            age=age,
            gender=gender,
            action=action,
            adult_visible=adult_visible,
        )

    def _build_copywriting(self, cand: StrategyCandidate, ctx: ContextSpec) -> BriefCopywriting:
        marketing_block = cand.selected_variables.marketing_info or {}
        headline = str(marketing_block.get("option_name") or marketing_block.get("variable_name") or "")
        if not headline and ctx.extra.get("hook"):
            headline = str(ctx.extra.get("hook"))
        selling = list(ctx.product.claims)[: ctx.platform.copy_limit]
        labels: list[str] = []
        diff_block = cand.selected_variables.differentiation or {}
        if diff_block.get("option_name"):
            labels.append(str(diff_block["option_name"]))
        return BriefCopywriting(
            headline=headline[:24],
            selling_points=selling,
            labels=labels[:2],
            price_visible=False,
        )

    def _build_negative(self, cand: StrategyCandidate, ctx: ContextSpec) -> list[str]:
        negatives = list(_DEFAULT_NEGATIVE)
        negatives.extend(ctx.store_visual_system.avoid_elements)
        for dim in (
            "visual_core", "people_interaction", "function_selling_point",
            "pattern_style", "marketing_info", "differentiation",
        ):
            block = getattr(cand.selected_variables, dim, {}) or {}
            negatives.extend(block.get("must_avoid", []) or [])
        deduped: list[str] = []
        for n in negatives:
            n = str(n).strip()
            if n and n not in deduped:
                deduped.append(n)
        return deduped[:18]

    def _apply_overrides(self, brief: CreativeBrief, overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            if not hasattr(brief, key) or value is None:
                continue
            current = getattr(brief, key)
            if hasattr(current, "model_copy") and isinstance(value, dict):
                setattr(brief, key, current.model_copy(update=value))
            else:
                setattr(brief, key, value)


def _pull_avoid(cand: StrategyCandidate) -> list[str]:
    avoid: list[str] = []
    for dim in (
        "visual_core", "people_interaction", "function_selling_point",
        "pattern_style", "marketing_info", "differentiation",
    ):
        block = getattr(cand.selected_variables, dim, {}) or {}
        avoid.extend(block.get("must_avoid", []) or [])
    return avoid
