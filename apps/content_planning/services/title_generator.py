"""TitleGenerator：LLM 驱动的小红书桌布品类标题生成器。"""

from __future__ import annotations

import logging

from apps.content_planning.schemas.content_generation import (
    TitleCandidate,
    TitleGenerationResult,
)
from apps.content_planning.schemas.note_plan import NewNotePlan
from apps.content_planning.utils.plan_trace import plan_trace_kwargs
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.intel_hub.extraction.llm_client import (
    call_text_llm,
    is_llm_available,
    parse_json_response,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一位资深小红书桌布品类的内容策划专家。
你的任务是根据给定的策划方案和改写策略，生成 5 条高质量的小红书笔记标题。

输出要求：
1. 每条标题贴合小红书用户阅读习惯，字数 10-25 字
2. 标题需覆盖不同切入角度（如场景代入、利益点、悬念、口语化等）
3. 避免使用被标记为禁用的词汇
4. 输出严格 JSON 格式
"""


class TitleGenerator:
    """LLM 优先，规则降级的标题生成器。"""

    def generate(
        self,
        plan: NewNotePlan,
        strategy: RewriteStrategy,
    ) -> TitleGenerationResult:
        if is_llm_available():
            result = self._llm_generate(plan, strategy)
            if result.titles:
                return result
            logger.info("TitleGenerator: LLM 返回空结果，降级到规则模式")

        return self._rule_fallback(plan, strategy)

    def _llm_generate(
        self,
        plan: NewNotePlan,
        strategy: RewriteStrategy,
    ) -> TitleGenerationResult:
        user_prompt = self._build_user_prompt(plan, strategy)
        raw = call_text_llm(_SYSTEM_PROMPT, user_prompt, temperature=0.7, max_tokens=1500)
        if not raw:
            return TitleGenerationResult(**plan_trace_kwargs(plan), mode="llm_empty", titles=[])

        data = parse_json_response(raw)
        titles_data = data.get("titles", [])
        titles: list[TitleCandidate] = []
        for item in titles_data:
            if isinstance(item, dict) and item.get("text"):
                titles.append(TitleCandidate(
                    title_text=item["text"],
                    axis=item.get("axis", ""),
                    rationale=item.get("rationale", ""),
                ))
        return TitleGenerationResult(**plan_trace_kwargs(plan), titles=titles, mode="llm")

    @staticmethod
    def _build_user_prompt(plan: NewNotePlan, strategy: RewriteStrategy) -> str:
        parts = [
            f"## 笔记目标\n{plan.note_goal or '种草收藏'}",
            f"## 核心卖点\n{plan.core_selling_point or ''}",
            f"## 目标用户\n{'、'.join(plan.target_user[:4])}",
            f"## 目标场景\n{'、'.join(plan.target_scene[:4])}",
            f"## 策划定位\n{strategy.positioning_statement}",
            f"## 钩子方向\n{strategy.new_hook}",
            f"## 语气风格\n{strategy.tone_of_voice}",
        ]
        if plan.title_plan.title_axes:
            parts.append(f"## 标题方向轴\n{'；'.join(plan.title_plan.title_axes[:4])}")
        if plan.title_plan.do_not_use_phrases:
            parts.append(f"## 禁用词汇\n{'、'.join(plan.title_plan.do_not_use_phrases[:6])}")

        parts.append(
            '\n请输出 JSON：{"titles": [{"text": "标题", "axis": "切入角度", "rationale": "选用理由"}]}\n'
            "生成 5 条标题。"
        )
        return "\n\n".join(parts)

    @staticmethod
    def _rule_fallback(plan: NewNotePlan, strategy: RewriteStrategy) -> TitleGenerationResult:
        """规则降级：从策略和模板信息拼接候选标题。"""
        titles: list[TitleCandidate] = []
        scene = plan.target_scene[0] if plan.target_scene else "居家"
        value = plan.core_selling_point or "桌布"
        tone = strategy.tone_of_voice or "分享"

        templates = [
            (f"🏠 {scene}桌布分享｜{value}真的绝了", "场景代入"),
            (f"这块{value}桌布也太好看了吧！{scene}必备", "口语种草"),
            (f"一块桌布改变{scene}氛围感✨{value}", "利益点"),
        ]
        for text, axis in templates:
            titles.append(TitleCandidate(title_text=text, axis=axis, rationale=f"规则降级-{tone}"))

        if plan.title_plan.candidate_titles:
            for ct in plan.title_plan.candidate_titles[:2]:
                clean = ct.replace("[参考] ", "")
                titles.append(TitleCandidate(title_text=clean, axis="模板参考", rationale="复用模板推荐话术"))

        return TitleGenerationResult(**plan_trace_kwargs(plan), titles=titles, mode="rule")
