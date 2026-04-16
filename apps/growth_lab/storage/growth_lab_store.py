"""GrowthLabStore — SQLite 持久化，管理裂变系统全部对象。

遵循现有 XHSReviewStore 模式：payload_json + 索引列。
自迁移：启动时检测并补表/补列，不引入迁移框架。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "growth_lab.sqlite"


class GrowthLabStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── 初始化 ──────────────────────────────────────────────────

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trend_opportunities (
                    opportunity_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    source_platform TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT 'trend',
                    freshness_score REAL NOT NULL DEFAULT 0.5,
                    actionability_score REAL NOT NULL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'new',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS selling_point_specs (
                    spec_id TEXT PRIMARY KEY,
                    core_claim TEXT NOT NULL DEFAULT '',
                    confidence_score REAL NOT NULL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'draft',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS main_image_variants (
                    variant_id TEXT PRIMARY KEY,
                    source_selling_point_id TEXT NOT NULL DEFAULT '',
                    platform TEXT NOT NULL DEFAULT '',
                    sku_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    generated_image_url TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS first3s_variants (
                    variant_id TEXT PRIMARY KEY,
                    source_selling_point_id TEXT NOT NULL DEFAULT '',
                    platform TEXT NOT NULL DEFAULT '',
                    key_hook_type TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_tasks (
                    task_id TEXT PRIMARY KEY,
                    source_variant_id TEXT NOT NULL DEFAULT '',
                    variant_type TEXT NOT NULL DEFAULT 'main_image',
                    platform TEXT NOT NULL DEFAULT '',
                    store_id TEXT NOT NULL DEFAULT '',
                    sku_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS result_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    date TEXT NOT NULL DEFAULT '',
                    overall_result TEXT NOT NULL DEFAULT 'pending',
                    ctr REAL,
                    refund_rate REAL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES test_tasks(task_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS amplification_plans (
                    plan_id TEXT PRIMARY KEY,
                    based_on_task_id TEXT NOT NULL,
                    amplification_type TEXT NOT NULL DEFAULT 'original_link_scale',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'proposed',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS asset_performance_cards (
                    asset_id TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL DEFAULT 'high_performer',
                    source_platform TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pattern_templates (
                    template_id TEXT PRIMARY KEY,
                    template_type TEXT NOT NULL DEFAULT 'main_image',
                    name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expert_annotations (
                    annotation_id TEXT PRIMARY KEY,
                    spec_id TEXT NOT NULL DEFAULT '',
                    field_name TEXT NOT NULL DEFAULT '',
                    annotation_type TEXT NOT NULL DEFAULT 'insight',
                    annotator TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.commit()

    # ── 通用 CRUD ──────────────────────────────────────────────

    def _upsert(
        self, table: str, pk_col: str, pk_val: str,
        index_cols: dict[str, Any], payload: dict,
    ) -> None:
        cols = [pk_col] + list(index_cols.keys()) + ["payload_json"]
        placeholders = ", ".join(["?"] * len(cols))
        updates = ", ".join(f"{c} = excluded.{c}" for c in list(index_cols.keys()) + ["payload_json"])
        values = [pk_val] + list(index_cols.values()) + [json.dumps(payload, ensure_ascii=False, default=str)]
        sql = f"""
            INSERT INTO {table} ({', '.join(cols)})
            VALUES ({placeholders})
            ON CONFLICT({pk_col}) DO UPDATE SET {updates}
        """
        with self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()

    def _get_one(self, table: str, pk_col: str, pk_val: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT payload_json FROM {table} WHERE {pk_col} = ?",
                (pk_val,),
            ).fetchone()
        if row:
            return json.loads(row["payload_json"])
        return None

    def _list_all(
        self, table: str, *,
        where: dict[str, Any] | None = None,
        order_by: str = "rowid DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params: list[Any] = []
        for col, val in (where or {}).items():
            conditions.append(f"{col} = ?")
            params.append(val)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT payload_json FROM {table} WHERE {where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?"
        params += [limit, offset]
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def _count(self, table: str, where: dict[str, Any] | None = None) -> int:
        conditions = []
        params: list[Any] = []
        for col, val in (where or {}).items():
            conditions.append(f"{col} = ?")
            params.append(val)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table} WHERE {where_clause}", params).fetchone()
        return row["cnt"] if row else 0

    # ── TrendOpportunity ──────────────────────────────────────

    def save_trend_opportunity(self, opp: dict) -> None:
        self._upsert("trend_opportunities", "opportunity_id", opp["opportunity_id"], {
            "title": opp.get("title", ""),
            "source_platform": opp.get("source_platform", ""),
            "source_type": opp.get("source_type", "trend"),
            "freshness_score": opp.get("freshness_score", 0.5),
            "actionability_score": opp.get("actionability_score", 0.5),
            "status": opp.get("status", "new"),
            "workspace_id": opp.get("workspace_id", ""),
            "brand_id": opp.get("brand_id", ""),
        }, opp)

    def get_trend_opportunity(self, opp_id: str) -> dict | None:
        return self._get_one("trend_opportunities", "opportunity_id", opp_id)

    def list_trend_opportunities(self, **kwargs: Any) -> list[dict]:
        return self._list_all("trend_opportunities", **kwargs)

    # ── SellingPointSpec ──────────────────────────────────────

    def save_selling_point_spec(self, spec: dict) -> None:
        self._upsert("selling_point_specs", "spec_id", spec["spec_id"], {
            "core_claim": spec.get("core_claim", ""),
            "confidence_score": spec.get("confidence_score", 0.5),
            "status": spec.get("status", "draft"),
            "workspace_id": spec.get("workspace_id", ""),
            "brand_id": spec.get("brand_id", ""),
        }, spec)

    def get_selling_point_spec(self, spec_id: str) -> dict | None:
        return self._get_one("selling_point_specs", "spec_id", spec_id)

    def list_selling_point_specs(self, **kwargs: Any) -> list[dict]:
        return self._list_all("selling_point_specs", **kwargs)

    # ── MainImageVariant ──────────────────────────────────────

    def save_main_image_variant(self, v: dict) -> None:
        self._upsert("main_image_variants", "variant_id", v["variant_id"], {
            "source_selling_point_id": v.get("source_selling_point_id", ""),
            "platform": v.get("platform", ""),
            "sku_id": v.get("sku_id", ""),
            "status": v.get("status", "draft"),
            "workspace_id": v.get("workspace_id", ""),
            "brand_id": v.get("brand_id", ""),
            "generated_image_url": v.get("generated_image_url", ""),
        }, v)

    def get_main_image_variant(self, variant_id: str) -> dict | None:
        return self._get_one("main_image_variants", "variant_id", variant_id)

    def list_main_image_variants(self, **kwargs: Any) -> list[dict]:
        return self._list_all("main_image_variants", **kwargs)

    # ── First3sVariant ────────────────────────────────────────

    def save_first3s_variant(self, v: dict) -> None:
        self._upsert("first3s_variants", "variant_id", v["variant_id"], {
            "source_selling_point_id": v.get("source_selling_point_id", ""),
            "platform": v.get("platform", ""),
            "key_hook_type": v.get("key_hook_type", ""),
            "status": v.get("status", "draft"),
            "workspace_id": v.get("workspace_id", ""),
            "brand_id": v.get("brand_id", ""),
        }, v)

    def get_first3s_variant(self, variant_id: str) -> dict | None:
        return self._get_one("first3s_variants", "variant_id", variant_id)

    def list_first3s_variants(self, **kwargs: Any) -> list[dict]:
        return self._list_all("first3s_variants", **kwargs)

    # ── TestTask ──────────────────────────────────────────────

    def save_test_task(self, t: dict) -> None:
        self._upsert("test_tasks", "task_id", t["task_id"], {
            "source_variant_id": t.get("source_variant_id", ""),
            "variant_type": t.get("variant_type", "main_image"),
            "platform": t.get("platform", ""),
            "store_id": t.get("store_id", ""),
            "sku_id": t.get("sku_id", ""),
            "status": t.get("status", "draft"),
            "workspace_id": t.get("workspace_id", ""),
            "brand_id": t.get("brand_id", ""),
            "owner": t.get("owner", ""),
        }, t)

    def get_test_task(self, task_id: str) -> dict | None:
        return self._get_one("test_tasks", "task_id", task_id)

    def list_test_tasks(self, **kwargs: Any) -> list[dict]:
        return self._list_all("test_tasks", **kwargs)

    # ── ResultSnapshot ────────────────────────────────────────

    def save_result_snapshot(self, s: dict) -> None:
        self._upsert("result_snapshots", "snapshot_id", s["snapshot_id"], {
            "task_id": s.get("task_id", ""),
            "date": s.get("date", ""),
            "overall_result": s.get("overall_result", "pending"),
            "ctr": s.get("ctr"),
            "refund_rate": s.get("refund_rate"),
        }, s)

    def list_result_snapshots(self, task_id: str) -> list[dict]:
        return self._list_all("result_snapshots", where={"task_id": task_id})

    # ── AmplificationPlan ─────────────────────────────────────

    def save_amplification_plan(self, p: dict) -> None:
        self._upsert("amplification_plans", "plan_id", p["plan_id"], {
            "based_on_task_id": p.get("based_on_task_id", ""),
            "amplification_type": p.get("amplification_type", "original_link_scale"),
            "priority": p.get("priority", "medium"),
            "status": p.get("status", "proposed"),
            "workspace_id": p.get("workspace_id", ""),
        }, p)

    def get_amplification_plan(self, plan_id: str) -> dict | None:
        return self._get_one("amplification_plans", "plan_id", plan_id)

    # ── AssetPerformanceCard ──────────────────────────────────

    def save_asset_performance_card(self, a: dict) -> None:
        self._upsert("asset_performance_cards", "asset_id", a["asset_id"], {
            "asset_type": a.get("asset_type", "high_performer"),
            "source_platform": a.get("source_platform", ""),
            "status": a.get("status", "active"),
            "workspace_id": a.get("workspace_id", ""),
            "brand_id": a.get("brand_id", ""),
        }, a)

    def get_asset_performance_card(self, asset_id: str) -> dict | None:
        return self._get_one("asset_performance_cards", "asset_id", asset_id)

    def list_asset_performance_cards(self, **kwargs: Any) -> list[dict]:
        return self._list_all("asset_performance_cards", **kwargs)

    # ── PatternTemplate ───────────────────────────────────────

    def save_pattern_template(self, t: dict) -> None:
        self._upsert("pattern_templates", "template_id", t["template_id"], {
            "template_type": t.get("template_type", "main_image"),
            "name": t.get("name", ""),
            "status": t.get("status", "draft"),
            "workspace_id": t.get("workspace_id", ""),
            "brand_id": t.get("brand_id", ""),
        }, t)

    def get_pattern_template(self, template_id: str) -> dict | None:
        return self._get_one("pattern_templates", "template_id", template_id)

    def list_pattern_templates(self, **kwargs: Any) -> list[dict]:
        return self._list_all("pattern_templates", **kwargs)

    # ── ExpertAnnotation ──────────────────────────────────────

    def save_expert_annotation(self, ann: dict) -> None:
        self._upsert("expert_annotations", "annotation_id", ann["annotation_id"], {
            "spec_id": ann.get("spec_id", ""),
            "field_name": ann.get("field_name", ""),
            "annotation_type": ann.get("annotation_type", "insight"),
            "annotator": ann.get("annotator", ""),
            "brand_id": ann.get("brand_id", ""),
        }, ann)

    def get_expert_annotation(self, annotation_id: str) -> dict | None:
        return self._get_one("expert_annotations", "annotation_id", annotation_id)

    def list_expert_annotations(self, **kwargs: Any) -> list[dict]:
        return self._list_all("expert_annotations", **kwargs)
