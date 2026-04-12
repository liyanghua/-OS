"""PromptOptimizer Skill: 通过 LLM 对结构化图片 prompt 进行优化重写。

输入：结构化 prompt（subject / style_tags / must_include / avoid_items / ref_image_url）
输出：优化后的结构化 prompt + 优化说明
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一个小红书图片生成专家。你的任务是优化图片提示词，使其更能生成高质量、符合小红书审美的图片。

优化原则：
1. 主体描述应具体、有画面感，避免抽象
2. 风格标签应精确，优先使用摄影/设计领域术语
3. 必含元素应聚焦核心视觉锚点，不超过 5 个
4. 规避项应覆盖常见生图问题（模糊、畸变、低质量等）
5. 整体风格偏暖、明亮、清新、高级感

你必须以 JSON 格式返回，包含以下字段：
{
  "subject": "优化后的主体描述",
  "style_tags": ["风格1", "风格2"],
  "must_include": ["元素1", "元素2"],
  "avoid_items": ["规避1", "规避2"],
  "explanation": "简要说明你做了哪些优化"
}"""


async def optimize_prompt(prompt_data: dict[str, Any]) -> dict[str, Any]:
    """调用 LLM 优化一个 slot 的结构化 prompt。

    Args:
        prompt_data: 包含 subject, style_tags, must_include, avoid_items, ref_image_url

    Returns:
        优化后的结构化数据 + explanation
    """
    import time as _time
    from apps.content_planning.adapters.llm_router import llm_router, LLMMessage

    user_msg = (
        f"请优化以下图片生成提示词：\n\n"
        f"主体描述: {prompt_data.get('subject', '')}\n"
        f"风格标签: {', '.join(prompt_data.get('style_tags', []))}\n"
        f"必含元素: {', '.join(prompt_data.get('must_include', []))}\n"
        f"规避项: {', '.join(prompt_data.get('avoid_items', []))}\n"
    )

    ref_url = prompt_data.get("ref_image_url", "")
    if ref_url:
        user_msg += "参考图: 有 (会作为参考风格)\n"

    msgs = [
        LLMMessage(role="system", content=_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_msg),
    ]
    trace: dict[str, Any] = {
        "operation": "optimize_prompt",
        "model": getattr(llm_router, "_model", "unknown"),
        "input_messages": [{"role": m.role, "content": m.content[:500]} for m in msgs],
        "status": "pending",
    }

    t0 = _time.perf_counter()
    try:
        result = await llm_router.achat(messages=msgs, temperature=0.7, max_tokens=800)
        elapsed = int((_time.perf_counter() - t0) * 1000)
        text = result.content if hasattr(result, "content") else str(result)
        trace["latency_ms"] = elapsed
        trace["output_raw"] = text[:1000]
        trace["status"] = "success"

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
            return {
                "subject": parsed.get("subject", prompt_data.get("subject", "")),
                "style_tags": parsed.get("style_tags", prompt_data.get("style_tags", [])),
                "must_include": parsed.get("must_include", prompt_data.get("must_include", [])),
                "avoid_items": parsed.get("avoid_items", prompt_data.get("avoid_items", [])),
                "explanation": parsed.get("explanation", ""),
                "optimized": True,
                "llm_trace": trace,
            }
        trace["status"] = "parse_error"
        logger.warning("prompt_optimizer: no JSON found in LLM response: %s", text[:200])
    except Exception as e:
        elapsed = int((_time.perf_counter() - t0) * 1000)
        trace["latency_ms"] = elapsed
        trace["status"] = "error"
        trace["error"] = str(e)
        logger.warning("prompt_optimizer LLM call failed: %s", e, exc_info=True)

    return {
        **prompt_data,
        "explanation": "LLM 优化失败，返回原始提示词",
        "optimized": False,
        "llm_trace": trace,
    }
