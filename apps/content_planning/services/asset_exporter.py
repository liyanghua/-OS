"""AssetExporter：统一导出 AssetBundle 到多种格式。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from apps.content_planning.schemas.asset_bundle import AssetBundle

logger = logging.getLogger(__name__)


class AssetExporter:
    """提供 JSON / Markdown / Image Package 三种导出格式。"""

    @staticmethod
    def export_json(bundle: AssetBundle) -> dict[str, Any]:
        """导出为 JSON 字典，可直接序列化。"""
        return bundle.model_dump(mode="json")

    @staticmethod
    def export_markdown(bundle: AssetBundle) -> str:
        """导出为 Markdown 格式的运营文档。"""
        lines: list[str] = []
        lines.append(f"# 内容资产包 {bundle.asset_bundle_id}")
        lines.append(f"")
        lines.append(f"- 机会 ID：{bundle.opportunity_id}")
        lines.append(f"- 模板：{bundle.template_name or bundle.template_id}")
        lines.append(f"- 创建时间：{bundle.created_at.isoformat()}")
        if bundle.lineage:
            lines.append(f"- Pipeline Run：{bundle.lineage.pipeline_run_id}")
        lines.append(f"- 导出状态：{bundle.export_status}")
        lines.append("")

        if bundle.title_candidates:
            lines.append("## 标题候选")
            lines.append("")
            for i, t in enumerate(bundle.title_candidates, 1):
                lines.append(f"{i}. **{t.get('title_text', '')}**")
                if t.get("axis"):
                    lines.append(f"   - 切入角度：{t['axis']}")
                if t.get("rationale"):
                    lines.append(f"   - 理由：{t['rationale']}")
            lines.append("")

        if bundle.body_draft:
            lines.append("## 正文")
            lines.append("")
            lines.append(bundle.body_draft)
            lines.append("")

        if bundle.body_outline:
            lines.append("## 正文大纲")
            lines.append("")
            for item in bundle.body_outline:
                lines.append(f"- {item}")
            lines.append("")

        if bundle.image_execution_briefs:
            lines.append("## 图片执行指令")
            lines.append("")
            for sb in bundle.image_execution_briefs:
                idx = sb.get("slot_index", "?")
                role = sb.get("role", "")
                lines.append(f"### 第 {idx} 张 — {role}")
                for key in ("subject", "composition", "color_mood", "text_overlay"):
                    val = sb.get(key, "")
                    if val:
                        lines.append(f"- {key}：{val}")
                props = sb.get("props", [])
                if props:
                    lines.append(f"- 道具：{'、'.join(props)}")
                avoid = sb.get("avoid_items", [])
                if avoid:
                    lines.append(f"- 规避：{'、'.join(avoid)}")
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def export_image_package(bundle: AssetBundle) -> dict[str, Any]:
        """导出图片执行包（给设计/拍摄团队的结构化指令集）。"""
        return {
            "bundle_id": bundle.asset_bundle_id,
            "opportunity_id": bundle.opportunity_id,
            "template": bundle.template_name or bundle.template_id,
            "total_slots": len(bundle.image_execution_briefs),
            "slots": bundle.image_execution_briefs,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
