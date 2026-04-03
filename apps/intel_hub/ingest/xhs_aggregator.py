"""小红书评论聚合器：将评论级 raw dict 按笔记聚合为笔记级信号。

同一 note_id 下的多条评论 → 一条高质量信号:
- 标题 = 笔记标题
- 正文 = 前 N 条高互动评论拼接
- metrics = 聚合互动数据
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


DEFAULT_AGGREGATION = {
    "max_comments_per_signal": 20,
    "min_comments_for_signal": 1,
    "top_comments_in_body": 5,
}


def aggregate_comments_to_signals(
    raw_records: list[dict[str, Any]],
    aggregation_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """将评论级 raw dict 按 note_id 聚合为笔记级信号。

    不带 ``_xhs_note_id`` 的记录直接透传（兼容非评论数据）。
    """
    cfg = {**DEFAULT_AGGREGATION, **(aggregation_config or {})}
    max_comments = int(cfg.get("max_comments_per_signal", 20))
    min_comments = int(cfg.get("min_comments_for_signal", 1))
    top_n = int(cfg.get("top_comments_in_body", 5))

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    passthrough: list[dict[str, Any]] = []

    for record in raw_records:
        note_id = record.get("_xhs_note_id")
        if note_id:
            groups[note_id].append(record)
        else:
            passthrough.append(record)

    signals: list[dict[str, Any]] = list(passthrough)
    for note_id, comments in groups.items():
        if len(comments) < min_comments:
            continue

        comments_sorted = sorted(
            comments,
            key=lambda r: int(r.get("_xhs_like_count") or 0),
            reverse=True,
        )
        top_comments = comments_sorted[:max_comments]
        display_comments = top_comments[:top_n]

        note_title = ""
        keyword = None
        source_url = None
        earliest_publish = None
        latest_capture = None
        first_record = comments[0]

        for c in comments:
            t = c.get("_xhs_note_title") or ""
            if t and not note_title:
                note_title = t
            if not keyword and c.get("keyword"):
                keyword = c["keyword"]
            if not source_url and c.get("source_url"):
                source_url = c["source_url"]
            pub = c.get("published_at")
            if pub and (earliest_publish is None or str(pub) < str(earliest_publish)):
                earliest_publish = pub
            cap = c.get("captured_at")
            if cap and (latest_capture is None or str(cap) > str(latest_capture)):
                latest_capture = cap

        total_likes = sum(int(c.get("_xhs_like_count") or 0) for c in top_comments)
        comment_count = len(top_comments)
        avg_likes = total_likes / comment_count if comment_count else 0

        body_parts = []
        for i, c in enumerate(display_comments, 1):
            likes = int(c.get("_xhs_like_count") or 0)
            text = str(c.get("raw_text") or "").strip()
            if text:
                body_parts.append(f"[{i}] {text}  (赞 {likes})")

        raw_text = "\n---\n".join(body_parts) if body_parts else ""
        if not note_title:
            note_title = raw_text[:80] if raw_text else "小红书笔记评论"

        title = f"[小红书] {note_title}"
        summary_line = f"{comment_count} 条评论 | 总赞 {total_likes} | 均赞 {avg_likes:.1f}"
        summary = f"{summary_line}\n{raw_text[:300]}" if raw_text else summary_line

        signals.append({
            "title": title,
            "summary": summary,
            "raw_text": raw_text,
            "source_url": source_url,
            "source_name": "小红书",
            "platform": "xhs",
            "published_at": earliest_publish,
            "captured_at": latest_capture,
            "author": first_record.get("author"),
            "metrics": {
                "engagement": total_likes,
                "comment_count": comment_count,
                "avg_likes": round(avg_likes, 2),
                "likes": total_likes,
            },
            "keyword": keyword,
            "watchlist_hits": [],
            "tags": ["小红书评论", "用户声音"],
            "raw_source_type": "xhs_aggregated",
            "raw_payload": {
                "note_id": note_id,
                "note_title": note_title,
                "comment_count": comment_count,
                "total_likes": total_likes,
                "top_comment_ids": [
                    c.get("raw_payload", {}).get("source_id") or c.get("raw_payload", {}).get("id")
                    for c in display_comments
                ],
            },
            "file_path": first_record.get("file_path"),
        })

    return signals
