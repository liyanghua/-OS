from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from apps.intel_hub.schemas import (
    DemandSpecAsset,
    EvidenceRef,
    InsightCard,
    OpportunityCard,
    ReviewDecisionSource,
    ReviewStatus,
    ReviewUpdateRequest,
    RiskCard,
    Signal,
    VisualPatternAsset,
    Watchlist,
)


MODEL_BY_TABLE = {
    "signals": Signal,
    "evidence_refs": EvidenceRef,
    "opportunity_cards": OpportunityCard,
    "risk_cards": RiskCard,
    "insight_cards": InsightCard,
    "visual_pattern_assets": VisualPatternAsset,
    "demand_spec_assets": DemandSpecAsset,
    "watchlists": Watchlist,
}
CARD_TABLES = {"opportunity_cards", "risk_cards", "insight_cards", "visual_pattern_assets", "demand_spec_assets"}
REVIEW_FIELDS = ("review_status", "review_notes", "reviewer", "reviewed_at", "review_decision_source", "feedback_tags")

TModel = TypeVar("TModel", bound=BaseModel)


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            for table_name in MODEL_BY_TABLE:
                connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        entity_refs TEXT NOT NULL,
                        topic_tags TEXT NOT NULL,
                        platform_refs TEXT NOT NULL,
                        source_refs TEXT NOT NULL,
                        review_status TEXT NOT NULL,
                        reviewer TEXT,
                        reviewed_at TEXT,
                        dedupe_key TEXT,
                        confidence REAL NOT NULL,
                        sort_timestamp TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                self._ensure_columns(connection, table_name)

    def save_signals(self, signals: list[Signal]) -> None:
        self._save_models("signals", signals, timestamp_key="published_at")

    def save_evidence_refs(self, evidence_refs: list[EvidenceRef]) -> None:
        self._save_models("evidence_refs", evidence_refs, timestamp_key="published_at")

    def save_opportunity_cards(self, cards: list[OpportunityCard]) -> None:
        self._save_models("opportunity_cards", cards, timestamp_key="compiled_at")

    def save_risk_cards(self, cards: list[RiskCard]) -> None:
        self._save_models("risk_cards", cards, timestamp_key="compiled_at")

    def save_insight_cards(self, cards: list[InsightCard]) -> None:
        self._save_models("insight_cards", cards, timestamp_key="compiled_at")

    def save_visual_pattern_assets(self, assets: list[VisualPatternAsset]) -> None:
        self._save_models("visual_pattern_assets", assets, timestamp_key="compiled_at")

    def save_demand_spec_assets(self, assets: list[DemandSpecAsset]) -> None:
        self._save_models("demand_spec_assets", assets, timestamp_key="compiled_at")

    def save_watchlists(self, watchlists: list[Watchlist]) -> None:
        self._save_models("watchlists", watchlists, timestamp_key="created_at")

    def list_models(
        self,
        table_name: str,
        *,
        page: int = 1,
        page_size: int = 20,
        entity: str | None = None,
        topic: str | None = None,
        platform: str | None = None,
        review_status: str | None = None,
        reviewer: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        filters = []
        params: list[Any] = []
        if entity:
            filters.append("entity_refs LIKE ?")
            params.append(f'%"{entity}"%')
        if topic:
            filters.append("topic_tags LIKE ?")
            params.append(f'%"{topic}"%')
        if platform:
            filters.append("platform_refs LIKE ?")
            params.append(f'%"{platform}"%')
        effective_review_status = review_status or status
        if effective_review_status:
            filters.append("review_status = ?")
            params.append(effective_review_status)
        if reviewer:
            filters.append("reviewer = ?")
            params.append(reviewer)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        offset = (max(page, 1) - 1) * max(page_size, 1)

        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM {table_name} {where_clause}",
                params,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM {table_name}
                {where_clause}
                ORDER BY sort_timestamp DESC, title ASC
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, offset],
            ).fetchall()

        model_cls = MODEL_BY_TABLE[table_name]
        items = [model_cls.model_validate_json(row["payload_json"]).model_dump(mode="json") for row in rows]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def update_card_review(self, table_name: str, card_id: str, review: ReviewUpdateRequest) -> OpportunityCard | RiskCard:
        if table_name not in CARD_TABLES:
            raise ValueError(f"Review updates are only supported for card tables, got {table_name}")

        with self._connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {table_name} WHERE id = ?",
                (card_id,),
            ).fetchone()
            if row is None:
                raise KeyError(card_id)

            model_cls = MODEL_BY_TABLE[table_name]
            card = model_cls.model_validate_json(row["payload_json"])
            reviewed_at = datetime.now(UTC).isoformat()
            updated_card = card.model_copy(
                update={
                    "review_status": review.review_status,
                    "review_notes": review.review_notes,
                    "reviewer": review.reviewer,
                    "reviewed_at": reviewed_at,
                    "review_decision_source": ReviewDecisionSource.MANUAL,
                    "feedback_tags": review.feedback_tags,
                }
            )
            self._save_models(table_name, [updated_card], timestamp_key="compiled_at", connection=connection)
            return updated_card

    def _save_models(
        self,
        table_name: str,
        models: list[TModel],
        *,
        timestamp_key: str,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        should_close_connection = connection is None
        connection = connection or self._connect()
        try:
            for model in models:
                model = self._merge_review_fields(connection, table_name, model)
                timestamps = getattr(model, "timestamps", {})
                sort_timestamp = timestamps.get(timestamp_key) or next(iter(timestamps.values()), "")
                connection.execute(
                    f"""
                    INSERT OR REPLACE INTO {table_name} (
                        id,
                        title,
                        summary,
                        entity_refs,
                        topic_tags,
                        platform_refs,
                        source_refs,
                        review_status,
                        reviewer,
                        reviewed_at,
                        dedupe_key,
                        confidence,
                        sort_timestamp,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        getattr(model, "id"),
                        getattr(model, "title"),
                        getattr(model, "summary", ""),
                        json.dumps(getattr(model, "entity_refs", []), ensure_ascii=False),
                        json.dumps(getattr(model, "topic_tags", []), ensure_ascii=False),
                        json.dumps(getattr(model, "platform_refs", []), ensure_ascii=False),
                        json.dumps(getattr(model, "source_refs", []), ensure_ascii=False),
                        str(getattr(model, "review_status").value if hasattr(getattr(model, "review_status"), "value") else getattr(model, "review_status")),
                        getattr(model, "reviewer", None),
                        getattr(model, "reviewed_at", None),
                        getattr(model, "dedupe_key", ""),
                        float(getattr(model, "confidence")),
                        sort_timestamp,
                        model.model_dump_json(),
                    ),
                )
        finally:
            if should_close_connection:
                connection.commit()
                connection.close()

    def _ensure_columns(self, connection: sqlite3.Connection, table_name: str) -> None:
        existing_columns = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_type in {
            "reviewer": "TEXT",
            "reviewed_at": "TEXT",
            "dedupe_key": "TEXT",
            "platform_refs": "TEXT NOT NULL DEFAULT '[]'",
        }.items():
            if column_name not in existing_columns:
                connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def _merge_review_fields(self, connection: sqlite3.Connection, table_name: str, model: TModel) -> TModel:
        if table_name not in CARD_TABLES:
            return model
        if getattr(model, "reviewer", None) or getattr(model, "review_notes", ""):
            return model
        current_review_status = getattr(model, "review_status", ReviewStatus.PENDING)
        if str(current_review_status) not in {ReviewStatus.PENDING.value, ReviewStatus.PENDING.name}:
            return model

        existing_row = None
        dedupe_key = getattr(model, "dedupe_key", "")
        if dedupe_key:
            existing_row = connection.execute(
                f"SELECT payload_json FROM {table_name} WHERE dedupe_key = ? LIMIT 1",
                (dedupe_key,),
            ).fetchone()
        if existing_row is None:
            existing_row = connection.execute(
                f"SELECT payload_json FROM {table_name} WHERE id = ?",
                (getattr(model, "id"),),
            ).fetchone()
        if existing_row is None:
            return model

        existing_model = MODEL_BY_TABLE[table_name].model_validate_json(existing_row["payload_json"])
        if existing_model.review_status == ReviewStatus.PENDING and not existing_model.review_notes and not existing_model.reviewer:
            return model

        return model.model_copy(
            update={
                field_name: getattr(existing_model, field_name)
                for field_name in REVIEW_FIELDS
            }
        )
