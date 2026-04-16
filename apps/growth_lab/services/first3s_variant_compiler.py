"""First3sVariantCompiler：从卖点规格生成前3秒钩子脚本裂变版本。

为每个卖点规格生成多种 hook 类型的口播/字幕脚本变体，
覆盖 question / shock / contrast / pain_point / benefit / curiosity 六类钩子。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from apps.growth_lab.schemas.first3s_variant import (
    First3sVariant,
    HookPattern,
    HookScript,
)

logger = logging.getLogger(__name__)

_HOOK_TYPES: list[str] = [
    "question", "shock", "contrast", "pain_point", "benefit", "curiosity",
]

_SYSTEM_PROMPT = """\
你是一个短视频前3秒脚本专家。给定卖点信息，为每种钩子类型生成口播脚本。

请输出严格 JSON 数组（不要 markdown code fence），每个元素格式：
{
  "hook_type": "question|shock|contrast|pain_point|benefit|curiosity",
  "opening_line": "前3秒开场句（15字以内）",
  "supporting_line": "补充信息句",
  "cta_line": "引导行动句",
  "tone": "语气描述",
  "conflict_type": "冲突类型描述",
  "visual_contrast": "画面对比描述"
}

要求：
- 每种 hook_type 生成一条，共 6 条
- opening_line 必须在3秒内说完，极度简洁有冲击力
- 不同 hook_type 之间风格差异要明显
- tone 用中文描述（如：紧迫感、好奇驱动、痛点共鸣）
"""


class First3sVariantCompiler:
    """前3秒钩子脚本裂变编译器：LLM 生成 + 规则兜底。"""

    async def generate_hook_variants(
        self,
        specs: list[dict],
        *,
        workspace_id: str = "",
        brand_id: str = "",
    ) -> list[First3sVariant]:
        """为每个卖点 spec dict 生成 3-4 个钩子变体。"""
        all_variants: list[First3sVariant] = []

        for spec in specs:
            spec_id = spec.get("spec_id", "")
            source_opp_id = (spec.get("source_opportunity_ids") or [""])[0]

            hooks = await self._try_llm_generate(spec)
            if not hooks:
                hooks = self._rule_based_generate(spec)

            for hook_data in hooks[:4]:
                variant = self._build_variant(
                    hook_data, spec_id, source_opp_id, workspace_id, brand_id,
                )
                all_variants.append(variant)

        logger.info(
            "前3秒钩子编译完成: %d 个 spec → %d 个变体",
            len(specs), len(all_variants),
        )
        return all_variants

    # ── LLM 路径 ──

    async def _try_llm_generate(self, spec: dict) -> list[dict]:
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return []

        user_content = self._build_user_content(spec)
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_content),
        ]

        try:
            resp = llm_router.chat(messages, temperature=0.7, max_tokens=2000)
            if resp.degraded or not resp.content.strip():
                return []
            return self._parse_llm_hooks(resp.content)
        except Exception:
            logger.debug("LLM 钩子生成失败", exc_info=True)
            return []

    @staticmethod
    def _build_user_content(spec: dict) -> str:
        core = spec.get("core_claim", "")
        supporting = spec.get("supporting_claims", [])
        people = spec.get("target_people", [])
        scenarios = spec.get("target_scenarios", [])
        diff = spec.get("differentiation_notes", "")
        first3s = spec.get("first3s_expression") or {}

        lines = [
            f"核心卖点: {core}",
            f"辅助卖点: {', '.join(supporting[:3])}",
            f"目标人群: {', '.join(people[:3])}",
            f"目标场景: {', '.join(scenarios[:3])}",
            f"差异化: {diff}",
        ]
        if first3s.get("headline"):
            lines.append(f"已有钩子参考: {first3s['headline']}")
        return "\n".join(lines)

    @staticmethod
    def _parse_llm_hooks(raw: str) -> list[dict]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict) and d.get("hook_type")]
        return []

    # ── 规则兜底 ──

    @staticmethod
    def _rule_based_generate(spec: dict) -> list[dict]:
        core = spec.get("core_claim", "")
        people = spec.get("target_people", [])
        scenarios = spec.get("target_scenarios", [])

        audience = people[0] if people else "你"
        scene = scenarios[0] if scenarios else ""

        templates: list[dict] = [
            {
                "hook_type": "question",
                "opening_line": f"{audience}还在为{scene or '这个'}烦恼？",
                "supporting_line": core,
                "cta_line": "看完你就懂了",
                "tone": "好奇驱动",
                "conflict_type": "需求未满足",
                "visual_contrast": "",
            },
            {
                "hook_type": "pain_point",
                "opening_line": f"别再踩坑了！{scene or '选错了真的亏'}",
                "supporting_line": core,
                "cta_line": "往下看解决方案",
                "tone": "痛点共鸣",
                "conflict_type": "踩坑风险",
                "visual_contrast": "踩坑 vs 正确选择",
            },
            {
                "hook_type": "benefit",
                "opening_line": f"用了这个之后{scene or '效果'}直接拉满",
                "supporting_line": core,
                "cta_line": "点击看同款",
                "tone": "利益前置",
                "conflict_type": "",
                "visual_contrast": "使用前 vs 使用后",
            },
            {
                "hook_type": "contrast",
                "opening_line": f"同样的价格，差距居然这么大",
                "supporting_line": core,
                "cta_line": "收藏备用",
                "tone": "对比冲击",
                "conflict_type": "性价比反差",
                "visual_contrast": "对比画面",
            },
        ]
        return templates

    # ── 构建 ──

    @staticmethod
    def _build_variant(
        hook_data: dict,
        spec_id: str,
        source_opp_id: str,
        workspace_id: str,
        brand_id: str,
    ) -> First3sVariant:
        hook_type = hook_data.get("hook_type", "contrast")

        hook_pattern = HookPattern(
            hook_type=hook_type,
            conflict_type=hook_data.get("conflict_type", ""),
            visual_contrast=hook_data.get("visual_contrast", ""),
            opening_sentence_pattern=hook_data.get("opening_line", ""),
        )

        hook_script = HookScript(
            hook_pattern_id=hook_pattern.pattern_id,
            opening_line=hook_data.get("opening_line", ""),
            supporting_line=hook_data.get("supporting_line", ""),
            cta_line=hook_data.get("cta_line", ""),
            tone=hook_data.get("tone", ""),
        )

        return First3sVariant(
            source_selling_point_id=spec_id,
            source_opportunity_id=source_opp_id,
            key_hook_type=hook_type,
            key_conflict_type=hook_data.get("conflict_type", ""),
            hook_script=hook_script,
            hook_pattern=hook_pattern,
            expected_goal=f"{hook_type} 钩子测试",
            workspace_id=workspace_id,
            brand_id=brand_id,
            status="scripted",
        )
