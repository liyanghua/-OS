"""WorkspaceExporter — Production-ready 导出。

三种导出：
1. PNG 包 / ZIP — 当前 plan 所有 approved/reviewed/generated 变体的图片 + 元数据 JSON
2. Excel 分镜单 — 视频 Frame 专用（mvp 用 CSV，无额外依赖）
3. 推送资产图谱 — 为已 approved 节点生成 AssetPerformanceCard

生产级行为：
- 真实下载远程 URL 到 zip
- 主图按 aspect_ratio / min_pixels / max_file_kb 做 Pillow 检查 + 可选再压缩
- brand_rule gate 在整个 plan 级别兜底
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.growth_lab.storage.growth_lab_store import GrowthLabStore

logger = logging.getLogger(__name__)


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _download_asset(asset_url: str) -> bytes | None:
    """支持 data-uri / 本地路径 / http(s) 三种。失败返回 None。"""
    if not asset_url:
        return None
    try:
        if asset_url.startswith("data:"):
            head, _, body = asset_url.partition(",")
            return base64.b64decode(body) if "base64" in head else body.encode("utf-8", errors="ignore")
        if asset_url.startswith("http://") or asset_url.startswith("https://"):
            import requests  # type: ignore
            resp = requests.get(asset_url, timeout=15, proxies={"http": "", "https": ""})
            if resp.status_code != 200:
                logger.warning("[Exporter] 下载失败 %s status=%s", asset_url, resp.status_code)
                return None
            return resp.content
        # 本地路径
        local = asset_url
        if local.startswith("/"):
            for root in (_REPO_ROOT, Path.cwd()):
                cand = root / local.lstrip("/")
                if cand.exists():
                    local = str(cand)
                    break
        if os.path.exists(local):
            with open(local, "rb") as f:
                return f.read()
    except Exception as exc:
        logger.warning("[Exporter] 资产读取异常 %s: %s", asset_url, exc)
    return None


def _ensure_spec(raw: bytes, *, target_aspect: str, min_pixels: int, max_file_kb: int) -> tuple[bytes, str, dict[str, Any]]:
    """主图规格修正：返回 (final_bytes, ext, report)。
    - 若 PIL 不可用：原样返回 + skipped 报告
    - 若尺寸不足：仅标记，不强行放大
    - 若比例偏差：中心裁剪到 target_aspect
    - 若超过 max_file_kb：JPEG 质量降档
    """
    report: dict[str, Any] = {"adjusted": [], "issues": []}
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return raw, "png", {"skipped": True, "reason": "Pillow 未安装"}

    try:
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGB") if im.mode != "RGB" else im
    except Exception as exc:
        return raw, "png", {"skipped": True, "reason": f"Image 打开失败：{exc}"}

    w, h = im.size
    report["original_size"] = [w, h]

    # 比例纠正
    if target_aspect and ":" in target_aspect:
        try:
            a, b = target_aspect.split(":")
            ratio_target = float(a) / float(b)
            ratio_real = w / max(1, h)
            if abs(ratio_target - ratio_real) / max(ratio_target, 0.01) > 0.02:
                if ratio_real > ratio_target:
                    new_w = int(h * ratio_target)
                    left = (w - new_w) // 2
                    im = im.crop((left, 0, left + new_w, h))
                else:
                    new_h = int(w / ratio_target)
                    top = (h - new_h) // 2
                    im = im.crop((0, top, w, top + new_h))
                report["adjusted"].append(f"center-crop to {target_aspect}")
                w, h = im.size
        except Exception:
            pass

    # 尺寸检查（V1 不强行 upscale）
    if min_pixels and (w < min_pixels or h < min_pixels):
        report["issues"].append(f"分辨率 {w}x{h} < {min_pixels}px（未自动放大）")

    # 尝试 PNG 输出
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    size_kb = len(png_bytes) / 1024.0

    if max_file_kb and size_kb > max_file_kb:
        # JPEG 降档
        for q in (90, 85, 80, 75, 70, 65):
            jbuf = io.BytesIO()
            im.save(jbuf, format="JPEG", quality=q, optimize=True)
            jb = jbuf.getvalue()
            if len(jb) / 1024.0 <= max_file_kb:
                report["adjusted"].append(f"jpeg q={q}, {len(jb)/1024:.0f}KB")
                report["final_size_kb"] = round(len(jb)/1024.0, 1)
                return jb, "jpg", report
        report["issues"].append(f"PNG/JPEG 均超 {max_file_kb}KB（最小质量也未达标）")
        return png_bytes, "png", report
    report["final_size_kb"] = round(size_kb, 1)
    report["final_size"] = list(im.size)
    return png_bytes, "png", report


class WorkspaceExporter:
    def __init__(self, store: GrowthLabStore | None = None) -> None:
        self._store = store or GrowthLabStore()

    # ── 导出 ZIP ──

    def export_plan_zip(self, plan_id: str, *, force: bool = False) -> tuple[bytes, str]:
        """生产级导出包。

        force=True：忽略品牌规则 gate 失败，照常输出（report 里仍会标红）。
        """
        plan = self._store.get_workspace_plan(plan_id)
        if not plan:
            raise ValueError(f"plan not found: {plan_id}")
        frames = self._store.list_workspace_frames(plan_id)
        nodes = self._store.list_workspace_nodes(plan_id=plan_id)

        # 跑品牌规则 gate
        variants_by_node = {
            n["node_id"]: self._store.list_workspace_variants(n["node_id"]) or []
            for n in nodes
        }
        rule_report: dict[str, Any] = {}
        try:
            from apps.growth_lab.services.brand_rule_validator import validate_plan
            brand_id = plan.get("brand_id") or "default"
            rule_report = validate_plan(plan, nodes, variants_by_node, brand_id=brand_id)
        except Exception as exc:
            rule_report = {"skipped": True, "reason": str(exc), "passed": True, "node_reports": []}

        require_all = bool((rule_report.get("rules") or {}).get("approval", {}).get("require_all_nodes_pass"))
        if require_all and not rule_report.get("passed") and not force:
            # 强策略：gate 未过禁止导出
            raise ValueError(f"品牌规则 gate 未通过（require_all_nodes_pass=True）。rule_report={json.dumps({'passed': rule_report.get('passed'), 'failed_nodes': [r['node_id'] for r in rule_report.get('node_reports', []) if not r.get('passed')]}, ensure_ascii=False)}")

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
            zf.writestr("brand_rule_report.json", json.dumps(rule_report, ensure_ascii=False, indent=2, default=str))

            # 主图目录（主图 frame → 下载 + Pillow 规格修正）
            main_image_specs = ((rule_report.get("rules") or {}).get("main_image_specs") or {})
            main_csv = io.StringIO()
            main_writer = csv.writer(main_csv)
            main_writer.writerow([
                "slot", "role", "file", "variant_id", "approved_at",
                "rule_pass", "headline", "size_kb", "adjusted",
            ])
            main_image_exported = 0
            for n in nodes:
                if n.get("result_type") != "main_image":
                    continue
                variant_id = n.get("active_variant_id", "")
                asset_url = ""
                if variant_id:
                    v = self._store.get_workspace_variant(variant_id)
                    asset_url = (v or {}).get("asset_url", "")
                if not asset_url:
                    continue
                node_report = next((r for r in (rule_report.get("node_reports") or []) if r.get("node_id") == n.get("node_id")), {})
                rule_pass = node_report.get("passed", True)
                if require_all and not rule_pass and not force:
                    continue  # 跳过未过 gate 的节点
                raw = _download_asset(asset_url)
                if raw is None:
                    continue
                final_bytes, ext, probe = _ensure_spec(
                    raw,
                    target_aspect=(main_image_specs.get("aspect_ratio") or n.get("aspect_ratio", "1:1")),
                    min_pixels=int(main_image_specs.get("min_pixels") or 0),
                    max_file_kb=int(main_image_specs.get("max_file_kb") or 0),
                )
                slot_index = int(n.get("slot_index") or (main_image_exported + 1))
                fname = f"main_image/frame_{slot_index:02d}.{ext}"
                zf.writestr(fname, final_bytes)
                main_image_exported += 1
                main_writer.writerow([
                    slot_index,
                    n.get("role", ""),
                    fname,
                    variant_id,
                    n.get("approved_at", "") or "",
                    "Y" if rule_pass else "N",
                    (n.get("copy_spec") or "").split("\n")[0][:80],
                    probe.get("final_size_kb", ""),
                    "; ".join(probe.get("adjusted", []) or []),
                ])
            if main_image_exported:
                zf.writestr("main_image/manifest.csv", main_csv.getvalue())

            # 全节点 manifest.csv（兼容旧路径）
            csv_bio = io.StringIO()
            writer = csv.writer(csv_bio)
            writer.writerow([
                "frame_key", "template_id", "slot_index", "role",
                "result_type", "aspect_ratio", "status",
                "active_variant_url", "copy_spec", "visual_spec",
                "rule_pass",
            ])
            for n in nodes:
                frame = next((f for f in frames if f["frame_id"] == n.get("frame_id")), {})
                active_url = ""
                if n.get("active_variant_id"):
                    v = self._store.get_workspace_variant(n["active_variant_id"])
                    active_url = (v or {}).get("asset_url", "")
                node_report = next((r for r in (rule_report.get("node_reports") or []) if r.get("node_id") == n.get("node_id")), {})
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
                    "Y" if node_report.get("passed", True) else "N",
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
            zf.writestr("README.txt", self._render_readme(plan, frames, nodes, rule_report))

        return bio.getvalue(), f"workspace_plan_{plan_id}_production.zip"

    @staticmethod
    def _render_readme(plan: dict, frames: list[dict], nodes: list[dict], rule_report: dict | None = None) -> str:
        intent = plan.get("intent") or {}
        done = sum(1 for n in nodes if n.get("status") in {"generated", "approved", "reviewed"})
        rr = rule_report or {}
        rr_summary = rr.get("summary") or {}
        return (
            f"视觉工作台 · 生产级导出包\n"
            f"==========================\n\n"
            f"商品：{intent.get('product_name', '')}\n"
            f"人群：{intent.get('audience', '')}\n"
            f"Plan ID：{plan.get('plan_id', '')}\n"
            f"Frame 数量：{len(frames)}（{', '.join(f.get('frame_key', '') for f in frames)}）\n"
            f"节点总数：{len(nodes)}（其中 {done} 个已生成）\n"
            f"品牌：{rr.get('brand_name') or rr.get('brand_id') or '-'}\n"
            f"品牌规则 gate：{'通过' if rr.get('passed') else '未通过'}"
            f"（通过 {rr_summary.get('passed', 0)}/{rr_summary.get('total', 0)}）\n\n"
            f"文件说明：\n"
            f"- main_image/frame_XX.(png|jpg)  主图 5 张（已按品牌规格裁剪/压缩）\n"
            f"- main_image/manifest.csv        主图清单\n"
            f"- manifest.csv                   全节点-资产索引\n"
            f"- metadata.json                  完整 plan/frame/node 序列化\n"
            f"- brand_rule_report.json         品牌规则 gate 结果\n"
            f"- video_shot_list.csv            视频分镜单（如有）\n"
            f"- competitor_analysis.json       竞品 32 维度拆解（如有）\n"
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

    # ── 沉淀为模板样例 ──

    def promote_to_template_asset(
        self,
        node_id: str,
        *,
        asset_root: str | Path | None = None,
    ) -> dict:
        """把 approved 节点的 active 变体 + 上下文落盘到 assets/promoted_main_images/。

        写入内容：
        - asset YAML（title、角色、slot 语义、intent 摘要、brand_rule、来源 template_slot_ref）
        - 对应图片文件（.png 或原始扩展名）

        返回 {template_id, yaml_path, image_path}。
        """
        n = self._store.get_workspace_node(node_id)
        if not n:
            raise ValueError(f"node not found: {node_id}")
        if n.get("status") != "approved":
            raise ValueError(f"只有 approved 节点可沉淀；当前 status={n.get('status')}")
        variant_id = n.get("active_variant_id", "")
        variant = self._store.get_workspace_variant(variant_id) if variant_id else None
        if not variant or not variant.get("asset_url"):
            raise ValueError("active 变体缺失或无 asset_url")
        plan = self._store.get_workspace_plan(n.get("plan_id", "")) or {}
        frame = self._store.get_workspace_frame(n.get("frame_id", "")) or {}
        intent = plan.get("intent") or {}

        root = Path(asset_root) if asset_root else (_REPO_ROOT / "assets" / "promoted_main_images")
        root.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        short_id = (node_id or uuid.uuid4().hex)[:10]
        slug = f"{stamp}_{short_id}"
        yaml_path = root / f"{slug}.yaml"
        img_name = f"{slug}.png"
        image_path = root / img_name

        # 下载并写图片（失败时回退存 asset_url 字段）
        data = _download_asset(variant["asset_url"])
        if data:
            image_path.write_bytes(data)
            relative_image = f"./{img_name}"
        else:
            relative_image = variant["asset_url"]
            image_path = None  # type: ignore

        template_id = f"promoted_{slug}"
        payload: dict[str, Any] = {
            "asset_id": template_id,
            "schema_version": "promoted_main_image_v1",
            "title": n.get("title") or f"{frame.get('title','')}·{n.get('role','')}",
            "asset_type": "promoted_main_image",
            "status": "active",
            "language": "zh-CN",
            "created_at": stamp,
            "source": {
                "plan_id": n.get("plan_id", ""),
                "frame_id": n.get("frame_id", ""),
                "node_id": node_id,
                "variant_id": variant_id,
                "template_slot_ref": n.get("template_slot_ref", ""),
                "frame_template_id": frame.get("template_id", ""),
            },
            "business_context": {
                "product_category": intent.get("product_category") or intent.get("category", ""),
                "product_name": intent.get("product_name", ""),
                "brand_name": intent.get("brand_name") or intent.get("brand_id", ""),
                "target_audience": intent.get("target_audience") or [],
                "must_have": intent.get("must_have") or [],
                "avoid": intent.get("avoid") or [],
            },
            "slot_semantics": {
                "role": n.get("role", ""),
                "visual_spec": n.get("visual_spec", ""),
                "copy_spec": n.get("copy_spec", ""),
                "aspect_ratio": n.get("aspect_ratio", ""),
            },
            "brand_rule_refs": n.get("brand_rule_refs", []),
            "rule_report": n.get("rule_report", {}),
            "image": {
                "path": relative_image,
                "prompt_sent": variant.get("prompt_sent", ""),
                "provider": variant.get("provider", ""),
            },
        }
        try:
            import yaml  # type: ignore
            yaml_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        except Exception:
            yaml_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info("promote_to_template_asset: node=%s yaml=%s image=%s",
                    node_id, yaml_path, image_path)
        return {
            "ok": True,
            "template_id": template_id,
            "yaml_path": str(yaml_path.relative_to(_REPO_ROOT)) if yaml_path.exists() else str(yaml_path),
            "image_path": str(image_path.relative_to(_REPO_ROOT)) if image_path and image_path.exists() else relative_image,
            "path": str(yaml_path),
        }

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
