"""VisualStrategyStore — 视觉策略包/候选/Brief/Prompt/Feedback 存储。

复用 data/growth_lab.sqlite 数据库（与 GrowthLabStore 同库不同表），
覆盖：
- visual_strategy_packs
- strategy_candidates
- creative_briefs
- prompt_specs
- feedback_records

遵循仓库统一模式：可查询索引列 + payload_json 全量。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "growth_lab.sqlite"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class VisualStrategyStore:
    """视觉策略编译器产出对象的存储。"""

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
                CREATE TABLE IF NOT EXISTS visual_strategy_packs (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL DEFAULT '',
                    scene TEXT NOT NULL DEFAULT '',
                    rule_pack_id TEXT NOT NULL DEFAULT '',
                    context_spec_id TEXT NOT NULL DEFAULT '',
                    opportunity_card_id TEXT NOT NULL DEFAULT '',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    brand_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'compiled',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_candidates (
                    id TEXT PRIMARY KEY,
                    visual_strategy_pack_id TEXT NOT NULL DEFAULT '',
                    archetype TEXT NOT NULL DEFAULT '',
                    score_total REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'generated',
                    creative_brief_id TEXT NOT NULL DEFAULT '',
                    prompt_spec_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS creative_briefs (
                    id TEXT PRIMARY KEY,
                    strategy_candidate_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompt_specs (
                    id TEXT PRIMARY KEY,
                    creative_brief_id TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT 'comfyui',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS visual_feedback_records (
                    id TEXT PRIMARY KEY,
                    image_variant_id TEXT NOT NULL DEFAULT '',
                    strategy_candidate_id TEXT NOT NULL DEFAULT '',
                    decision TEXT NOT NULL DEFAULT 'enter_test_pool',
                    expert_overall REAL NOT NULL DEFAULT 0.0,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vsp_oc ON visual_strategy_packs(opportunity_card_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vsp_cat ON visual_strategy_packs(category)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sc_pack ON strategy_candidates(visual_strategy_pack_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_sc ON creative_briefs(strategy_candidate_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ps_cb ON prompt_specs(creative_brief_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fb_sc ON visual_feedback_records(strategy_candidate_id)",
            )
            conn.commit()

    # ── VisualStrategyPack ─────────────────────────────────────

    def save_visual_strategy_pack(self, pack: dict) -> None:
        now = _now_iso()
        source = pack.get("source") or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO visual_strategy_packs
                  (id, category, scene, rule_pack_id, context_spec_id, opportunity_card_id,
                   workspace_id, brand_id, status, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  category=excluded.category,
                  scene=excluded.scene,
                  rule_pack_id=excluded.rule_pack_id,
                  context_spec_id=excluded.context_spec_id,
                  opportunity_card_id=excluded.opportunity_card_id,
                  workspace_id=excluded.workspace_id,
                  brand_id=excluded.brand_id,
                  status=excluded.status,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    pack["id"],
                    pack.get("category", ""),
                    pack.get("scene", ""),
                    pack.get("rule_pack_id", ""),
                    pack.get("context_spec_id", ""),
                    source.get("opportunity_card_id", ""),
                    pack.get("workspace_id", ""),
                    pack.get("brand_id", ""),
                    pack.get("status", "compiled"),
                    json.dumps(pack, ensure_ascii=False, default=str),
                    pack.get("created_at", now),
                    now,
                ),
            )
            conn.commit()

    def get_visual_strategy_pack(self, pack_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM visual_strategy_packs WHERE id = ?",
                (pack_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_visual_strategy_packs(
        self,
        *,
        opportunity_card_id: str | None = None,
        category: str | None = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[Any] = []
        if opportunity_card_id:
            clauses.append("opportunity_card_id = ?")
            params.append(opportunity_card_id)
        if category:
            clauses.append("category = ?")
            params.append(category)
        sql = "SELECT payload_json FROM visual_strategy_packs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY rowid DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    # ── StrategyCandidate ──────────────────────────────────────

    def save_strategy_candidate(self, cand: dict) -> None:
        now = _now_iso()
        score = cand.get("score") or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_candidates
                  (id, visual_strategy_pack_id, archetype, score_total, status,
                   creative_brief_id, prompt_spec_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  visual_strategy_pack_id=excluded.visual_strategy_pack_id,
                  archetype=excluded.archetype,
                  score_total=excluded.score_total,
                  status=excluded.status,
                  creative_brief_id=excluded.creative_brief_id,
                  prompt_spec_id=excluded.prompt_spec_id,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    cand["id"],
                    cand.get("visual_strategy_pack_id", ""),
                    cand.get("archetype", ""),
                    float(score.get("total", 0.0) or 0.0),
                    cand.get("status", "generated"),
                    cand.get("creative_brief_id", ""),
                    cand.get("prompt_spec_id", ""),
                    json.dumps(cand, ensure_ascii=False, default=str),
                    cand.get("created_at", now),
                    now,
                ),
            )
            conn.commit()

    def get_strategy_candidate(self, candidate_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM strategy_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_strategy_candidates(self, visual_strategy_pack_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM strategy_candidates WHERE visual_strategy_pack_id = ? ORDER BY score_total DESC, rowid ASC",
                (visual_strategy_pack_id,),
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    # ── CreativeBrief ──────────────────────────────────────────

    def save_creative_brief(self, brief: dict) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO creative_briefs
                  (id, strategy_candidate_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  strategy_candidate_id=excluded.strategy_candidate_id,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    brief["id"],
                    brief.get("strategy_candidate_id", ""),
                    json.dumps(brief, ensure_ascii=False, default=str),
                    brief.get("created_at", now),
                    now,
                ),
            )
            conn.commit()

    def get_creative_brief(self, brief_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM creative_briefs WHERE id = ?",
                (brief_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    # ── PromptSpec ─────────────────────────────────────────────

    def save_prompt_spec(self, spec: dict) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO prompt_specs
                  (id, creative_brief_id, provider, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  creative_brief_id=excluded.creative_brief_id,
                  provider=excluded.provider,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (
                    spec["id"],
                    spec.get("creative_brief_id", ""),
                    spec.get("provider", "comfyui"),
                    json.dumps(spec, ensure_ascii=False, default=str),
                    spec.get("created_at", now),
                    now,
                ),
            )
            conn.commit()

    def get_prompt_spec(self, prompt_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM prompt_specs WHERE id = ?",
                (prompt_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    # ── FeedbackRecord ─────────────────────────────────────────

    def save_feedback_record(self, record: dict) -> None:
        expert = record.get("expert_score") or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO visual_feedback_records
                  (id, image_variant_id, strategy_candidate_id, decision, expert_overall,
                   payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  image_variant_id=excluded.image_variant_id,
                  strategy_candidate_id=excluded.strategy_candidate_id,
                  decision=excluded.decision,
                  expert_overall=excluded.expert_overall,
                  payload_json=excluded.payload_json
                """,
                (
                    record["id"],
                    record.get("image_variant_id", ""),
                    record.get("strategy_candidate_id", ""),
                    record.get("decision", "enter_test_pool"),
                    float(expert.get("overall", 0.0) or 0.0),
                    json.dumps(record, ensure_ascii=False, default=str),
                    record.get("created_at", _now_iso()),
                ),
            )
            conn.commit()

    def get_feedback_record(self, record_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM visual_feedback_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def list_feedback_records(self, strategy_candidate_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM visual_feedback_records WHERE strategy_candidate_id = ? ORDER BY rowid DESC",
                (strategy_candidate_id,),
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]
