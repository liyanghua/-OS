"""DetailModuleCompiler — 详情页 9 模块专用 prompt 增强器。

视觉工作台的详情 Frame 由 VisualPlanCompiler 生成节点骨架后，
再通过本 compiler 把"模块级文案+视觉"诉求编译成可送入图像生成的 prompt。

关键：一屏一卖点、模块在"品牌势能建立 → 产品体验表达 → 品牌与信任建设 → 转化收口"
的叙事链路中各有定位，由此给每个模块加上"紧贴上下文"的 prompt 前缀。
模块划分对齐《品牌级详情页策划案报告》模块脚本（9 个模块）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_MODULE_NARRATIVE_ROLE = {
    1: "首屏海报，品牌势能建立，第一眼传达品牌符号与奢华气质",
    2: "核心卖点展示，强化品牌符号识别度的审美表达",
    3: "功能演示，展示乳霜到泡沫的温和细腻转化体验",
    4: "材质特写，突出高级包装材质与仪式感",
    5: "使用场景，晨晚切换中的日常悦己与洁面仪式情绪",
    6: "人物互动，都市女性的生活方式与身份表达",
    7: "品牌故事，品牌历史与奢护认知的纵深背书",
    8: "信任背书，全球高端认知与官方渠道构成的可信度",
    9: "规格参数，产品全貌与购买决策收口",
}

_MODULE_NARRATIVE_STAGE = {
    1: "品牌势能建立",
    2: "品牌势能建立",
    3: "产品体验表达",
    4: "产品体验表达",
    5: "产品体验表达",
    6: "产品体验表达",
    7: "品牌与信任建设",
    8: "品牌与信任建设",
    9: "转化收口",
}

_TOTAL_MODULES = 9


class DetailModuleCompiler:
    """详情页 9 模块专用 prompt 增强器。"""

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
        narrative_stage = _MODULE_NARRATIVE_STAGE.get(slot_idx, "")

        header = f"[详情页第 {slot_idx}/{_TOTAL_MODULES} 模块"
        if narrative_stage:
            header += f" · 阶段：{narrative_stage}"
        header += f" · 叙事定位：{narrative_role}]"
        parts: list[str] = [header]
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
