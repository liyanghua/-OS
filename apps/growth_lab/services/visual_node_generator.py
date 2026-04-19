"""VisualNodeGenerator — 把 ResultNode 送入图像/视频生成，回写 Variant。

对外只暴露两个方法：
- generate_node(node_id, count=1) → 触发一次批量生成，返回 batch_id
- ensure_frame_generated(frame_id) → 检查 frame 内所有 draft 节点，批量触发

实际图像生成复用现有 VariantBatchQueue + ImageGeneratorService，
所以 LLM/provider 选择逻辑完全一致。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.growth_lab.schemas.visual_workspace import Variant
from apps.growth_lab.services.template_library import get_template_library
from apps.growth_lab.services.variant_batch_queue import VariantBatchQueue
from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)


_queue_instance: VariantBatchQueue | None = None


def _get_queue() -> VariantBatchQueue:
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = VariantBatchQueue()
    return _queue_instance


# 画布宽高比 → provider 接受的 size 字符串
_ASPECT_TO_SIZE = {
    "1:1": "1024*1024",
    "3:4": "864*1152",
    "4:3": "1152*864",
    "16:9": "1280*720",
    "9:16": "720*1280",
}


def _size_for_node(aspect_ratio: str) -> str:
    return _ASPECT_TO_SIZE.get(aspect_ratio or "1:1", "1024*1024")


def _lookup_slot_and_template(node: dict) -> tuple[Any, Any]:
    """通过 `template_slot_ref = '{template_id}#{slot_index}'` 回查模板与 slot。

    返回 (template, slot)；找不到时返回 (None, None)。
    """
    ref = node.get("template_slot_ref") or ""
    if "#" not in ref:
        return None, None
    template_id, _, idx_str = ref.partition("#")
    try:
        slot_idx = int(idx_str)
    except ValueError:
        return None, None
    lib = get_template_library()
    template = lib.get(template_id)
    if template is None:
        return None, None
    slot = next((s for s in template.slots if s.index == slot_idx), None)
    return template, slot


def _expert_enrichment(node: dict) -> tuple[list[str], list[str]]:
    """根据节点绑定的模板，返回 (positive_blocks, negative_blocks)。

    富模板（Schema v2 / 详情 MD 等）会提供明确的 prompt blocks；
    精简模板退回空列表。
    """
    template, slot = _lookup_slot_and_template(node)
    if slot is None:
        return [], []
    pos: list[str] = list(slot.positive_prompt_blocks or [])
    neg: list[str] = list(slot.negative_prompt_blocks or [])
    # global_style 补充（仅 Schema v2 有）
    if template is not None:
        gs = template.global_style or {}
        if gs.get("tone"):
            pos.append(f"整体基调：{gs['tone']}")
        if gs.get("visual_keywords"):
            pos.append("视觉关键词：" + "、".join(gs["visual_keywords"][:6]))
        if gs.get("avoid_keywords"):
            neg.extend(gs["avoid_keywords"])
        sp = template.strategy_pack or {}
        mh = (sp.get("message_hierarchy") or {})
        if mh.get("primary_message"):
            pos.append(f"主信息：{mh['primary_message']}")
    return pos, neg


def _compose_prompt(node: dict, intent: dict | None = None) -> str:
    """按节点 result_type 调用专用 compiler。"""
    intent = intent or {}
    result_type = node.get("result_type", "main_image")

    if result_type == "detail_module":
        from apps.growth_lab.services.detail_module_compiler import get_detail_module_compiler
        base = get_detail_module_compiler().enhance_node_prompt(node, intent=intent)
        return _append_expert_blocks(base, node)

    if result_type == "video_shot":
        from apps.growth_lab.services.video_shot_compiler import get_video_shot_compiler
        base = get_video_shot_compiler().enhance_node_prompt(node, intent=intent)
        return _append_expert_blocks(base, node)

    if result_type == "buyer_show":
        try:
            from apps.growth_lab.services.buyer_show_compiler import get_buyer_show_compiler
            base = get_buyer_show_compiler().enhance_node_prompt(node, intent=intent)
            return _append_expert_blocks(base, node)
        except ImportError:
            pass  # Sprint 3 未到位时 fallback 到通用 prompt

    if result_type == "competitor_ref":
        # 竞品节点不做图像生成，由 competitor_deconstructor 单独处理
        return ""

    # 主图 / 默认
    parts: list[str] = []
    if intent.get("product_name"):
        parts.append(f"商品：{intent['product_name']}")
    if intent.get("audience"):
        parts.append(f"人群：{intent['audience']}")
    if node.get("role"):
        parts.append(f"节点角色：{node['role']}")
    if node.get("visual_spec"):
        parts.append(f"视觉要求：{node['visual_spec']}")
    if node.get("copy_spec"):
        parts.append(f"文案方向：{node['copy_spec']}")
    if intent.get("style_refs"):
        parts.append(f"参考风格：{', '.join(intent['style_refs'][:3])}")
    if intent.get("must_have"):
        parts.append(f"必须呈现：{', '.join(intent['must_have'][:3])}")
    if intent.get("avoid"):
        parts.append(f"避免：{', '.join(intent['avoid'][:3])}")
    pos_blocks, _ = _expert_enrichment(node)
    if pos_blocks:
        parts.append("专家视觉块：" + "；".join(pos_blocks))
    return "\n".join(parts)


def _append_expert_blocks(base: str, node: dict) -> str:
    pos_blocks, _ = _expert_enrichment(node)
    if not pos_blocks:
        return base
    return base + "\n专家视觉块：" + "；".join(pos_blocks)


def _compose_negative_prompt(node: dict, intent: dict | None = None) -> str:
    intent = intent or {}
    parts: list[str] = []
    _, neg = _expert_enrichment(node)
    parts.extend(neg)
    if intent.get("avoid"):
        parts.extend(intent["avoid"])
    # 去重保序
    seen: set[str] = set()
    unique: list[str] = []
    for p in parts:
        if p and p not in seen:
            unique.append(p)
            seen.add(p)
    return "，".join(unique[:12])


class VisualNodeGenerator:
    """节点 → 变体生成器。"""

    def __init__(self, store: GrowthLabStore | None = None) -> None:
        self._store = store or GrowthLabStore()
        self._queue = _get_queue()

    # ── 单节点生成 ──

    def generate_for_node(self, node_id: str, count: int = 1) -> str:
        """对单个节点生成 count 张变体；返回 batch_id。"""
        node = self._store.get_workspace_node(node_id)
        if not node:
            raise ValueError(f"节点不存在: {node_id}")

        plan = self._store.get_workspace_plan(node.get("plan_id", ""))
        intent = (plan or {}).get("intent", {}) if plan else {}

        prompt = _compose_prompt(node, intent)
        negative_prompt = _compose_negative_prompt(node, intent)
        size = _size_for_node(node.get("aspect_ratio", "1:1"))

        variants_to_save: list[Variant] = []
        variant_dicts: list[dict[str, Any]] = []
        for _ in range(max(1, count)):
            v = Variant(
                node_id=node_id,
                prompt_sent=prompt,
                provider="",
                status="pending",
                asset_type="image",
            )
            variants_to_save.append(v)

            # 为 VariantBatchQueue 构造 variant dict（它期待的 shape）
            variant_dict = {
                "variant_id": v.variant_id,
                "source_opportunity_id": plan.get("plan_id", "") if plan else "",
                "image_variant_spec": {
                    "base_prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "size": size,
                    "reference_image_urls": [],
                    "provider_hint": "auto",
                },
                "_node_id": node_id,
            }
            variant_dicts.append(variant_dict)

        # 落库（pending 状态）
        for v in variants_to_save:
            self._store.save_workspace_variant(v.model_dump(mode="json"))
        # 更新节点状态
        node["status"] = "generating"
        node["updated_at"] = datetime.now(UTC).isoformat()
        node["variant_ids"] = (node.get("variant_ids") or []) + [v.variant_id for v in variants_to_save]
        self._store.save_workspace_node(node)

        # 入队
        queue = VariantBatchQueue(
            on_slot_done=self._make_on_done(),
        )
        batch_id = queue.enqueue_batch(variant_dicts)
        # 把 batch 暴露到 _queue_instance 也可轮询（这里 queue 是本次私有实例，保留句柄）
        self._queue_last_private = queue  # 便于 route 拿到状态
        _register_batch(batch_id, queue)
        return batch_id

    # ── 图生图微调 ──

    def edit_variant(
        self,
        node_id: str,
        user_prompt: str,
        *,
        base_variant_id: str = "",
        count: int = 1,
    ) -> str:
        """以 active 变体（或指定 base_variant_id）为底图做图生图微调。

        返回 batch_id。底图缺失或无 asset_url 时抛 ValueError。
        """
        node = self._store.get_workspace_node(node_id)
        if not node:
            raise ValueError(f"节点不存在: {node_id}")
        if not (user_prompt or "").strip():
            raise ValueError("请描述要调整的内容")

        target_variant_id = base_variant_id or node.get("active_variant_id") or ""
        base_variant = self._store.get_workspace_variant(target_variant_id) if target_variant_id else None
        if not base_variant or not base_variant.get("asset_url"):
            raise ValueError("先生成或采纳一个变体后再开始微调")
        base_asset_url = base_variant["asset_url"]

        plan = self._store.get_workspace_plan(node.get("plan_id", "")) if node.get("plan_id") else None
        intent = (plan or {}).get("intent", {}) if plan else {}

        # 构造 edit 指令：不再叠加全量 expert blocks，避免把旧细节拉回来
        instruction = user_prompt.strip()
        hints: list[str] = []
        for m in (intent.get("must_have") or [])[:2]:
            if isinstance(m, str) and m.strip():
                hints.append(str(m).strip())
        if hints:
            instruction += "；保持：" + "、".join(hints)
        avoid = [a for a in (intent.get("avoid") or []) if isinstance(a, str) and a.strip()][:4]
        negative_prompt = "、".join(avoid)

        size = _size_for_node(node.get("aspect_ratio", "1:1"))

        variants_to_save: list[Variant] = []
        variant_dicts: list[dict[str, Any]] = []
        for _ in range(max(1, count)):
            v = Variant(
                node_id=node_id,
                prompt_sent=instruction,
                provider="",
                status="pending",
                asset_type="image",
                extra={
                    "mode": "edit",
                    "base_variant_id": target_variant_id,
                    "edit_instruction": user_prompt.strip(),
                },
            )
            variants_to_save.append(v)
            variant_dicts.append({
                "variant_id": v.variant_id,
                "source_opportunity_id": plan.get("plan_id", "") if plan else "",
                "image_variant_spec": {
                    "base_prompt": instruction,
                    "negative_prompt": negative_prompt,
                    "size": size,
                    "reference_image_urls": [base_asset_url],
                    "provider_hint": "auto",
                    "mode": "edit",
                },
                "_node_id": node_id,
            })

        for v in variants_to_save:
            self._store.save_workspace_variant(v.model_dump(mode="json"))
        node["status"] = "generating"
        node["updated_at"] = datetime.now(UTC).isoformat()
        node["variant_ids"] = (node.get("variant_ids") or []) + [v.variant_id for v in variants_to_save]
        self._store.save_workspace_node(node)

        queue = VariantBatchQueue(on_slot_done=self._make_on_done())
        batch_id = queue.enqueue_batch(variant_dicts)
        self._queue_last_private = queue
        _register_batch(batch_id, queue)
        logger.info("edit_variant enqueued: node=%s base_variant=%s count=%d batch=%s",
                    node_id, target_variant_id, count, batch_id)
        return batch_id

    def _make_on_done(self):
        store = self._store

        def _cb(variant: dict, result_url: str) -> None:
            variant_id = variant.get("variant_id", "")
            node_id = variant.get("_node_id", "")
            if not variant_id:
                return
            stored = store.get_workspace_variant(variant_id) or {
                "variant_id": variant_id, "node_id": node_id,
            }
            if result_url:
                stored["asset_url"] = result_url
                stored["status"] = "done"
            else:
                stored["status"] = "failed"
            stored["updated_at"] = datetime.now(UTC).isoformat()
            store.save_workspace_variant(stored)

            if node_id:
                node = store.get_workspace_node(node_id)
                if node is not None:
                    if result_url:
                        node["status"] = "generated"
                        if not node.get("active_variant_id"):
                            node["active_variant_id"] = variant_id
                    else:
                        # 节点整体仍可能 generating（其他 variant 未完成），这里保守不覆盖
                        if not node.get("active_variant_id"):
                            node["status"] = "failed"
                    node["updated_at"] = datetime.now(UTC).isoformat()
                    store.save_workspace_node(node)

        return _cb


# ── 批量句柄登记（让 status 端点能找到对应队列） ──

_batch_queues: dict[str, VariantBatchQueue] = {}


def _register_batch(batch_id: str, q: VariantBatchQueue) -> None:
    _batch_queues[batch_id] = q


def get_batch_queue(batch_id: str) -> VariantBatchQueue | None:
    return _batch_queues.get(batch_id)
