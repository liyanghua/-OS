"""WorkspaceExporter — Production-ready 导出。

三种导出：
1. PNG 包 / ZIP — 当前 plan 所有 generated 变体的图片 + 元数据 JSON
2. Excel 分镜单 — 视频 Frame 专用（mvp 用 CSV，无额外依赖）
3. 推送资产图谱 — 为已 approved 节点生成 AssetPerformanceCard

因本 MVP 不下载远程 URL（图片可能在外部 OSS），
ZIP 内保存 metadata.json + manifest.csv，图片以 URL 形式索引；
可后续用 requests 下载并打包。
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)


class WorkspaceExporter:
    def __init__(self, store: GrowthLabStore | None = None) -> None:
        self._store = store or GrowthLabStore()

    # ── 导出 ZIP ──

    def export_plan_zip(self, plan_id: str) -> tuple[bytes, str]:
        plan = self._store.get_workspace_plan(plan_id)
        if not plan:
            raise ValueError(f"plan not found: {plan_id}")
        frames = self._store.list_workspace_frames(plan_id)
        nodes = self._store.list_workspace_nodes(plan_id=plan_id)

        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
            # metadata.json
            meta = {
                "plan_id": plan_id,
                "exported_at": datetime.now(UTC).isoformat(),
                "product": (plan.get("intent") or {}).get("product_name", ""),
                "audience": (plan.get("intent") or {}).get("audience", ""),
                "frame_count": len(frames),
                "node_count": len(nodes),
                "frames": frames,
                "nodes": nodes,
            }
            zf.writestr("metadata.json", json.dumps(meta, ensure_ascii=False, indent=2, default=str))

            # manifest.csv — 每个节点一行
            csv_bio = io.StringIO()
            writer = csv.writer(csv_bio)
            writer.writerow([
                "frame_key", "template_id", "slot_index", "role",
                "result_type", "aspect_ratio", "status",
                "active_variant_url", "copy_spec", "visual_spec",
            ])
            for n in nodes:
                frame = next((f for f in frames if f["frame_id"] == n.get("frame_id")), {})
                active_url = ""
                if n.get("active_variant_id"):
                    v = self._store.get_workspace_variant(n["active_variant_id"])
                    active_url = (v or {}).get("asset_url", "")
                writer.writerow([
                    frame.get("frame_key", ""),
                    frame.get("template_id", ""),
                    n.get("slot_index", ""),
                    n.get("role", ""),
                    n.get("result_type", ""),
                    n.get("aspect_ratio", ""),
                    n.get("status", ""),
                    active_url,
                    (n.get("copy_spec") or "").replace("\n", " "),
                    (n.get("visual_spec") or "").replace("\n", " "),
                ])
            zf.writestr("manifest.csv", csv_bio.getvalue())

            # 分镜表（视频 Frame）
            video_frames = [f for f in frames if f["frame_key"] == "video_shots"]
            if video_frames:
                csv2 = io.StringIO()
                w2 = csv.writer(csv2)
                w2.writerow([
                    "frame_id", "slot", "role", "shot_size", "camera_move",
                    "real_person", "visual", "copy", "asset_url",
                ])
                for f in video_frames:
                    vnodes = [n for n in nodes if n.get("frame_id") == f["frame_id"]]
                    for n in sorted(vnodes, key=lambda x: x.get("slot_index", 0)):
                        extra = n.get("extra", {}) or {}
                        asset_url = ""
                        if n.get("active_variant_id"):
                            v = self._store.get_workspace_variant(n["active_variant_id"])
                            asset_url = (v or {}).get("asset_url", "")
                        w2.writerow([
                            f["frame_id"], n.get("slot_index", ""),
                            n.get("role", ""), extra.get("shot_size", ""),
                            extra.get("camera_move", ""), extra.get("real_person", ""),
                            (n.get("visual_spec") or "").replace("\n", " "),
                            (n.get("copy_spec") or "").replace("\n", " "),
                            asset_url,
                        ])
                zf.writestr("video_shot_list.csv", csv2.getvalue())

            # 竞品拆解汇总
            comp_nodes = [n for n in nodes if n.get("result_type") == "competitor_ref"]
            if comp_nodes:
                comp_data = []
                for n in comp_nodes:
                    extra = n.get("extra", {}) or {}
                    if extra.get("competitor_analysis"):
                        comp_data.append({
                            "slot": n.get("slot_index", ""),
                            "role": n.get("role", ""),
                            "image_url": extra.get("competitor_image_url", ""),
                            "analysis": extra["competitor_analysis"],
                        })
                if comp_data:
                    zf.writestr(
                        "competitor_analysis.json",
                        json.dumps(comp_data, ensure_ascii=False, indent=2, default=str),
                    )

            # README
            zf.writestr("README.txt", self._render_readme(plan, frames, nodes))

        return bio.getvalue(), f"workspace_plan_{plan_id}.zip"

    @staticmethod
    def _render_readme(plan: dict, frames: list[dict], nodes: list[dict]) -> str:
        intent = plan.get("intent") or {}
        done = sum(1 for n in nodes if n.get("status") in {"generated", "approved", "reviewed"})
        return (
            f"视觉工作台导出包\n"
            f"================\n\n"
            f"商品：{intent.get('product_name', '')}\n"
            f"人群：{intent.get('audience', '')}\n"
            f"Plan ID：{plan.get('plan_id', '')}\n"
            f"Frame 数量：{len(frames)}（{', '.join(f.get('frame_key', '') for f in frames)}）\n"
            f"节点总数：{len(nodes)}（其中 {done} 个已生成）\n\n"
            f"文件说明：\n"
            f"- metadata.json        完整 plan/frame/node 序列化\n"
            f"- manifest.csv         节点-资产索引（交付摄影/美工/剪辑）\n"
            f"- video_shot_list.csv  视频分镜单（如果有视频 Frame）\n"
            f"- competitor_analysis.json  竞品 32 维度拆解（如果有竞品 Frame）\n"
        )

    # ── 推送资产图谱 ──

    def push_to_asset_graph(self, plan_id: str) -> list[dict]:
        """把 approved / reviewed 节点生成 AssetPerformanceCard。"""
        plan = self._store.get_workspace_plan(plan_id)
        if not plan:
            raise ValueError(f"plan not found: {plan_id}")
        nodes = self._store.list_workspace_nodes(plan_id=plan_id)
        intent = plan.get("intent") or {}

        pushed: list[dict] = []
        for n in nodes:
            if n.get("status") not in {"approved", "reviewed"}:
                continue
            variant_id = n.get("active_variant_id", "")
            if not variant_id:
                continue
            v = self._store.get_workspace_variant(variant_id) or {}
            image_url = v.get("asset_url", "")
            if not image_url:
                continue

            asset_id = f"ws_{n['node_id'][:12]}_{uuid.uuid4().hex[:6]}"
            card = {
                "asset_id": asset_id,
                "asset_type": "high_performer" if n.get("status") == "approved" else "main_image_template",
                "source_platform": "workspace",
                "source_variant_id": variant_id,
                "source_test_task_id": "",
                "linked_selling_points": [intent.get("source_spec_id", "")] if intent.get("source_spec_id") else [],
                "linked_patterns": [n.get("template_slot_ref", "")],
                "linked_scenarios": intent.get("scenario_refs", []),
                "best_metrics": {},
                "usage_count": 0,
                "reusable": True,
                "reuse_directions": [],
                "tags": [n.get("result_type", ""), n.get("role", "")],
                "image_url": image_url,
                "video_url": "",
                "description": f"{intent.get('product_name', '')} · {n.get('role', '')}",
                "workspace_id": plan.get("workspace_id", ""),
                "brand_id": plan.get("brand_id", ""),
                "status": "active",
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self._store.save_asset_performance_card(card)
            pushed.append(card)

        logger.info("push_to_asset_graph: plan=%s pushed=%d", plan_id, len(pushed))
        return pushed

    # ── 最终结果卡 ──

    def render_final_result_card(self, node_id: str) -> dict:
        """为 approved 节点产出标准化"最终结果卡"。"""
        n = self._store.get_workspace_node(node_id)
        if not n:
            raise ValueError(f"node not found: {node_id}")
        plan = self._store.get_workspace_plan(n.get("plan_id", "")) or {}
        frame = self._store.get_workspace_frame(n.get("frame_id", "")) or {}
        variant = self._store.get_workspace_variant(n.get("active_variant_id", "")) if n.get("active_variant_id") else None

        intent = plan.get("intent") or {}
        return {
            "node_id": node_id,
            "status": n.get("status", ""),
            "title": n.get("title", ""),
            "role": n.get("role", ""),
            "result_type": n.get("result_type", ""),
            "aspect_ratio": n.get("aspect_ratio", ""),
            "asset_url": (variant or {}).get("asset_url", ""),
            "source": {
                "intent": intent,
                "template_slot_ref": n.get("template_slot_ref", ""),
                "frame_template_id": frame.get("template_id", ""),
                "brand_rule_refs": n.get("brand_rule_refs", []),
            },
            "copy_spec": n.get("copy_spec", ""),
            "visual_spec": n.get("visual_spec", ""),
            "variant_count": len(n.get("variant_ids", []) or []),
            "promoted_to_asset_graph": False,  # 推送后由调用方更新
        }
