"""BuyerShowCompiler — 买家秀 8 张场景风格库专用 prompt 增强器。

针对真人买家秀场景，强调：
- 真实生活感（避免过度美化）
- 中国都市女性人物特征
- 环境元素贴近目标人群日常
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BuyerShowCompiler:
    """买家秀节点 prompt 增强器。"""

    def enhance_node_prompt(
        self,
        node: dict,
        *,
        intent: dict | None = None,
    ) -> str:
        intent = intent or {}
        parts: list[str] = [
            "[真人买家秀 · 3:4 竖版 · 真实生活感]",
        ]
        if intent.get("product_name"):
            parts.append(f"商品：{intent['product_name']}")
        if intent.get("audience"):
            parts.append(f"人群：{intent['audience']}")
        else:
            parts.append("人群：18-29 岁中国都市女性")
        if node.get("role"):
            parts.append(f"场景：{node['role']}")
        if node.get("visual_spec"):
            parts.append(f"画面：{node['visual_spec']}")
        parts.append("风格：自然光、柔和色调、真人真实表情、轻熟日常氛围；避免过度美颜/虚化背景")
        if intent.get("avoid"):
            parts.append(f"避免：{', '.join(intent['avoid'][:3])}")
        return "\n".join(parts)


_instance: BuyerShowCompiler | None = None


def get_buyer_show_compiler() -> BuyerShowCompiler:
    global _instance
    if _instance is None:
        _instance = BuyerShowCompiler()
    return _instance
