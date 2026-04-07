"""桥接层：从 intel_hub 存储读取 promoted 机会卡 + source note + review 数据。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.intel_hub.config_loader import resolve_repo_path
from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard
from apps.intel_hub.storage.xhs_review_store import XHSReviewStore


class IntelHubAdapter:
    """不依赖 API 层，直接读取 intel_hub 存储以获取上游数据。"""

    def __init__(
        self,
        review_store: XHSReviewStore | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if review_store is not None:
            self._store = review_store
        else:
            _db = Path(db_path) if db_path else resolve_repo_path("data/xhs_review.sqlite")
            self._store = XHSReviewStore(_db)
        self._details_cache: dict[str, dict[str, Any]] | None = None
        self._notes_cache: list[dict[str, Any]] | None = None

    def get_promoted_cards(self) -> list[XHSOpportunityCard]:
        return self._store.list_promoted_cards()

    def get_card(self, opportunity_id: str) -> XHSOpportunityCard | None:
        card = self._store.get_card(opportunity_id)
        if card is None:
            return None
        return card

    def get_review_summary(self, opportunity_id: str) -> dict[str, Any]:
        reviews = self._store.get_reviews(opportunity_id)
        if not reviews:
            return {"review_count": 0}
        scores = [r.manual_quality_score for r in reviews]
        return {
            "review_count": len(reviews),
            "avg_quality_score": round(sum(scores) / len(scores), 2),
            "actionable_count": sum(1 for r in reviews if r.is_actionable),
            "evidence_sufficient_count": sum(1 for r in reviews if r.evidence_sufficient),
            "latest_notes": [r.review_notes for r in reviews[:3] if r.review_notes],
        }

    def get_source_notes(self, note_ids: list[str]) -> list[dict[str, Any]]:
        """从 pipeline_details 中按 note_id 提取原始笔记上下文。"""
        idx = self._load_details_index()
        return [idx[nid] for nid in note_ids if nid in idx]

    def get_raw_notes(self) -> list[dict[str, Any]]:
        """加载全量小红书原始笔记记录。"""
        if self._notes_cache is not None:
            return self._notes_cache
        from apps.intel_hub.config_loader import load_runtime_settings

        settings = load_runtime_settings()
        all_records: list[dict[str, Any]] = []
        for src in settings.mediacrawler_sources:
            if not src.get("enabled", True):
                continue
            out = resolve_repo_path(src.get("output_path", ""))
            if out.exists():
                all_records.extend(
                    load_mediacrawler_records(str(out), platform=src.get("platform", "xiaohongshu"))
                )
        self._notes_cache = all_records
        return all_records

    def _load_details_index(self) -> dict[str, dict[str, Any]]:
        if self._details_cache is not None:
            return self._details_cache
        details_path = resolve_repo_path("data/output/xhs_opportunities/pipeline_details.json")
        if not details_path.exists():
            self._details_cache = {}
            return self._details_cache
        try:
            details = json.loads(details_path.read_text(encoding="utf-8"))
        except Exception:
            self._details_cache = {}
            return self._details_cache
        idx: dict[str, dict[str, Any]] = {}
        for d in details:
            nid = d.get("note_id", "")
            if nid:
                idx[nid] = d
        self._details_cache = idx
        return idx
