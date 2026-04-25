"""SystemAssetService — 三主线产物统一资产视图。

设计目标（参考 docs/IA_AND_PAGES.md）：
- ``list_assets`` 聚合三处来源的"已存在产物"，不要求事先 register；
- ``register`` 用于显式登记一条 SystemAsset（写入 JSON 持久化），方便人工标注或 cron 回刷；
- 对每个来源的失败保持容错（单个 lane 异常不影响其他 lane 输出）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from apps.intel_hub.domain.system_asset import SystemAsset


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class SystemAssetService:
    def __init__(
        self,
        *,
        storage_path: str | Path = "data/runtime_data/system_assets.json",
        review_store: Any | None = None,
        cp_flow: Any | None = None,
        growth_store_factory: Any | None = None,
    ) -> None:
        self._storage_path = Path(storage_path)
        self._review_store = review_store
        self._cp_flow = cp_flow
        self._growth_store_factory = growth_store_factory

    # ── 持久化 ────────────────────────────────────────────────

    def _load_registered(self) -> list[dict[str, Any]]:
        if not self._storage_path.exists():
            return []
        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_registered(self, items: list[dict[str, Any]]) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def register(self, asset: SystemAsset) -> SystemAsset:
        """写入或覆盖一条已显式登记的系统资产。"""
        items = self._load_registered()
        items = [it for it in items if it.get("asset_id") != asset.asset_id]
        items.append(json.loads(asset.model_dump_json()))
        self._save_registered(items)
        return asset

    def remove(self, asset_id: str) -> bool:
        items = self._load_registered()
        next_items = [it for it in items if it.get("asset_id") != asset_id]
        if len(next_items) == len(items):
            return False
        self._save_registered(next_items)
        return True

    # ── 聚合视图 ──────────────────────────────────────────────

    def list_assets(
        self,
        *,
        lane: str | None = None,
        lens: str | None = None,
        status: str | None = None,
        asset_type: str | None = None,
    ) -> list[SystemAsset]:
        assets: list[SystemAsset] = []

        # 1) content_note：promoted 卡片的 asset_bundle
        if lane in (None, "content_note"):
            try:
                assets.extend(self._aggregate_content_notes())
            except Exception:
                pass

        # 2) growth_lab：asset_performance_cards
        if lane in (None, "growth_lab"):
            try:
                assets.extend(self._aggregate_growth_lab_assets())
            except Exception:
                pass

        # 3) workspace_bundle：workspace_plans
        if lane in (None, "workspace_bundle"):
            try:
                assets.extend(self._aggregate_workspace_bundles())
            except Exception:
                pass

        # 4) 显式 register 的资产（合并去重，按 asset_id 后到先到覆盖）
        registered = self._load_registered()
        seen = {a.asset_id for a in assets}
        for raw in registered:
            try:
                a = SystemAsset(**raw)
            except Exception:
                continue
            if a.asset_id in seen:
                # 已聚合产生过同 id，注册条目优先覆盖
                assets = [x for x in assets if x.asset_id != a.asset_id]
            assets.append(a)
            seen.add(a.asset_id)

        # 过滤
        def _ok(a: SystemAsset) -> bool:
            if lens and a.lens_id != lens:
                return False
            if status and a.status != status:
                return False
            if asset_type and a.asset_type != asset_type:
                return False
            return True

        def _sort_key(a: SystemAsset) -> float:
            ts = a.created_at
            if ts is None:
                return 0.0
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.timestamp()

        return sorted(
            (a for a in assets if _ok(a)),
            key=_sort_key,
            reverse=True,
        )

    # ── lane 聚合：content_note ──────────────────────────────

    def _aggregate_content_notes(self) -> Iterable[SystemAsset]:
        if not self._review_store or not self._cp_flow:
            return []
        try:
            promoted = self._review_store.list_cards(
                opportunity_status="promoted",
                page=1,
                page_size=200,
            )
            items = promoted.get("items", []) if isinstance(promoted, dict) else []
        except Exception:
            return []

        out: list[SystemAsset] = []
        for card in items:
            opp_id = getattr(card, "opportunity_id", None) or (
                card.get("opportunity_id") if isinstance(card, dict) else None
            )
            if not opp_id:
                continue
            title = getattr(card, "title", None) or (
                card.get("title") if isinstance(card, dict) else opp_id[:12]
            )
            lens_id = getattr(card, "lens_id", None) or (
                card.get("lens_id") if isinstance(card, dict) else None
            )

            try:
                sess = self._cp_flow.get_session_data(opp_id)
            except Exception:
                sess = {}
            bundle = sess.get("asset_bundle") if isinstance(sess, dict) else None

            thumbs: list[str] = []
            if isinstance(bundle, dict):
                for key in ("hero_image", "cover", "main_image"):
                    if bundle.get(key):
                        thumbs.append(str(bundle[key]))
                for img in bundle.get("images", [])[:6]:
                    if isinstance(img, dict) and img.get("url"):
                        thumbs.append(str(img["url"]))
                    elif isinstance(img, str):
                        thumbs.append(img)

            status: str = "ready" if bundle else "draft"
            out.append(
                SystemAsset(
                    asset_id=f"cn:{opp_id}",
                    source_lane="content_note",
                    source_ref=opp_id,
                    lens_id=lens_id,
                    asset_type="xhs_note" if bundle else "asset_bundle",
                    title=title or opp_id,
                    thumbnails=thumbs,
                    status=status,  # type: ignore[arg-type]
                    lineage={
                        "planning_url": f"/planning/{opp_id}",
                        "visual_url": f"/planning/{opp_id}/visual-builder",
                        "brief_url": f"/content-planning/brief/{opp_id}",
                        "strategy_url": f"/content-planning/strategy/{opp_id}",
                        "asset_bundle_url": f"/content-planning/assets/{opp_id}",
                        "opportunity_id": opp_id,
                    },
                    created_at=_now_utc(),
                )
            )
        return out

    # ── lane 聚合：growth_lab ────────────────────────────────

    def _aggregate_growth_lab_assets(self) -> Iterable[SystemAsset]:
        store = self._call_growth_store()
        if store is None:
            return []
        try:
            cards = store.list_asset_performance_cards(limit=500)
        except Exception:
            cards = []
        out: list[SystemAsset] = []
        for c in cards or []:
            cid = c.get("card_id") or c.get("id") or ""
            if not cid:
                continue
            spec_id = c.get("spec_id") or c.get("source_spec_id") or ""
            asset_url = c.get("asset_url") or c.get("generated_image_url") or ""
            title = c.get("name") or c.get("title") or f"Growth Asset {cid[:8]}"
            raw_status = (c.get("status") or "ready").lower()
            status_map = {
                "promoted": "published",
                "winning": "published",
                "ready": "ready",
                "draft": "draft",
                "archived": "archived",
            }
            status = status_map.get(raw_status, "ready")
            out.append(
                SystemAsset(
                    asset_id=f"gl:{cid}",
                    source_lane="growth_lab",
                    source_ref=spec_id or cid,
                    lens_id=c.get("lens_id"),
                    asset_type="growth_test_card",
                    title=title,
                    thumbnails=[asset_url] if asset_url else [],
                    status=status,  # type: ignore[arg-type]
                    lineage={
                        "asset_graph_url": "/growth-lab/assets",
                        "test_id": c.get("test_id") or "",
                        "spec_id": spec_id,
                        "card_id": cid,
                    },
                    created_at=self._safe_datetime(c.get("created_at")),
                )
            )
        return out

    # ── lane 聚合：workspace_bundle ──────────────────────────

    def _aggregate_workspace_bundles(self) -> Iterable[SystemAsset]:
        store = self._call_growth_store()
        if store is None:
            return []
        try:
            plans = store.list_workspace_plans(limit=200)
        except Exception:
            plans = []
        out: list[SystemAsset] = []
        for p in plans or []:
            pid = p.get("plan_id") or p.get("id") or ""
            if not pid:
                continue
            intent = p.get("intent") or {}
            spec_id = intent.get("source_spec_id", "") if isinstance(intent, dict) else ""
            output_types = intent.get("output_types", []) if isinstance(intent, dict) else []
            atype = "main_image_set"
            if "video_shots" in output_types:
                atype = "video"
            elif "detail" in output_types:
                atype = "detail_gallery"
            elif "buyer_show" in output_types:
                atype = "buyer_show"
            elif "competitor" in output_types:
                atype = "competitor_benchmark"

            raw_status = (p.get("status") or "draft").lower()
            status_map = {
                "published": "published",
                "ready": "ready",
                "draft": "draft",
                "archived": "archived",
            }
            status = status_map.get(raw_status, "draft")

            thumbs: list[str] = []
            try:
                nodes = store.list_workspace_nodes(plan_id=pid)
                for n in nodes[:6]:
                    av_id = n.get("active_variant_id")
                    if not av_id:
                        continue
                    try:
                        v = store.get_workspace_variant(av_id) if hasattr(store, "get_workspace_variant") else None
                    except Exception:
                        v = None
                    if v and v.get("generated_image_url"):
                        thumbs.append(v["generated_image_url"])
            except Exception:
                pass

            title = (
                intent.get("product_name") if isinstance(intent, dict) else None
            ) or f"套图项目 {pid[:8]}"

            out.append(
                SystemAsset(
                    asset_id=f"wb:{pid}",
                    source_lane="workspace_bundle",
                    source_ref=spec_id or pid,
                    lens_id=p.get("lens_id"),
                    asset_type=atype,  # type: ignore[arg-type]
                    title=title,
                    thumbnails=thumbs,
                    status=status,  # type: ignore[arg-type]
                    lineage={
                        "workspace_url": "/growth-lab/workspace",
                        "plan_id": pid,
                        "spec_id": spec_id,
                        "output_types": output_types,
                    },
                    created_at=self._safe_datetime(p.get("created_at")),
                )
            )
        return out

    # ── 工具 ─────────────────────────────────────────────────

    def _call_growth_store(self) -> Any | None:
        if not self._growth_store_factory:
            return None
        try:
            return self._growth_store_factory()
        except Exception:
            return None

    @staticmethod
    def _safe_datetime(v: Any) -> datetime:
        dt: datetime | None = None
        if isinstance(v, datetime):
            dt = v
        elif isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                dt = None
        if dt is None:
            return _now_utc()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
