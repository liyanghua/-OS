"""RuleStore — 视觉策略编译器规则生产线存储。

复用 data/content_plan.sqlite 数据库（与 ContentPlanStore 同库不同表），
覆盖 source_documents / rule_specs / rule_packs / context_specs / rule_weight_history。

遵循仓库统一模式：可查询索引列 + payload_json 全量。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "content_plan.sqlite"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RuleStore:
    """视觉策略编译器规则线存储。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_documents (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL DEFAULT '',
                    file_name TEXT NOT NULL DEFAULT '',
                    dimension TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL DEFAULT 'v1',
                    status TEXT NOT NULL DEFAULT 'uploaded',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rule_specs (
                    id TEXT PRIMARY KEY,
                    rule_pack_id TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    dimension TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT 'draft',
                    lifecycle_status TEXT NOT NULL DEFAULT 'candidate',
                    base_weight REAL NOT NULL DEFAULT 0.5,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rule_packs (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL DEFAULT 'v1',
                    status TEXT NOT NULL DEFAULT 'draft',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_specs (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    scene TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rule_weight_history (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL DEFAULT '',
                    feedback_record_id TEXT NOT NULL DEFAULT '',
                    old_weight REAL NOT NULL DEFAULT 0.0,
                    new_weight REAL NOT NULL DEFAULT 0.0,
                    delta REAL NOT NULL DEFAULT 0.0,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_specs_category ON rule_specs(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_specs_dim ON rule_specs(dimension)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_specs_review ON rule_specs(review_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_packs_category ON rule_packs(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_docs_category ON source_documents(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_weight_rule ON rule_weight_history(rule_id)")
            conn.commit()

    # ── SourceDocument ──────────────────────────────────────────

    def save_source_document(self, doc: dict) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_documents
                  (id, category, file_name, dimension, version, status, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  category=excluded.category,
                  file_name=excluded.file_name,
                  dimension=excluded.dimension,
                  version=excluded.version,
                  status=excluded.status,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    doc["id"],
                    doc.get("category", ""),
                    doc.get("file_name", ""),
                    doc.get("dimension", ""),
                    doc.get("version", "v1"),
                    doc.get("status", "uploaded"),
                    json.dumps(doc, ensure_ascii=False, default=str),
                    doc.get("created_at", now),
                    now,
                ),
            )
            conn.commit()

    def get_source_document(self, doc_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM source_documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_source_documents(self, *, category: str | None = None) -> list[dict]:
        sql = "SELECT payload_json FROM source_documents"
        params: list[Any] = []
        if category:
            sql += " WHERE category = ?"
            params.append(category)
        sql += " ORDER BY rowid ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    # ── RuleSpec ────────────────────────────────────────────────

    def save_rule_spec(self, rule: dict) -> None:
        now = _now_iso()
        evidence = rule.get("evidence") or {}
        scoring = rule.get("scoring") or {}
        review = rule.get("review") or {}
        lifecycle = rule.get("lifecycle") or {}
        category_scope = rule.get("category_scope") or []
        category = category_scope[0] if category_scope else ""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rule_specs
                  (id, rule_pack_id, category, dimension, review_status, lifecycle_status,
                   base_weight, confidence, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  rule_pack_id=excluded.rule_pack_id,
                  category=excluded.category,
                  dimension=excluded.dimension,
                  review_status=excluded.review_status,
                  lifecycle_status=excluded.lifecycle_status,
                  base_weight=excluded.base_weight,
                  confidence=excluded.confidence,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    rule["id"],
                    rule.get("rule_pack_id", ""),
                    category,
                    rule.get("dimension", ""),
                    review.get("status", "draft"),
                    lifecycle.get("status", "candidate"),
                    float(scoring.get("base_weight", 0.5) or 0.5),
                    float(evidence.get("confidence", 0.5) or 0.5),
                    json.dumps(rule, ensure_ascii=False, default=str),
                    rule.get("lifecycle", {}).get("created_at", now),
                    now,
                ),
            )
            conn.commit()

    def get_rule_spec(self, rule_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM rule_specs WHERE id = ?",
                (rule_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_rule_specs(
        self,
        *,
        category: str | None = None,
        dimension: str | None = None,
        review_status: str | None = None,
        rule_pack_id: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[Any] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if dimension:
            clauses.append("dimension = ?")
            params.append(dimension)
        if review_status:
            clauses.append("review_status = ?")
            params.append(review_status)
        if rule_pack_id:
            clauses.append("rule_pack_id = ?")
            params.append(rule_pack_id)
        sql = "SELECT payload_json FROM rule_specs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY rowid ASC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def count_rule_specs(self, *, category: str, review_status: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS cnt FROM rule_specs WHERE category = ?"
        params: list[Any] = [category]
        if review_status:
            sql += " AND review_status = ?"
            params.append(review_status)
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["cnt"]) if row else 0

    # ── RulePack ────────────────────────────────────────────────

    def save_rule_pack(self, pack: dict) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rule_packs
                  (id, category, name, version, status, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  category=excluded.category,
                  name=excluded.name,
                  version=excluded.version,
                  status=excluded.status,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    pack["id"],
                    pack.get("category", ""),
                    pack.get("name", ""),
                    pack.get("version", "v1"),
                    pack.get("status", "draft"),
                    json.dumps(pack, ensure_ascii=False, default=str),
                    pack.get("created_at", now),
                    now,
                ),
            )
            conn.commit()

    def get_rule_pack(self, rule_pack_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM rule_packs WHERE id = ?",
                (rule_pack_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_rule_packs(self, *, category: str | None = None) -> list[dict]:
        sql = "SELECT payload_json FROM rule_packs"
        params: list[Any] = []
        if category:
            sql += " WHERE category = ?"
            params.append(category)
        sql += " ORDER BY rowid DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def get_active_rule_pack(self, category: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json FROM rule_packs
                WHERE category = ? AND status = 'active'
                ORDER BY rowid DESC LIMIT 1
                """,
                (category,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    # ── ContextSpec ────────────────────────────────────────────

    def save_context_spec(self, spec: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO context_specs
                  (id, source_type, source_id, category, scene, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  source_type=excluded.source_type,
                  source_id=excluded.source_id,
                  category=excluded.category,
                  scene=excluded.scene,
                  payload_json=excluded.payload_json
                """,
                (
                    spec["id"],
                    spec.get("source_type", "manual"),
                    spec.get("source_id", ""),
                    spec.get("category", ""),
                    spec.get("scene", ""),
                    json.dumps(spec, ensure_ascii=False, default=str),
                    spec.get("created_at", _now_iso()),
                ),
            )
            conn.commit()

    def get_context_spec(self, spec_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM context_specs WHERE id = ?",
                (spec_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    # ── RuleWeightHistory ──────────────────────────────────────

    def save_rule_weight_history(self, record: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rule_weight_history
                  (id, rule_id, feedback_record_id, old_weight, new_weight, delta, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record.get("rule_id", ""),
                    record.get("feedback_record_id", ""),
                    float(record.get("old_weight", 0.0) or 0.0),
                    float(record.get("new_weight", 0.0) or 0.0),
                    float(record.get("delta", 0.0) or 0.0),
                    record.get("reason", ""),
                    record.get("created_at", _now_iso()),
                ),
            )
            conn.commit()

    def list_rule_weight_history(self, rule_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, rule_id, feedback_record_id, old_weight, new_weight, delta, reason, created_at
                FROM rule_weight_history
                WHERE rule_id = ?
                ORDER BY rowid DESC
                """,
                (rule_id,),
            ).fetchall()
        return [dict(row) for row in rows]
