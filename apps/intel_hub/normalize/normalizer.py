from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from apps.intel_hub.schemas.enums import ReviewStatus
from apps.intel_hub.schemas.evidence_ref import EvidenceRef
from apps.intel_hub.schemas.signal import Signal


def normalize_raw_signals(raw_records: list[dict[str, Any]]) -> tuple[list[Signal], list[EvidenceRef]]:
    signals: list[Signal] = []
    evidence_refs: list[EvidenceRef] = []
    seen_keys: set[str] = set()
    captured_at = datetime.now(UTC).isoformat()

    for raw in raw_records:
        dedupe_key = _build_dedupe_key(raw)
        if not dedupe_key or dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        published_at = _normalize_datetime(raw.get("published_at")) or captured_at
        confidence = _derive_confidence(raw.get("metrics", {}))
        signal_id = _stable_id("signal", dedupe_key)
        evidence_id = _stable_id("evidence", dedupe_key)
        source_refs = [raw["source_url"]] if raw.get("source_url") else []
        topic_tags = [str(tag).strip() for tag in raw.get("tags", []) if str(tag).strip()]

        evidence = EvidenceRef(
            id=evidence_id,
            title=raw.get("title") or "Untitled evidence",
            summary=raw.get("summary") or "",
            source_name=raw.get("source_name"),
            source_url=raw.get("source_url"),
            source_refs=source_refs,
            topic_tags=topic_tags,
            timestamps={
                "published_at": published_at,
                "captured_at": _normalize_datetime(raw.get("captured_at")) or captured_at,
            },
            confidence=confidence,
            evidence_refs=[evidence_id],
            review_status=ReviewStatus.PENDING,
            raw_text=raw.get("raw_text") or "",
            author=raw.get("author"),
            account=raw.get("account"),
            watchlist_hits=raw.get("watchlist_hits", []),
            raw_source_type=raw.get("raw_source_type"),
            metrics=raw.get("metrics", {}),
            platform=raw.get("platform"),
            keyword=raw.get("keyword"),
            rank=raw.get("rank"),
            raw_payload=raw.get("raw_payload", {}),
        )
        evidence_refs.append(evidence)

        business_signals = raw.get("_business_signals") or None
        if business_signals is not None and not isinstance(business_signals, dict):
            business_signals = None

        signals.append(
            Signal(
                id=signal_id,
                title=raw.get("title") or "Untitled signal",
                summary=raw.get("summary") or "",
                source_refs=source_refs,
                topic_tags=topic_tags,
                platform_refs=[raw.get("platform")] if raw.get("platform") else [],
                timestamps={
                    "published_at": published_at,
                    "captured_at": _normalize_datetime(raw.get("captured_at")) or captured_at,
                },
                confidence=confidence,
                evidence_refs=[evidence_id],
                review_status=ReviewStatus.PENDING,
                raw_text=raw.get("raw_text") or "",
                source_name=raw.get("source_name"),
                source_url=raw.get("source_url"),
                author=raw.get("author"),
                account=raw.get("account"),
                watchlist_hits=raw.get("watchlist_hits", []),
                raw_source_type=raw.get("raw_source_type"),
                metrics=raw.get("metrics", {}),
                keyword=raw.get("keyword"),
                rank=raw.get("rank"),
                raw_payload=raw.get("raw_payload", {}),
                lens_id=raw.get("lens_id"),
                business_signals=business_signals,
            )
        )

    return signals, evidence_refs


def _build_dedupe_key(raw: dict[str, Any]) -> str:
    return "|".join(
        [
            str(raw.get("source_url") or "").strip(),
            str(raw.get("title") or "").strip(),
            str(raw.get("published_at") or "").strip(),
        ]
    )


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _normalize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt).replace(tzinfo=UTC)
                return parsed.isoformat()
            except ValueError:
                continue
    return None


def _derive_confidence(metrics: dict[str, Any]) -> float:
    trending_score = metrics.get("trending_score")
    if isinstance(trending_score, (int, float)):
        return round(max(0.3, min(1.0, float(trending_score) / 100)), 3)

    comment_count = metrics.get("comment_count")
    if isinstance(comment_count, (int, float)) and comment_count > 0:
        avg_likes = float(metrics.get("avg_likes", 0))
        base = min(1.0, float(comment_count) / 50.0) * 0.6
        engage = min(1.0, avg_likes / 20.0) * 0.4
        return round(max(0.35, min(1.0, base + engage)), 3)

    engagement = metrics.get("engagement")
    if isinstance(engagement, (int, float)):
        return round(max(0.35, min(1.0, float(engagement) / 2000)), 3)
    return 0.5
