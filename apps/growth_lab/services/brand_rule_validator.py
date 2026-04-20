"""brand_rule_validator — 品牌规则 gate。

按 `config/brand_rules/{brand_id}.yaml` 读取规则，对单个节点 / 整个 plan 进行校验。

V1 覆盖：
  - 必选关键词（must_keywords）——全 plan 文案至少命中 1 个
  - 禁用词（avoid_keywords）——节点文案命中一个即失败
  - 主图尺寸（aspect_ratio / min_pixels）——从 active_variant asset 中取图
  - 文件大小（max_file_kb）

V2 预留（返回 skipped=True，不影响 gate）：
  - 颜色偏移（product_colors）
  - Logo 遮挡（logo_zones）
"""
from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BRAND_RULE_DIR = _REPO_ROOT / "config" / "brand_rules"

_rule_cache: dict[str, dict[str, Any]] = {}


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore
    except ImportError:
        logger.warning("PyYAML 未安装，品牌规则加载失败")
        return None
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("[BrandRule] yaml 加载失败 %s: %s", path, exc)
        return None


def load_brand_rules(brand_id: str) -> dict[str, Any]:
    """按 brand_id 加载规则，未命中则兜底到 default。"""
    key = (brand_id or "default").strip().lower()
    if key in _rule_cache:
        return _rule_cache[key]
    path = _BRAND_RULE_DIR / f"{key}.yaml"
    data = _load_yaml(path)
    if not data and key != "default":
        data = _load_yaml(_BRAND_RULE_DIR / "default.yaml")
    if not data:
        data = {
            "brand_id": key,
            "brand_name": key,
            "must_keywords": [],
            "avoid_keywords": [],
            "main_image_specs": {"aspect_ratio": "1:1", "min_pixels": 800, "max_file_kb": 500},
            "approval": {"require_all_nodes_pass": False},
        }
    _rule_cache[key] = data
    return data


def reload_brand_rules() -> None:
    _rule_cache.clear()


# ── Image probe ──

def _probe_image(asset_url: str) -> dict[str, Any]:
    """尝试读取图片尺寸与大小。支持 data-uri / 本地路径 / http(s)。失败返回 probed=False。"""
    if not asset_url:
        return {"probed": False, "reason": "no url"}
    try:
        raw: bytes
        if asset_url.startswith("data:"):
            head, _, body = asset_url.partition(",")
            raw = base64.b64decode(body) if "base64" in head else body.encode("utf-8", errors="ignore")
        elif asset_url.startswith("http://") or asset_url.startswith("https://"):
            import requests  # type: ignore
            resp = requests.get(asset_url, timeout=8, proxies={"http": "", "https": ""})
            if resp.status_code != 200:
                return {"probed": False, "reason": f"http {resp.status_code}"}
            raw = resp.content
        else:
            # 支持 /media/... 等本地相对路径
            local = asset_url
            if local.startswith("/"):
                for root in (_REPO_ROOT, Path.cwd()):
                    cand = root / local.lstrip("/")
                    if cand.exists():
                        local = str(cand)
                        break
            if not os.path.exists(local):
                return {"probed": False, "reason": "file not found"}
            with open(local, "rb") as f:
                raw = f.read()
        size_kb = len(raw) / 1024.0
        width = height = 0
        try:
            from PIL import Image  # type: ignore
            with Image.open(io.BytesIO(raw)) as im:
                width, height = im.size
        except Exception as exc:
            logger.debug("[BrandRule] PIL 读取失败 %s", exc)
        return {"probed": True, "size_kb": size_kb, "width": width, "height": height}
    except Exception as exc:
        return {"probed": False, "reason": str(exc)[:80]}


# ── Checks ──

