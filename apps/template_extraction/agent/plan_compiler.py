"""主图策划方案编译器。"""

from __future__ import annotations

import uuid

from apps.template_extraction.schemas.agent_plan import ImageSlotPlan, MainImagePlan
from apps.template_extraction.schemas.template import (
    CopyRules,
    SceneRules,
    TableclothMainImageStrategyTemplate,
    VisualRules,
)

_SHOT_CN = {
    "topdown": "俯拍/平铺",
    "wide_scene": "广视角餐桌场景",
    "closeup": "特写/近景",
    "detail": "细节特写",
    "lifestyle": "生活方式场景",
    "flatlay": "平铺静物",
}

_ELEM_CN = {
    "tablecloth": "桌布",
    "tableware": "餐具",
    "flowers": "花艺/鲜花",
    "food": "食物",
    "candles": "蜡烛",
    "napkin": "餐巾",
    "plates": "餐盘",
}

_TOKEN_CN = {
    "warm": "暖调",
    "cream": "奶油感",
    "soft": "柔和",
    "natural": "自然光感",
    "cool": "冷调",
    "neutral": "中性",
}


def _shots_phrase(shots: list[str]) -> str:
    if not shots:
        return "按模板推荐景别"
    parts = [_SHOT_CN.get(s, s) for s in shots]
    return "、".join(parts)


def _elems_cn(elems: list[str]) -> str:
    if not elems:
        return ""
    return "、".join(_ELEM_CN.get(e, e) for e in elems)


def _tokens_cn(tokens: list[str]) -> str:
    if not tokens:
        return ""
    return "、".join(_TOKEN_CN.get(t, t) for t in tokens)


def _overlay_cn(level: str) -> str:
    m = {"light": "轻量", "medium": "中等", "heavy": "较重", "none": "无"}
    return m.get(level, level or "轻量")


def _cover_style_cn(style: str) -> str:
    m = {"short": "短句精炼", "medium": "中等篇幅", "long": "可稍长说明", "minimal": "极简"}
    return m.get(style, style or "短句精炼")


def _build_visual_directive(role: str, visual_rules: VisualRules, slot_idx: int) -> str:
    """根据槽位角色与视觉规则生成视觉指令（中文）。"""
    shots = _shots_phrase(visual_rules.preferred_shots)
    req = _elems_cn(visual_rules.required_elements) if visual_rules.required_elements else "桌布清晰可辨"
    opt = _elems_cn(visual_rules.optional_elements[:4]) if visual_rules.optional_elements else ""
    colors = _tokens_cn(visual_rules.color_direction) if visual_rules.color_direction else "柔和统一"
    light = _tokens_cn(visual_rules.lighting_direction) if visual_rules.lighting_direction else "自然柔和"
    overlay = _overlay_cn(visual_rules.text_overlay_level)

    opt_suffix = f"；可搭配{opt}" if opt else ""

    if role in ("cover_hook", "hook_click"):
        return (
            f"封面吸睛：采用{shots}，主体为{req}{opt_suffix}；"
            f"色彩倾向{colors}，光线{light}；文案叠层{overlay}，保证首图点击率与辨识度。"
        )
    if role == "style_expand":
        return (
            f"风格延展（第{slot_idx + 1}张）：强化风格一致性，沿用{shots}；"
            f"突出{req}与整体氛围{opt_suffix}；色彩{colors}，{light}。"
        )
    if role == "texture_expand":
        return (
            f"质感细节（第{slot_idx + 1}张）：以特写呈现织纹/印花/垂感；"
            f"优先{ _SHOT_CN.get('closeup', '特写') }或细节景别；"
            f"桌布占比高、纹理可读；避免过度虚化丢失材质信息{opt_suffix}。"
        )
    if role == "usage_expand":
        return (
            f"使用场景（第{slot_idx + 1}张）：展示真实用餐/布置场景，{shots}；"
            f"包含{req}，生活感强{opt_suffix}；色彩{colors}，{light}。"
        )
    if role == "guide_expand":
        return (
            f"引导转化（第{slot_idx + 1}张）：可含尺寸对比、铺法示意或搭配建议；"
            f"{shots}；信息清晰、减少认知成本；{overlay}文案可点明核心利益点。"
        )
    return (
        f"通用主图（第{slot_idx + 1}张，角色 {role}）：{shots}；"
        f"保证{req}{opt_suffix}；色彩{colors}，{light}，叠层{overlay}。"
    )


def _build_copy_directive(role: str, copy_rules: CopyRules, slot_idx: int) -> str:
    """根据槽位角色与文案规则生成文案指令（中文）。"""
    styles = "、".join(copy_rules.title_style[:3]) if copy_rules.title_style else "突出卖点与场景收益"
    cover_style = _cover_style_cn(copy_rules.cover_copy_style)
    rec = copy_rules.recommended_phrases[:2] if copy_rules.recommended_phrases else []
    rec_seg = f"可参考话术：{'；'.join(rec)}" if rec else "避免空洞口号"

    if role in ("cover_hook", "hook_click"):
        return (
            f"封面文案：{cover_style}；风格取向{styles}。{rec_seg}。"
            f"禁用：{'、'.join(copy_rules.avoid_phrases) if copy_rules.avoid_phrases else '强促销与违规用语'}。"
        )
    if role == "style_expand":
        return f"延展图文案：强调风格标签与氛围词，与封面话术呼应；{styles}。{rec_seg}。"
    if role == "texture_expand":
        return "质感图文案：突出触感、工艺、材质关键词（如厚实、垂坠、清晰印花），少用夸张承诺。"
    if role == "usage_expand":
        return f"场景图文案：描述使用情境与代入感（如早餐、聚会）；{styles}。{rec_seg}。"
    if role == "guide_expand":
        return "引导图文案：明确规格、铺法、搭配或下单理由，语句简短、可扫读。"
    return f"文案：{styles}；{rec_seg}。"


