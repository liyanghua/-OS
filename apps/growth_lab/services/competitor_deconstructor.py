"""CompetitorDeconstructor — 竞品主图 32 维度 VLM 拆解器。

输入：竞品图片 URL
输出：按 competitor_deconstruct_32d 模板 4 组共 32 维度的结构化分析 + 对标本品的差异点。

LLM 不可用时，返回规则降级（即返回 32 维空值骨架），方便前端仍能渲染画布节点。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
你是一位资深电商视觉拆解专家，按 32 个维度分析竞品主图。
输入是一张竞品主图的 URL，请从以下四组共 32 个维度输出结构化分析。

严格输出纯 JSON（不要 code fence）：
{
  "composition_color": {  // 构图与色彩 8 维
    "主体物位置": "...", "构图方式": "...", "层次关系": "...", "主色调": "...",
    "辅助色": "...", "色彩对比": "...", "色彩情绪": "...", "产品占比": "..."
  },
  "display_copy": {  // 展示与文案 8 维
    "展示角度": "...", "展示数量": "...", "细节呈现": "...", "标题文字": "...",
    "促销信息": "...", "卖点文案": "...", "文字位置": "...", "文字占比": "..."
  },
  "background_mood": {  // 背景与氛围 8 维
    "背景类型": "...", "背景颜色": "...", "简洁程度": "...", "氛围营造": "...",
    "装饰元素": "...", "图标标识": "...", "边框修饰": "...", "特效处理": "..."
  },
  "scene_quality": {  // 场景与品质 8 维
    "使用场景": "...", "人物元素": "...", "生活化元素": "...", "场景道具": "...",
    "图片清晰度": "...", "光影处理": "...", "精致程度": "...", "专业度": "..."
  },
  "summary": "一句话总结竞品主图的差异化打法（≤40字）",
  "borrow_ideas": ["可借鉴点1", "可借鉴点2"],
  "avoid_ideas": ["应规避点1"]
}
"""


class CompetitorDeconstructor:
    """VLM 竞品拆解器。"""

    async def deconstruct(self, image_url: str) -> dict:
        """分析一张竞品图；LLM 不可用时返回骨架。"""
        if not image_url:
            return self._empty_skeleton(reason="empty_url")
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return self._empty_skeleton(reason="llm_router_unavailable")

        user_content = f"请分析以下竞品主图（图片 URL）:\n{image_url}\n\n" \
                       f"如果你不支持视觉输入，请基于 URL 文本猜测品类并给出典型电商主图的 32 维度参考评估。"

        try:
            resp = await llm_router.achat(
                [LLMMessage(role="system", content=_SYSTEM_PROMPT),
                 LLMMessage(role="user", content=user_content)],
                temperature=0.4, max_tokens=1800,
            )
            parsed = self._safe_json(resp.content)
            if not parsed:
                return self._empty_skeleton(reason="json_parse_failed")
            parsed["image_url"] = image_url
            parsed["provider"] = resp.model
            return parsed
        except Exception as exc:
            logger.warning("[CompetitorDeconstructor] LLM 调用失败 %s", exc)
            return self._empty_skeleton(reason=f"llm_error:{exc}")

    @staticmethod
    def _safe_json(text: str) -> dict:
        if not text:
            return {}
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _empty_skeleton(*, reason: str = "") -> dict:
        empty_group = lambda keys: {k: "" for k in keys}
        return {
            "composition_color": empty_group([
                "主体物位置", "构图方式", "层次关系", "主色调",
                "辅助色", "色彩对比", "色彩情绪", "产品占比",
            ]),
            "display_copy": empty_group([
                "展示角度", "展示数量", "细节呈现", "标题文字",
                "促销信息", "卖点文案", "文字位置", "文字占比",
            ]),
            "background_mood": empty_group([
                "背景类型", "背景颜色", "简洁程度", "氛围营造",
                "装饰元素", "图标标识", "边框修饰", "特效处理",
            ]),
            "scene_quality": empty_group([
                "使用场景", "人物元素", "生活化元素", "场景道具",
                "图片清晰度", "光影处理", "精致程度", "专业度",
            ]),
            "summary": "",
            "borrow_ideas": [],
            "avoid_ideas": [],
            "note": f"degraded: {reason}",
        }


_instance: CompetitorDeconstructor | None = None


def get_competitor_deconstructor() -> CompetitorDeconstructor:
    global _instance
    if _instance is None:
        _instance = CompetitorDeconstructor()
    return _instance