def _check_avoid_keywords(text: str, avoid: list[str]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    low = text or ""
    for w in avoid or []:
        if w and w in low:
            hits.append({"keyword": w, "field_preview": _snippet(low, w)})
    return hits


def _check_must_keywords(texts: list[str], must: list[str]) -> dict[str, Any]:
    if not must:
        return {"required": [], "hit": [], "missing": [], "passed": True}
    blob = " ".join([t or "" for t in texts])
    hit = [w for w in must if w and w in blob]
    missing = [w for w in must if w and w not in blob]
    return {"required": list(must), "hit": hit, "missing": missing, "passed": not missing}


def _snippet(text: str, w: str) -> str:
    idx = text.find(w)
    if idx < 0:
        return ""
    s = max(0, idx - 8)
    e = min(len(text), idx + len(w) + 8)
    return text[s:e]


def _check_image_specs(probe: dict[str, Any], specs: dict[str, Any], aspect_from_node: str) -> dict[str, Any]:
    issues: list[str] = []
    if not probe.get("probed"):
        return {"skipped": True, "reason": probe.get("reason", "probe failed"), "passed": True}
    w, h = int(probe.get("width") or 0), int(probe.get("height") or 0)
    size_kb = float(probe.get("size_kb") or 0)
    target_aspect = (specs.get("aspect_ratio") or aspect_from_node or "1:1").strip()
    min_pixels = int(specs.get("min_pixels") or 0)
    max_file_kb = int(specs.get("max_file_kb") or 0)

    if min_pixels and (w < min_pixels or h < min_pixels):
        issues.append(f"分辨率 {w}x{h} 小于 {min_pixels}px")
    if target_aspect and w and h:
        try:
            a, b = target_aspect.split(":")
            ratio_target = float(a) / float(b)
            ratio_real = w / max(1, h)
            if abs(ratio_target - ratio_real) / max(ratio_target, 0.01) > 0.02:
                issues.append(f"纵横比 {w}:{h} 不符合 {target_aspect}")
        except Exception:
            pass
    if max_file_kb and size_kb > max_file_kb:
        issues.append(f"文件大小 {size_kb:.0f}KB 超过 {max_file_kb}KB")
    return {
        "skipped": False,
        "passed": not issues,
        "width": w, "height": h, "size_kb": round(size_kb, 1),
        "target_aspect": target_aspect,
        "min_pixels": min_pixels,
        "max_file_kb": max_file_kb,
        "issues": issues,
    }


def _active_variant_asset(node: dict[str, Any]) -> tuple[str, str]:
    """返回 (active_variant_id, asset_url)。需要调用方注入 variants 查询。"""
    return node.get("active_variant_id", ""), ""


def validate_node(node: dict[str, Any], *, brand_id: str = "default", variants: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """对单节点做 gate。"""
    rules = load_brand_rules(brand_id)
    variants = variants or []
    # 取 active variant
    active_id = node.get("active_variant_id") or ""
    active = None
    if active_id:
        active = next((v for v in variants if v.get("variant_id") == active_id), None)
    if active is None and variants:
        for v in reversed(variants):
            if v.get("asset_url"):
                active = v
                break
    asset_url = (active or {}).get("asset_url", "")

    # 文案
    text_fields = {
        "title": node.get("title", ""),
        "role": node.get("role", ""),
        "objective": node.get("objective", ""),
        "copy_spec": node.get("copy_spec", ""),
        "visual_spec": node.get("visual_spec", ""),
    }
    hits = _check_avoid_keywords(" ".join(text_fields.values()), rules.get("avoid_keywords", []))

    # 图像
    specs = rules.get("main_image_specs") or {}
    img_report = {"skipped": True, "reason": "no asset", "passed": True}
    if asset_url:
        probe = _probe_image(asset_url)
        img_report = _check_image_specs(probe, specs, node.get("aspect_ratio") or "")

    # VLM 桩
    vlm_checks = [
        {"name": "color_drift", "status": "skipped", "reason": "VLM 接入预留（V1 不跑）"},
        {"name": "logo_occlusion", "status": "skipped", "reason": "VLM 接入预留（V1 不跑）"},
    ]

    passed = (not hits) and bool(img_report.get("passed"))
    return {
        "brand_id": rules.get("brand_id", brand_id),
        "node_id": node.get("node_id", ""),
        "passed": passed,
        "avoid_hits": hits,
        "image_check": img_report,
        "vlm_checks": vlm_checks,
        "text_fields_preview": {k: (v or "")[:80] for k, v in text_fields.items()},
        "asset_url": asset_url,
    }


def validate_node_dict(node: dict[str, Any], *, brand_id: str = "default", store: Any = None) -> dict[str, Any]:
    """方便 routes.py 调用——自动查 variants。"""
    variants: list[dict[str, Any]] = []
    try:
        if store is None:
            from apps.growth_lab.storage.growth_lab_store import GrowthLabStore
            store = GrowthLabStore()
        variants = store.list_workspace_variants(node.get("node_id", "")) or []
    except Exception:
        variants = []
    return validate_node(node, brand_id=brand_id, variants=variants)


def validate_plan(plan: dict[str, Any], nodes: list[dict[str, Any]], variants_by_node: dict[str, list[dict[str, Any]]], *, brand_id: str = "") -> dict[str, Any]:
    """对整个 plan gate。"""
    bid = brand_id or plan.get("brand_id") or "default"
    rules = load_brand_rules(bid)
    node_reports = []
    all_texts: list[str] = []
    for n in nodes:
        rep = validate_node(n, brand_id=bid, variants=variants_by_node.get(n["node_id"], []))
        node_reports.append(rep)
        for v in rep.get("text_fields_preview", {}).values():
            all_texts.append(v)

    must_report = _check_must_keywords(all_texts, rules.get("must_keywords") or [])
    require_all = bool((rules.get("approval") or {}).get("require_all_nodes_pass"))
    failed_nodes = [r["node_id"] for r in node_reports if not r.get("passed")]
    plan_passed = must_report["passed"] and (not failed_nodes if require_all else True)

    return {
        "brand_id": rules.get("brand_id", bid),
        "brand_name": rules.get("brand_name", ""),
        "plan_id": plan.get("plan_id", ""),
        "rules": rules,
        "passed": plan_passed,
        "must_keywords": must_report,
        "require_all_nodes_pass": require_all,
        "node_reports": node_reports,
        "summary": {
            "total": len(node_reports),
            "passed": sum(1 for r in node_reports if r.get("passed")),
            "failed": len(failed_nodes),
        },
    }
