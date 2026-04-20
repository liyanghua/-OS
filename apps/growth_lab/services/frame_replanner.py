"""FrameReplanner — 换模板保结果。

当用户在 Frame header 切换模板时，按 slot_index 做最佳匹配：
- 相同 slot_index 的节点：保留 active_variant（asset 不丢），更新 role/visual_spec/copy_spec
- 超出新模板 slot 数的节点：归档（status=archived），但 variants 仍保留
- 新模板新增的 slot：创建 draft 新节点

这样用户改模板也不需要重新生成（已合意的结果不丢）。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from apps.growth_lab.schemas.visual_workspace import ResultNode
from apps.growth_lab.services.template_library import get_template_library
from apps.growth_lab.services.visual_plan_compiler import (
    _FRAME_KEY_CONFIG,
    _FRAME_KEY_TO_RESULT_TYPE,
    VisualPlanCompiler,
)
from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)


class FrameReplanner:
    def __init__(self, store: GrowthLabStore | None = None) -> None:
        self._store = store or GrowthLabStore()

    def preview(
        self,
        *,
        frame_id: str,
        new_template_id: str,
        keep_assets: bool = True,
    ) -> dict:
        """返回换模板的 diff 预览（不落库）。"""
        frame = self._store.get_workspace_frame(frame_id)
        if not frame:
            raise ValueError(f"frame not found: {frame_id}")
        new_template = get_template_library().get(new_template_id)
        if not new_template:
            raise ValueError(f"template not found: {new_template_id}")
        existing_nodes = self._store.list_workspace_nodes(frame_id=frame_id)
        node_by_slot: dict[int, dict] = {n["slot_index"]: n for n in existing_nodes}

        will_update: list[dict] = []
        will_create: list[dict] = []
        for i, slot in enumerate(new_template.slots):
            slot_idx = slot.index or (i + 1)
            existing = node_by_slot.pop(slot_idx, None)
            if existing and keep_assets:
                will_update.append({
                    "slot_index": slot_idx,
                    "node_id": existing.get("node_id", ""),
                    "old_role": existing.get("role", ""),
                    "new_role": slot.role,
                    "old_visual": (existing.get("visual_spec") or "")[:60],
                    "new_visual": (slot.visual_spec or "")[:60],
                    "keeps_variants": bool(existing.get("variant_ids")),
                    "active_variant_id": existing.get("active_variant_id", ""),
                })
            else:
                will_create.append({
                    "slot_index": slot_idx,
                    "role": slot.role,
                    "visual_spec": (slot.visual_spec or "")[:80],
                })
        will_archive: list[dict] = []
        for n in node_by_slot.values():
            will_archive.append({
                "slot_index": n.get("slot_index"),
                "node_id": n.get("node_id", ""),
                "role": n.get("role", ""),
                "has_active": bool(n.get("active_variant_id")),
            })
        return {
            "frame_id": frame_id,
            "old_template_id": frame.get("template_id", ""),
            "new_template_id": new_template.template_id,
            "new_template_name": new_template.name,
            "will_update": will_update,
            "will_create": will_create,
            "will_archive": will_archive,
            "keep_assets": keep_assets,
        }

    def replan(
        self,
        *,
        frame_id: str,
        new_template_id: str,
        keep_assets: bool = True,
    ) -> dict:
        frame = self._store.get_workspace_frame(frame_id)
        if not frame:
            raise ValueError(f"frame not found: {frame_id}")
        new_template = get_template_library().get(new_template_id)
        if not new_template:
            raise ValueError(f"template not found: {new_template_id}")

        cfg = _FRAME_KEY_CONFIG.get(frame.get("frame_key", ""))
        if cfg is None:
            raise ValueError(f"unsupported frame_key: {frame.get('frame_key')}")

        existing_nodes = self._store.list_workspace_nodes(frame_id=frame_id)
        node_by_slot: dict[int, dict] = {n["slot_index"]: n for n in existing_nodes}

        node_w, node_h = cfg["node_size"]
        gap = cfg["gap"]
        padding_left = 20.0
        padding_top = 52.0
        cols = max(1, VisualPlanCompiler._cols_for(frame["frame_key"], len(new_template.slots), cfg))

        updated: list[dict] = []
        created: list[dict] = []
        archived: list[dict] = []

        # 匹配新 slot
        for i, slot in enumerate(new_template.slots):
            slot_idx = slot.index or (i + 1)
            col = i % cols
            row = i // cols
            canvas_x = float(frame.get("canvas_x", 0)) + padding_left + col * (node_w + gap)
            canvas_y = float(frame.get("canvas_y", 0)) + padding_top + row * (node_h + gap)

            existing = node_by_slot.pop(slot_idx, None)
            if existing and keep_assets:
                # 保留 active_variant，更新 slot 语义
                existing["role"] = slot.role
                existing["visual_spec"] = slot.visual_spec
                existing["copy_spec"] = slot.copy_spec
                existing["aspect_ratio"] = slot.aspect_ratio or existing.get("aspect_ratio")
                existing["template_slot_ref"] = f"{new_template.template_id}#{slot_idx}"
                existing["canvas_x"] = canvas_x
                existing["canvas_y"] = canvas_y
                existing["width"] = node_w
                existing["height"] = node_h
                existing["updated_at"] = datetime.now(UTC).isoformat()
                # 保留旧 status：若之前是 generated/approved，用户应重新 review
                if existing.get("status") in {"generated", "approved"}:
                    existing["status"] = "reviewed"  # 提示用户 re-review
                self._store.save_workspace_node(existing)
                updated.append(existing)
            else:
                # 新节点
                new_node = ResultNode(
                    plan_id=frame.get("plan_id", ""),
                    frame_id=frame_id,
                    slot_index=slot_idx,
                    role=slot.role,
                    result_type=_FRAME_KEY_TO_RESULT_TYPE.get(frame["frame_key"], "main_image"),
                    title=f"{cfg['title']} · {slot.role}",
                    objective=slot.role,
                    visual_spec=slot.visual_spec,
                    copy_spec=slot.copy_spec,
                    aspect_ratio=slot.aspect_ratio or "1:1",
                    canvas_x=canvas_x,
                    canvas_y=canvas_y,
                    width=node_w,
                    height=node_h,
                    template_slot_ref=f"{new_template.template_id}#{slot_idx}",
                    brand_rule_refs=list(new_template.default_brand_rules),
                    status="draft",
                )
                self._store.save_workspace_node(new_node.model_dump(mode="json"))
                created.append(new_node.model_dump(mode="json"))

        # 剩余的旧 slot → 归档（保留资产）
        for n in node_by_slot.values():
            if keep_assets:
                n["status"] = "archived"
                n["updated_at"] = datetime.now(UTC).isoformat()
                self._store.save_workspace_node(n)
                archived.append(n)

        # 更新 frame
        frame["template_id"] = new_template.template_id
        frame["title"] = f"{cfg['title']} · {new_template.name}"
        all_current = self._store.list_workspace_nodes(frame_id=frame_id)
        frame["node_ids"] = [
            n["node_id"] for n in all_current if n.get("status") != "archived"
        ]
        self._store.save_workspace_frame(frame)

        logger.info(
            "replan_frame: frame=%s updated=%d created=%d archived=%d",
            frame_id, len(updated), len(created), len(archived),
        )
        return {
            "frame": frame,
            "updated": len(updated),
            "created": len(created),
            "archived": len(archived),
        }
