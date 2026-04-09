"""Agent Memory：跨会话记忆系统。

借鉴 Hermes 的 Learning Loop 概念：Agent 在完成任务后自动提取
可复用的决策理由、用户偏好、策略模式，并在后续会话中引用。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MemoryEntry(BaseModel):
    """单条记忆。"""
    memory_id: str = ""
    opportunity_id: str = ""
    category: str = ""  # decision_rationale / user_preference / strategy_pattern / lesson_learned
    content: str = ""
    source_agent: str = ""
    relevance_score: float = 0.5
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentMemory:
    """SQLite-backed agent memory store."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else Path("data/agent_memory.sqlite")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    source_agent TEXT NOT NULL DEFAULT '',
                    relevance_score REAL NOT NULL DEFAULT 0.5,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_opp ON memories(opportunity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat ON memories(category)")

    def store(self, entry: MemoryEntry) -> None:
        """Store a memory entry."""
        if not entry.memory_id:
            import uuid
            entry.memory_id = uuid.uuid4().hex[:16]
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO memories
                   (memory_id, opportunity_id, category, content, source_agent, relevance_score, tags_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.memory_id,
                    entry.opportunity_id,
                    entry.category,
                    entry.content,
                    entry.source_agent,
                    entry.relevance_score,
                    json.dumps(entry.tags, ensure_ascii=False),
                    entry.created_at.isoformat(),
                ),
            )

    def recall(
        self,
        *,
        opportunity_id: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Recall memories, optionally filtered."""
        clauses = []
        params: list[Any] = []
        if opportunity_id:
            clauses.append("opportunity_id = ?")
            params.append(opportunity_id)
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM memories{where} ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        entries = []
        for row in rows:
            tags = []
            try:
                tags = json.loads(row["tags_json"])
            except Exception:
                pass
            entries.append(MemoryEntry(
                memory_id=row["memory_id"],
                opportunity_id=row["opportunity_id"],
                category=row["category"],
                content=row["content"],
                source_agent=row["source_agent"],
                relevance_score=row["relevance_score"],
                tags=tags,
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(UTC),
            ))
        return entries

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Simple keyword search across memory content."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY relevance_score DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        entries = []
        for row in rows:
            tags = []
            try:
                tags = json.loads(row["tags_json"])
            except Exception:
                pass
            entries.append(MemoryEntry(
                memory_id=row["memory_id"],
                opportunity_id=row["opportunity_id"],
                category=row["category"],
                content=row["content"],
                source_agent=row["source_agent"],
                relevance_score=row["relevance_score"],
                tags=tags,
            ))
        return entries

    def inject_context(self, opportunity_id: str, agent_role: str = "", limit: int = 5) -> str:
        """Build a memory context string for injection into LLM prompts."""
        entries = self.recall(opportunity_id=opportunity_id, limit=limit)
        if agent_role:
            role_entries = [e for e in entries if e.source_agent == agent_role]
            if role_entries:
                entries = role_entries + [e for e in entries if e.source_agent != agent_role]
                entries = entries[:limit]
        if not entries:
            return ""
        lines = []
        for e in entries:
            lines.append(f"[{e.category}|{e.source_agent}] {e.content[:150]}")
        return "\n".join(lines)

    def extract_from_result(self, opportunity_id: str, agent_role: str, explanation: str, confidence: float) -> MemoryEntry | None:
        """Auto-extract a memory from an agent result if confidence is high enough."""
        if confidence < 0.6 or len(explanation) < 20:
            return None
        entry = MemoryEntry(
            opportunity_id=opportunity_id,
            category="decision_rationale" if confidence >= 0.8 else "strategy_pattern",
            content=explanation[:500],
            source_agent=agent_role,
            relevance_score=confidence,
            tags=[agent_role],
        )
        self.store(entry)
        logger.debug("Extracted memory from %s: %s...", agent_role, explanation[:60])
        return entry
