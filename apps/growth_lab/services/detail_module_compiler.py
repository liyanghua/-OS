"""DetailModuleCompiler — 详情页 8 模块专用 prompt 增强器。

视觉工作台的详情 Frame 由 VisualPlanCompiler 生成节点骨架后，
再通过本 compiler 把"模块级文案+视觉"诉求编译成可送入图像生成的 prompt。

关键：一屏一卖点、模块有上下文（第 n 模块在 "吸引→设计→材料→…" 叙事链路中的位置），
由此给每个模块加上"紧贴上下文"的 prompt 前缀。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_MODULE_NARRATIVE_ROLE = {
    1: "开篇吸睛，第一眼让用户记住产品",
    2: "呈现独特设计的差异化爽点",
    3: "强调材料/成分的安全或功能性",
    4: "工艺或制作的专业背书",
    5: "核心功能解决真实痛点",
    6: "使用过程的便捷与简单",
    7: "耐用性/性价比数据化表达",
    8: "关键参数清单，帮助决策",
}


class DetailModuleCompiler:
    """详情页 8 模块专用 prompt 增强器。"""

    def enhance_node_prompt(
        self,
        node: dict,
        *,
        intent: dict | None = None,
    ) -> str:
        """基于节点 slot_index 补足详情模块上下文，返回增强后的 prompt。"""
        intent = intent or {}
        slot_idx = int(node.get("slot_index") or 1)
        narrative_role = _MODULE_NARRATIVE_ROLE.get(
            slot_idx, "一屏一卖点的详情模块",
        )

        parts: list[str] = [
            f"[详情页第 {slot_idx}/8 模块 · 叙事定位：{narrative_role}]",
        ]
        if intent.get("product_name"):
            parts.append(f"商品：{intent['product_name']}")
        if intent.get("audience"):
            parts.append(f"目标人群：{intent['audience']}")
        if node.get("role"):
            parts.append(f"模块角色：{node['role']}")
        if node.get("visual_spec"):
            parts.append(f"视觉要求：{node['visual_spec']}")
        if node.get("copy_spec"):
            parts.append(f"文案方向：{node['copy_spec']}")
        if intent.get("must_have"):
            parts.append(f"必呈现卖点：{', '.join(intent['must_have'][:3])}")
        if intent.get("avoid"):
            parts.append(f"避免：{', '.join(intent['avoid'][:3])}")
        parts.append("输出：竖版 3:4 商详图；左图右文或上图下文；单屏聚焦，避免信息过载")
        return "\n".join(parts)


_instance: DetailModuleCompiler | None = None


def get_detail_module_compiler() -> DetailModuleCompiler:
    global _instance
    if _instance is None:
        _instance = DetailModuleCompiler()
    return _instance
