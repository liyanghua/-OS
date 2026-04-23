"""CompetitorDeconstructor — 竞品主图 32 维度 VLM 拆解器。

输入：竞品图片 URL（公网 http(s) 或本地 /source-images/、/generated-images/ 路径）
输出：按 competitor_deconstruct_32d 模板 4 组共 32 维度的结构化分析 + 对标本品的差异点。

多模态调用复用 `apps.growth_lab.services.vlm_client.call_vlm_multimodal`，
按 DashScope Qwen-VL → OpenAI 代理 → OpenRouter 的优先级回退；
LLM 不可用 / 解析失败时返回规则降级（32 维空值骨架），让前端仍能渲染画布节点。
"""

from __future__ import annotations

import logging

from apps.growth_lab.services.vlm_client import (
    call_vlm_multimodal,
    candidate_providers,
    resolve_image_ref,
    safe_json_obj,
)

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
你是一位资深电商视觉拆解专家，按 32 个维度分析竞品主图。
输入是一张竞品主图（通过 image_url 传入），请认真观察图片，从以下四组共 32 个维度输出结构化分析。
每个维度必须基于你对该图片的实际观察给出具体、简短的描述（≤20 字），不要留空、不要用“无/N/A”。

严格输出纯 JSON（不要 code fence、不要多余文字）：
{
  "composition_color": {
    "主体物位置": "...", "构图方式": "...", "层次关系": "...", "主色调": "...",
    "辅助色": "...", "色彩对比": "...", "色彩情绪": "...", "产品占比": "..."
  },
  "display_copy": {
    "展示角度": "...", "展示数量": "...", "细节呈现": "...", "标题文字": "...",
    "促销信息": "...", "卖点文案": "...", "文字位置": "...", "文字占比": "..."
  },
  "background_mood": {
    "背景类型": "...", "背景颜色": "...", "简洁程度": "...", "氛围营造": "...",
    "装饰元素": "...", "图标标识": "...", "边框修饰": "...", "特效处理": "..."
  },
  "scene_quality": {
    "使用场景": "...", "人物元素": "...", "生活化元素": "...", "场景道具": "...",
    "图片清晰度": "...", "光影处理": "...", "精致程度": "...", "专业度": "..."
  },
  "summary": "一句话总结竞品主图的差异化打法（≤40字）",
  "borrow_ideas": ["可借鉴点1", "可借鉴点2"],
  "avoid_ideas": ["应规避点1"]
}
"""

_USER_HINT = (
    "请仔细观察这张竞品主图，按系统提示给出的 JSON 结构填充 32 维分析，"
    "每个维度用你实际观察到的视觉特征来写具体描述，不要留空。"
)


class CompetitorDeconstructor:
    """VLM 竞品拆解器。"""

    async def deconstruct(self, image_url: str) -> dict:
        """分析一张竞品图；VLM 不可用或解析失败时返回空骨架。"""
        if not image_url:
            return self._empty_skeleton(reason="empty_url")

        ref_url = resolve_image_ref(image_url)
        if not ref_url:
            return self._empty_skeleton(reason="local_image_not_found")

        providers = candidate_providers()
        if not providers:
            logger.warning(
                "[CompetitorDeconstructor] 未配置 VLM 提供方（DASHSCOPE / OPENAI_BASE_URL / OPENROUTER 均缺失）"
            )
            return self._empty_skeleton(reason="no_vision_provider")

        resp = await call_vlm_multimodal(
            system_prompt=_SYSTEM_PROMPT,
            user_text=_USER_HINT,
            image_urls=[image_url],
            temperature=0.3,
            max_tokens=4096,
            force_json=True,
        )
        if not resp.content:
            return self._empty_skeleton(reason=resp.raw_reason or "vlm_empty")

        parsed = safe_json_obj(resp.content)
        if not parsed:
            logger.warning(
                "[CompetitorDeconstructor] VLM 响应无法解析 JSON provider=%s model=%s preview=%s",
                resp.provider, resp.model, (resp.content or "")[:200],
            )
            return self._empty_skeleton(reason="json_parse_failed")

        parsed["image_url"] = image_url
        parsed["provider"] = f"{resp.provider}:{resp.model}"
        return parsed

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
