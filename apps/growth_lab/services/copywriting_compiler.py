"""CopywritingCompiler — CreativeBrief × StrategyCandidate → CopywritingPack。

承接「视觉产线分流 + 小红书封面联动」plan 第 2.2 节。
xhs_cover 场景下，单个候选展开成「整篇笔记」时需要标题 + 正文 + hashtag 文案。

MVP 走模板兜底；预留 LLM hook（关闭时使用确定性模板）。
模板按 archetype 选择，确保候选 ribbon 切换时文案风格一致变化。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.growth_lab.schemas.creative_brief import CreativeBrief
from apps.growth_lab.schemas.note_pack import CopywritingPack
from apps.growth_lab.schemas.strategy_candidate import StrategyCandidate

logger = logging.getLogger(__name__)


_HEADLINE_TEMPLATE_BY_ARCHETYPE: dict[str, str] = {
    "function_demo": "{product}｜{point}的真实演示",
    "efficacy_proof": "{point}！{product}用了{duration}的真实变化",
    "scene_immersion": "{scene}场景里的{product}：{point}",
    "before_after": "对比图｜{product}用前 VS 用后{point}",
    "ingredient_proof": "成分党测评 | {product} {point} 全公开",
    "lifestyle": "我的{scene}日常 | {product} 真的{point}",
    "satin_minimal": "极简风｜{product} 一物多用",
    "warm_kids": "宝妈实测｜{product} {point}",
}

_BODY_TEMPLATE = (
    "「{headline}」\n\n"
    "🌟 {hook}\n\n"
    "{value_props}\n"
    "\n关键卖点：\n{points_block}\n"
    "\n{cta}"
)


class CopywritingCompiler:
    """生成笔记标题 + 正文 + hashtag。"""

    def __init__(self, *, llm_client: Any | None = None) -> None:
        # llm_client 预留位：关闭时只走模板。
        self.llm_client = llm_client

    def compile(
        self,
        *,
        brief: CreativeBrief,
        candidate: StrategyCandidate,
    ) -> CopywritingPack:
        archetype = candidate.archetype or "function_demo"
        product = self._resolve_product(brief, candidate)
        point = self._resolve_main_point(brief, candidate)
        scene = brief.scene.background or brief.scene.environment or "日常"
        duration = "7天" if "效" in (point + archetype) else "一周"

        headline_template = _HEADLINE_TEMPLATE_BY_ARCHETYPE.get(
            archetype, _HEADLINE_TEMPLATE_BY_ARCHETYPE["function_demo"]
        )
        headline = headline_template.format(
            product=product, point=point, scene=scene, duration=duration
        )
        if brief.copywriting.headline:
            headline = brief.copywriting.headline

        hook = self._build_hook(brief, archetype, point)
        value_props = self._build_value_props(brief)
        points_block = self._build_points_block(brief)
        cta = self._build_cta(archetype, brief)

        body_text = _BODY_TEMPLATE.format(
            headline=headline,
            hook=hook,
            value_props=value_props,
            points_block=points_block,
            cta=cta,
        )

        hashtags = self._build_hashtags(brief, candidate, archetype)

        field_source: dict[str, str] = {
            "headline": (
                "brief.copywriting.headline"
                if brief.copywriting.headline
                else f"archetype_template:{archetype}"
            ),
            "body_text": "template_body",
            "value_props": "brief.copywriting.selling_points",
            "cta": f"archetype_cta:{archetype}",
            "hashtags": "brief.style+selling_points",
        }
        for r in candidate.rule_refs[:3]:
            field_source.setdefault(f"rule_ref:{r}", r)

        return CopywritingPack(
            headline=headline.strip()[:32],
            body_text=body_text.strip(),
            hashtags=hashtags,
            field_source=field_source,
        )

    # ── helpers ─────────────────────────────────────────────────

    def _resolve_product(self, brief: CreativeBrief, candidate: StrategyCandidate) -> str:
        for v in (brief.product.visible_features or []):
            if v:
                return v[:8]
        if candidate.name:
            return candidate.name[:8]
        return "新品"

    def _resolve_main_point(self, brief: CreativeBrief, candidate: StrategyCandidate) -> str:
        if brief.copywriting.selling_points:
            return brief.copywriting.selling_points[0][:8]
        diff = (candidate.selected_variables.differentiation or {}).get("option_name")
        if diff:
            return str(diff)[:8]
        fn = (candidate.selected_variables.function_selling_point or {}).get("option_name")
        if fn:
            return str(fn)[:8]
        return "好用"

    def _build_hook(self, brief: CreativeBrief, archetype: str, point: str) -> str:
        if archetype.startswith("before_after"):
            return f"亲测对比，{point}差距太大了！"
        if "scene" in archetype or archetype == "lifestyle":
            return f"在{brief.scene.background or '日常场景'}里，{point}是真的很顶。"
        if "ingredient" in archetype:
            return f"成分党友友们注意，{point}经得起放大看。"
        return f"如果你也在意{point}，这一篇请认真看完。"

    def _build_value_props(self, brief: CreativeBrief) -> str:
        if not brief.copywriting.selling_points:
            return ""
        lines = []
        for sp in brief.copywriting.selling_points[:3]:
            lines.append(f"✓ {sp}")
        return "\n".join(lines)

    def _build_points_block(self, brief: CreativeBrief) -> str:
        items = list(brief.copywriting.selling_points[:3])
        items.extend(brief.copywriting.labels[:2])
        if not items:
            items = ["真实使用感受", "性价比突出"]
        return "\n".join(f"· {it}" for it in items if it)

    def _build_cta(self, archetype: str, brief: CreativeBrief) -> str:
        if "before_after" in archetype:
            return "📌 评论区告诉我你最关心哪一点～"
        if "ingredient" in archetype:
            return "📌 想看完整成分表的扣 1～"
        if "lifestyle" in archetype:
            return "📌 收藏起来不迷路 👇"
        return "📌 有问题评论区扣我，看到必回。"

    def _build_hashtags(
        self,
        brief: CreativeBrief,
        candidate: StrategyCandidate,
        archetype: str,
    ) -> list[str]:
        tags: list[str] = []
        for sp in brief.copywriting.selling_points[:2]:
            tags.append(f"#{sp.strip().replace(' ', '')}")
        for label in brief.copywriting.labels[:2]:
            if label:
                tags.append(f"#{label.strip().replace(' ', '')}")
        if brief.style.tone:
            tags.append(f"#{brief.style.tone.strip().replace(' ', '')}")
        tags.append(f"#{archetype}")
        deduped: list[str] = []
        for t in tags:
            if t and t not in deduped:
                deduped.append(t)
        return deduped[:5]
