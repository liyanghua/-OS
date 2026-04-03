"""轻量 SQLite 存储 —— XHS 机会卡检视反馈与聚合数据。

独立于旧 Repository，专门管理 XHS 三维结构化流水线的机会卡 review 闭环。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
from apps.intel_hub.schemas.opportunity_review import OpportunityReview


class XHSReviewStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS xhs_opportunity_cards (
                    opportunity_id TEXT PRIMARY KEY,
                    opportunity_type TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    review_count INTEGER NOT NULL DEFAULT 0,
                    manual_quality_score_avg REAL,
                    actionable_ratio REAL,
                    evidence_sufficient_ratio REAL,
                    composite_review_score REAL,
                    qualified_opportunity INTEGER NOT NULL DEFAULT 0,
                    opportunity_status TEXT NOT NULL DEFAULT 'pending_review',
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS xhs_reviews (
                    review_id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    manual_quality_score INTEGER NOT NULL,
                    is_actionable INTEGER NOT NULL,
                    evidence_sufficient INTEGER NOT NULL,
                    review_notes TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (opportunity_id) REFERENCES xhs_opportunity_cards(opportunity_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_opportunity
                ON xhs_reviews(opportunity_id)
            """)

    # ── Cards ──

    def sync_cards_from_json(self, json_path: str | Path) -> int:
        """从 pipeline JSON 输出同步卡片。已存在的卡片保留聚合数据，只更新 payload。"""
        path = Path(json_path)
        if not path.exists():
            return 0
        cards_data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        with self._connect() as conn:
            for card_dict in cards_data:
                card = XHSOpportunityCard.model_validate(card_dict)
                existing = conn.execute(
                    "SELECT review_count, manual_quality_score_avg, actionable_ratio, "
                    "evidence_sufficient_ratio, composite_review_score, qualified_opportunity, "
                    "opportunity_status FROM xhs_opportunity_cards WHERE opportunity_id = ?",
                    (card.opportunity_id,),
                ).fetchone()
                if existing:
                    card = card.model_copy(update={
                        "review_count": existing["review_count"],
                        "manual_quality_score_avg": existing["manual_quality_score_avg"],
                        "actionable_ratio": existing["actionable_ratio"],
                        "evidence_sufficient_ratio": existing["evidence_sufficient_ratio"],
                        "composite_review_score": existing["composite_review_score"],
                        "qualified_opportunity": bool(existing["qualified_opportunity"]),
                        "opportunity_status": existing["opportunity_status"],
                    })
                conn.execute(
                    """INSERT OR REPLACE INTO xhs_opportunity_cards
                    (opportunity_id, opportunity_type, title, confidence,
                     review_count, manual_quality_score_avg, actionable_ratio,
                     evidence_sufficient_ratio, composite_review_score,
                     qualified_opportunity, opportunity_status, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        card.opportunity_id,
                        card.opportunity_type,
                        card.title,
                        card.confidence,
                        card.review_count,
                        card.manual_quality_score_avg,
                        card.actionable_ratio,
                        card.evidence_sufficient_ratio,
                        card.composite_review_score,
                        int(card.qualified_opportunity),
                        card.opportunity_status,
                        card.model_dump_json(),
                    ),
                )
                count += 1
        return count

    def get_card(self, opportunity_id: str) -> XHSOpportunityCard | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM xhs_opportunity_cards WHERE opportunity_id = ?",
                (opportunity_id,),
            ).fetchone()
        if row is None:
            return None
        return XHSOpportunityCard.model_validate_json(row["payload_json"])

    def list_cards(
        self,
        *,
        opportunity_type: str | None = None,
        opportunity_status: str | None = None,
        qualified: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        filters: list[str] = []
        params: list[Any] = []
        if opportunity_type:
            filters.append("opportunity_type = ?")
            params.append(opportunity_type)
        if opportunity_status:
            filters.append("opportunity_status = ?")
            params.append(opportunity_status)
        if qualified is not None:
            filters.append("qualified_opportunity = ?")
            params.append(int(qualified))

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        offset = (max(page, 1) - 1) * max(page_size, 1)

        with self._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM xhs_opportunity_cards {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT payload_json FROM xhs_opportunity_cards {where}
                ORDER BY confidence DESC, title ASC
                LIMIT ? OFFSET ?""",
                [*params, page_size, offset],
            ).fetchall()

        cards = [XHSOpportunityCard.model_validate_json(r["payload_json"]) for r in rows]
        return {"items": cards, "total": total, "page": page, "page_size": page_size}

    def list_promoted_cards(self) -> list[XHSOpportunityCard]:
        return self.list_cards(opportunity_status="promoted", page_size=1000)["items"]

    def update_card_review_stats(self, opportunity_id: str, stats: dict[str, Any]) -> XHSOpportunityCard | None:
        card = self.get_card(opportunity_id)
        if card is None:
            return None
        updated = card.model_copy(update=stats)
        with self._connect() as conn:
            conn.execute(
                """UPDATE xhs_opportunity_cards SET
                    review_count = ?, manual_quality_score_avg = ?, actionable_ratio = ?,
                    evidence_sufficient_ratio = ?, composite_review_score = ?,
                    qualified_opportunity = ?, opportunity_status = ?, payload_json = ?
                WHERE opportunity_id = ?""",
                (
                    updated.review_count,
                    updated.manual_quality_score_avg,
                    updated.actionable_ratio,
                    updated.evidence_sufficient_ratio,
                    updated.composite_review_score,
                    int(updated.qualified_opportunity),
                    updated.opportunity_status,
                    updated.model_dump_json(),
                    opportunity_id,
                ),
            )
        return updated

    # ── Reviews ──

    def save_review(self, review: OpportunityReview) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO xhs_reviews
                (review_id, opportunity_id, reviewer, reviewed_at,
                 manual_quality_score, is_actionable, evidence_sufficient,
                 review_notes, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.opportunity_id,
                    review.reviewer,
                    review.reviewed_at.isoformat(),
                    review.manual_quality_score,
                    int(review.is_actionable),
                    int(review.evidence_sufficient),
                    review.review_notes,
                    review.model_dump_json(),
                ),
            )

    def get_reviews(self, opportunity_id: str) -> list[OpportunityReview]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM xhs_reviews WHERE opportunity_id = ? ORDER BY reviewed_at DESC",
                (opportunity_id,),
            ).fetchall()
        return [OpportunityReview.model_validate_json(r["payload_json"]) for r in rows]

    # ── Stats ──

    def get_review_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM xhs_opportunity_cards").fetchone()[0]
            reviewed = conn.execute(
                "SELECT COUNT(*) FROM xhs_opportunity_cards WHERE review_count > 0"
            ).fetchone()[0]
            promoted = conn.execute(
                "SELECT COUNT(*) FROM xhs_opportunity_cards WHERE opportunity_status = 'promoted'"
            ).fetchone()[0]
            row = conn.execute(
                """SELECT
                    AVG(manual_quality_score_avg) as avg_quality,
                    AVG(actionable_ratio) as avg_actionable,
                    AVG(evidence_sufficient_ratio) as avg_evidence,
                    AVG(composite_review_score) as avg_composite
                FROM xhs_opportunity_cards WHERE review_count > 0"""
            ).fetchone()

        avg_q = row["avg_quality"] if row["avg_quality"] is not None else 0
        avg_a = row["avg_actionable"] if row["avg_actionable"] is not None else 0
        avg_e = row["avg_evidence"] if row["avg_evidence"] is not None else 0
        avg_c = row["avg_composite"] if row["avg_composite"] is not None else 0

        needs_opt = (
            avg_q < 6.5
            or avg_a < 0.5
            or avg_e < 0.6
            or avg_c < 0.65
        )

        return {
            "total_opportunities": total,
            "reviewed_opportunities": reviewed,
            "promoted_opportunities": promoted,
            "average_manual_quality_score": round(avg_q, 2),
            "average_actionable_ratio": round(avg_a, 3),
            "average_evidence_sufficient_ratio": round(avg_e, 3),
            "average_composite_review_score": round(avg_c, 3),
            "needs_optimization": needs_opt,
        }

    def card_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM xhs_opportunity_cards").fetchone()[0]

    def type_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT opportunity_type, COUNT(*) as cnt FROM xhs_opportunity_cards GROUP BY opportunity_type"
            ).fetchall()
        return {r["opportunity_type"]: r["cnt"] for r in rows}
