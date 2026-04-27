"""VisualPromptCompiler — CreativeBrief → PromptSpec / NotePack。

承接 docs/SOP_to_content_plan.md 第 11.2-11.3 节。
MVP 仅生成中文 positive / negative；
英文 prompt 与 workflow_json 留空（Phase 4 接入）。

xhs_cover 场景下追加 compile_xhs_pack：单候选 → cover + N body + copy。
每张 body 按 archetype_dim 独立编译，仅取该维度对应的 brief 子集。
"""

from __future__ import annotations

import logging

from apps.growth_lab.schemas.creative_brief import CreativeBrief
from apps.growth_lab.schemas.note_pack import (
    BodyImageSpec,
    CopywritingPack,
    NotePack,
)
from apps.growth_lab.schemas.prompt_spec import (
    PromptGenerationParams,
    PromptProvider,
    PromptSpec,
)
from apps.growth_lab.schemas.strategy_candidate import StrategyCandidate
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore

logger = logging.getLogger(__name__)


_RATIO_TO_DIMS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "3:4": (864, 1152),
    "4:5": (896, 1120),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
}


# 内文 body 的 archetype_dim 默认排布（按封面 archetype 决定 3 张内文风格）
_BODY_DIM_PLAN_BY_ARCHETYPE: dict[str, list[str]] = {
    "function_demo": ["function_demo", "before_after", "lifestyle"],
    "efficacy_proof": ["before_after", "function_demo", "lifestyle"],
    "scene_immersion": ["scene", "lifestyle", "function_demo"],
    "before_after": ["before_after", "function_demo", "lifestyle"],
    "ingredient_proof": ["ingredient", "function_demo", "texture"],
    "lifestyle": ["lifestyle", "scene", "function_demo"],
    "satin_minimal": ["function_demo", "texture", "lifestyle"],
    "warm_kids": ["lifestyle", "scene", "function_demo"],
}