def _build_scene_directive(role: str, scene_rules: SceneRules, slot_idx: int) -> str:
    """根据槽位角色与场景规则生成场景指令（中文）。"""
    must = "必须带可识别的生活场景/餐桌场景。" if scene_rules.must_have_scene else "场景可虚实结合，以商品清晰为先。"
    types = "、".join(scene_rules.scene_types[:4]) if scene_rules.scene_types else "居家餐桌、日常用餐"
    avoid = "、".join(scene_rules.avoid_scenes) if scene_rules.avoid_scenes else "杂乱背景、过度棚拍感"

    if role in ("cover_hook", "hook_click"):
        return f"场景：{must}优先{types}；规避{avoid}。"
    if role == "texture_expand":
        return f"场景：以桌面/局部场景为主即可；{must}若模板要求实景则弱背景突出材质。规避{avoid}。"
    if role == "usage_expand":
        return f"场景：强生活化，{types}；{must}规避{avoid}。"
    if role == "guide_expand":
        return f"场景：简洁干净，信息层级清楚；可与轻场景结合。规避{avoid}。"
    return f"场景：{types}；{must}规避{avoid}。"


def _role_intent_cn(role: str) -> str:
    m = {
        "cover_hook": "封面拉点击与风格第一印象",
        "hook_click": "封面拉点击与风格第一印象",
        "style_expand": "强化风格定锚与系列感",
        "texture_expand": "证明质感与工艺细节",
        "usage_expand": "代入真实使用场景",
        "guide_expand": "降低决策成本、引导转化",
    }
    return m.get(role, f"槽位执行：{role}")


def _copy_hints_from_directive(directive: str) -> list[str]:
    parts = [p.strip() for p in directive.replace("。", "；").split("；") if p.strip()]
    return parts if parts else [directive]


def _global_notes(tpl: TableclothMainImageStrategyTemplate, product_brief: str) -> str:
    bits = [tpl.template_goal]
    if tpl.hook_mechanism:
        bits.append("钩子：" + "；".join(tpl.hook_mechanism[:2]))
    if product_brief:
        bits.append("商品摘要：" + product_brief[:200])
    if tpl.risk_rules:
        bits.append("风险规避：" + "；".join(tpl.risk_rules[:3]))
    return "\n".join(bits)


class MainImagePlanCompiler:
    """将匹配模板编译为 Agent 可消费的 MainImagePlan。"""

    def compile_main_image_plan(
        self,
        matched_template: TableclothMainImageStrategyTemplate,
        opportunity_card: dict | None = None,
        product_brief: str = "",
        matcher_rationale: str = "",
    ) -> MainImagePlan:
        """基于模板 + 机会卡 + 商品信息编译 5 张主图策划方案。"""
        plan_id = uuid.uuid4().hex[:12]

        seq = list(matched_template.image_sequence_pattern or [])
        while len(seq) < 5:
            seq.append("usage_expand")
        seq = seq[:5]

        visual_rules = matched_template.visual_rules
        copy_rules = matched_template.copy_rules
        scene_rules = matched_template.scene_rules

        avoid_pool: list[str] = []
        avoid_pool.extend(scene_rules.avoid_scenes)
        avoid_pool.extend(copy_rules.avoid_phrases)

        image_slots: list[ImageSlotPlan] = []
        for i, role in enumerate(seq):
            vd = _build_visual_directive(role, visual_rules, i)
            cd = _build_copy_directive(role, copy_rules, i)
            sd = _build_scene_directive(role, scene_rules, i)
            visual_brief = f"{vd}\n【场景】{sd}".strip()
            image_slots.append(
                ImageSlotPlan(
                    slot_index=i + 1,
                    role=role,
                    intent=_role_intent_cn(role),
                    visual_brief=visual_brief,
                    copy_hints=_copy_hints_from_directive(cd),
                    must_include_elements=list(visual_rules.required_elements),
                    avoid_elements=list(avoid_pool),
                    reference_template_fragment=f"{matched_template.template_id}#{role}",
                )
            )

        opp_ref = ""
        if opportunity_card:
            opp_ref = str(opportunity_card.get("opportunity_id", "") or "")

        return MainImagePlan(
            plan_id=plan_id,
            template_id=matched_template.template_id,
            template_name=matched_template.template_name,
            template_version=matched_template.template_version,
            priority_axis=matched_template.template_goal,
            matcher_rationale=matcher_rationale,
            global_notes=_global_notes(matched_template, product_brief),
            image_slots=image_slots,
        )