_DEFAULT_BODY_DIMS = ["function_demo", "before_after", "lifestyle"]


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

        provenance = self._brief_field_provenance(cb)
        spec = PromptSpec(
            creative_brief_id=cb.id,
            provider=provider,
            positive_prompt_zh=positive_zh,
            negative_prompt_zh=negative_zh,
            positive_prompt_en="",
            negative_prompt_en="",
            generation_params=gen_params,
            workflow_json={},
            field_provenance=provenance,
        )
        self.store.save_prompt_spec(spec.model_dump())
        return spec

    # ── XHS Note Pack：cover + N body + copy 多 slot ─────────────

    def compile_xhs_pack(
        self,
        *,
        brief: CreativeBrief | dict,
        candidate: StrategyCandidate | dict,
        provider: PromptProvider = "comfyui",
        body_count: int = 3,
    ) -> NotePack:
        """xhs_cover 场景：单候选 → cover + body_N + copy 整篇笔记。

        每张 body 按 archetype_dim 独立编译（function_demo / before_after / lifestyle
        / scene / ingredient / texture）。
        """
        cb = brief if isinstance(brief, CreativeBrief) else CreativeBrief.model_validate(brief)
        cand = (
            candidate
            if isinstance(candidate, StrategyCandidate)
            else StrategyCandidate.model_validate(candidate)
        )

        # 1) cover：保留候选完整变量集
        cover_spec = self.compile(brief=cb, provider=provider)

        # 2) body：按 archetype_dim 各自收窄 brief 后再编译
        plan = _BODY_DIM_PLAN_BY_ARCHETYPE.get(cand.archetype, _DEFAULT_BODY_DIMS)
        body_dims = plan[:body_count] if body_count <= len(plan) else plan + _DEFAULT_BODY_DIMS[: body_count - len(plan)]

        body_specs: list[BodyImageSpec] = []
        for idx, dim in enumerate(body_dims, start=1):
            scoped_brief = self._narrow_brief_for_dim(cb, dim)
            sub_spec = self.compile(brief=scoped_brief, provider=provider)
            body_specs.append(
                BodyImageSpec(
                    slot_id=f"body_{idx}",
                    archetype_dim=dim,  # type: ignore[arg-type]
                    prompt_spec=sub_spec,
                    rationale=self._dim_rationale(dim, cand),
                    rule_refs=list(cand.rule_refs[:5]),
                )
            )

        # 3) copy：CopywritingCompiler 在 routes 层后注入；这里给空壳。
        copy_pack = CopywritingPack()

        # 4) field_provenance：记录每张图主要字段来自哪条 rule_ref / brief 字段
        provenance: dict[str, dict[str, str]] = {
            "cover": cover_spec.field_provenance or {},
        }
        for idx, body in enumerate(body_specs, start=1):
            provenance[f"body_{idx}"] = body.prompt_spec.field_provenance or {
                "archetype_dim": body.archetype_dim,
            }

        pack = NotePack(
            candidate_id=cand.id,
            creative_brief_id=cb.id,
            scene="xhs_cover",
            cover=cover_spec,
            cover_rule_refs=list(cand.rule_refs[:5]),
            body=body_specs,
            copy=copy_pack,
            field_provenance=provenance,
        )
        self.store.save_note_pack(pack.model_dump())
        return pack

    # ── helpers ─────────────────────────────────────────────────

    def _narrow_brief_for_dim(self, brief: CreativeBrief, dim: str) -> CreativeBrief:
        """按 archetype_dim 裁剪 brief，确保每张 body 聚焦一种叙事。"""
        b = brief.model_copy(deep=True)
        if dim == "function_demo":
            b.scene.background = b.scene.background or "纯色棚拍背景，强调产品本体"
            b.scene.environment = "明亮均匀打光，突出功能演示"
            b.product.placement = "中心居中"
            b.product.scale = "占画面 70-80%"
            b.product.angle = "俯视演示"
            b.copywriting.headline = ""
            b.people.enabled = False
        elif dim == "before_after":
            b.scene.background = "左右分屏，左 BEFORE、右 AFTER"
            b.scene.environment = "中性灰底，对比清晰"
            b.product.placement = "左右对称"
            b.product.scale = "各占画面 40%"
            b.product.angle = "正面"
            b.copywriting.headline = "BEFORE / AFTER"
            b.people.enabled = False
        elif dim == "lifestyle":
            b.people.enabled = True
            if not b.people.action:
                b.people.action = "自然使用产品"
            b.scene.background = b.scene.background or "真实家居场景"
            b.scene.environment = b.scene.environment or "自然柔光"
            b.product.placement = "贴近使用者，自然出现"
            b.product.scale = "占画面 30-45%"
            b.copywriting.headline = ""
        elif dim == "scene":
            b.scene.background = b.scene.background or "目标使用场景"
            b.scene.environment = b.scene.environment or "场景化沉浸氛围"
            b.product.placement = "嵌入场景"
            b.product.scale = "占画面 40-55%"
            b.copywriting.headline = ""
        elif dim == "ingredient":
            b.scene.background = "成分平铺/特写底"
            b.scene.environment = "棚拍特写打光"
            b.product.placement = "中心特写"
            b.product.scale = "占画面 60-75%"
            b.product.angle = "微距"
            b.copywriting.headline = "成分公开"
            b.people.enabled = False
        elif dim == "texture":
            b.scene.background = "干净底，强调质感细节"
            b.scene.environment = "侧光强化纹理"
            b.product.placement = "局部特写"
            b.product.scale = "占画面 75-90%"
            b.product.angle = "微距 / 30°"
            b.copywriting.headline = ""
            b.people.enabled = False
        # 共性：body 上少出现主标题，避免与封面重复
        b.copywriting.labels = b.copywriting.labels[:1]
        return b

    def _dim_rationale(self, dim: str, candidate: StrategyCandidate) -> str:
        return {
            "function_demo": f"功能演示张：聚焦 {candidate.name} 的核心使用方式",
            "before_after": "对比张：用前后差距强化卖点说服力",
            "lifestyle": "生活化张：场景真实感，建立代入感",
            "scene": "场景张：用环境放大产品价值",
            "ingredient": "成分/构造特写：建立专业可信",
            "texture": "质感特写：强化产品工艺与品质",
        }.get(dim, dim)

    def _brief_field_provenance(self, brief: CreativeBrief) -> dict[str, str]:
        """从 brief.field_provenance 拷一份；缺失时按字段默认归因。"""
        if brief.field_provenance:
            return dict(brief.field_provenance)
        out: dict[str, str] = {}
        if brief.scene.background:
            out["scene.background"] = "brief.scene.background"
        if brief.product.visible_features:
            out["product.visible_features"] = "brief.product.visible_features"
        if brief.style.tone:
            out["style.tone"] = "brief.style.tone"
        if brief.copywriting.headline:
            out["copywriting.headline"] = "brief.copywriting.headline"
        return out

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
