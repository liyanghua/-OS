"""Agent Memory v2：FTS5 全文检索 + 跨会话检索 + nudge 机制。

借鉴 Hermes Agent 的 FTS5 记忆系统：
- FTS5 全文检索替代 LIKE 模糊查询
- 跨会话检索（从历史 pipeline runs 中检索）
- Nudge 机制：定期提示 Agent 是否有值得记住的内容
- 语义相关性排序（FTS5 rank + relevance_score）
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MemoryEntry(BaseModel):
    """单条记忆。"""
    memory_id: str = ""
    opportunity_id: str = ""
    session_id: str = ""
    category: str = ""
    content: str = ""
    source_agent: str = ""
    relevance_score: float = 0.5
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    nudge_source: str = ""


class NudgeResult(BaseModel):
    """Agent 对 nudge 提问的回答。"""
    should_remember: bool = False
    content: str = ""
    category: str = "lesson_learned"
    tags: list[str] = Field(default_factory=list)


class AgentMemory:
    """SQLite-backed agent memory with FTS5 full-text search."""

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
                    session_id TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    source_agent TEXT NOT NULL DEFAULT '',
                    relevance_score REAL NOT NULL DEFAULT 0.5,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT '',
                    nudge_source TEXT NOT NULL DEFAULT ''
                )
            """)
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
            migrations = {
                "session_id": "ALTER TABLE memories ADD COLUMN session_id TEXT NOT NULL DEFAULT ''",
                "nudge_source": "ALTER TABLE memories ADD COLUMN nudge_source TEXT NOT NULL DEFAULT ''",
            }
            for col, ddl in migrations.items():
                if col not in existing_cols:
                    try:
                        conn.execute(ddl)
                        logger.info("Migrated memories table: added column %s", col)
                    except sqlite3.OperationalError:
                        pass

            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_opp ON memories(opportunity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id)")

            # FTS5 virtual table for full-text search
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                    USING fts5(
                        memory_id UNINDEXED,
                        content,
                        category,
                        source_agent,
                        tags_text,
                        content=memories,
                        content_rowid=rowid
                    )
                """)
            except sqlite3.OperationalError:
                logger.debug("FTS5 table already exists or not supported", exc_info=True)

            # Triggers to keep FTS in sync
            for trigger_sql in [
                """CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, memory_id, content, category, source_agent, tags_text)
                    VALUES (new.rowid, new.memory_id, new.content, new.category, new.source_agent, new.tags_json);
                END""",
                """CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, memory_id, content, category, source_agent, tags_text)
                    VALUES ('delete', old.rowid, old.memory_id, old.content, old.category, old.source_agent, old.tags_json);
                END""",
                """CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, memory_id, content, category, source_agent, tags_text)
                    VALUES ('delete', old.rowid, old.memory_id, old.content, old.category, old.source_agent, old.tags_json);
                    INSERT INTO memories_fts(rowid, memory_id, content, category, source_agent, tags_text)
                    VALUES (new.rowid, new.memory_id, new.content, new.category, new.source_agent, new.tags_json);
                END""",
            ]:
                try:
                    conn.execute(trigger_sql)
                except sqlite3.OperationalError:
                    pass

    def store(self, entry: MemoryEntry) -> None:
        if not entry.memory_id:
            entry.memory_id = uuid.uuid4().hex[:16]
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO memories
                   (memory_id, opportunity_id, session_id, category, content, source_agent,
                    relevance_score, tags_json, created_at, nudge_source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.memory_id, entry.opportunity_id, entry.session_id,
                    entry.category, entry.content, entry.source_agent,
                    entry.relevance_score, json.dumps(entry.tags, ensure_ascii=False),
                    entry.created_at.isoformat(), entry.nudge_source,
                ),
            )

    def recall(
        self,
        *,
        opportunity_id: str | None = None,
        category: str | None = None,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        clauses = []
        params: list[Any] = []
        if opportunity_id:
            clauses.append("opportunity_id = ?")
            params.append(opportunity_id)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM memories{where} ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """FTS5-powered full-text search across memory content."""
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """SELECT m.*, rank
                       FROM memories_fts fts
                       JOIN memories m ON fts.memory_id = m.memory_id
                       WHERE memories_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, limit),
                ).fetchall()
                if rows:
                    return [self._row_to_entry(row) for row in rows]
            except sqlite3.OperationalError:
                logger.debug("FTS5 search failed, falling back to LIKE", exc_info=True)

            rows = conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY relevance_score DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def search_sessions(self, query: str, *, limit: int = 5) -> list[MemoryEntry]:
        """Cross-session search: find memories across all pipeline runs."""
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """SELECT m.*, rank
                       FROM memories_fts fts
                       JOIN memories m ON fts.memory_id = m.memory_id
                       WHERE memories_fts MATCH ?
                       AND m.session_id != ''
                       ORDER BY rank
                       LIMIT ?""",
                    (query, limit),
                ).fetchall()
                if rows:
                    return [self._row_to_entry(row) for row in rows]
            except sqlite3.OperationalError:
                pass

            rows = conn.execute(
                """SELECT * FROM memories
                   WHERE content LIKE ? AND session_id != ''
                   ORDER BY relevance_score DESC LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def inject_context(self, opportunity_id: str, agent_role: str = "", limit: int = 5) -> str:
        """Build a memory context string with semantic relevance ranking."""
        entries = self.recall(opportunity_id=opportunity_id, limit=limit * 2)

        if agent_role:
            role_entries = [e for e in entries if e.source_agent == agent_role]
            other_entries = [e for e in entries if e.source_agent != agent_role]
            for re in role_entries:
                re.relevance_score += 0.1
            entries = sorted(role_entries + other_entries, key=lambda e: e.relevance_score, reverse=True)[:limit]
        else:
            entries = sorted(entries, key=lambda e: e.relevance_score, reverse=True)[:limit]

        if not entries:
            return ""
        lines = []
        for e in entries:
            lines.append(f"[{e.category}|{e.source_agent}|{e.relevance_score:.1f}] {e.content[:150]}")
        return "\n".join(lines)

    def extract_from_result(
        self,
        opportunity_id: str,
        agent_role: str,
        explanation: str,
        confidence: float,
        *,
        session_id: str = "",
    ) -> MemoryEntry | None:
        if confidence < 0.6 or len(explanation) < 20:
            return None
        entry = MemoryEntry(
            opportunity_id=opportunity_id,
            session_id=session_id,
            category="decision_rationale" if confidence >= 0.8 else "strategy_pattern",
            content=explanation[:500],
            source_agent=agent_role,
            relevance_score=confidence,
            tags=[agent_role],
        )
        self.store(entry)
        logger.debug("Extracted memory from %s: %s...", agent_role, explanation[:60])
        return entry

    def nudge(self, opportunity_id: str, agent_role: str, context_summary: str) -> str:
        """Generate a nudge prompt asking the Agent if there's something worth remembering.

        Returns a prompt string that should be appended to the Agent's next LLM call.
        The LLM response should be parsed into a NudgeResult.
        """
        existing = self.recall(opportunity_id=opportunity_id, limit=3)
        existing_summary = "; ".join([e.content[:50] for e in existing]) if existing else "无"

        return (
            f"\n---\n[记忆助手] 基于刚才的工作，是否有值得记住的经验或教训？\n"
            f"已有记忆: {existing_summary}\n"
            f"当前上下文: {context_summary[:200]}\n"
            f"如果有，请以 JSON 格式返回: {{\"should_remember\": true, \"content\": \"...\", \"category\": \"lesson_learned\", \"tags\": [...]}}\n"
            f"如果没有，返回: {{\"should_remember\": false}}"
        )

    def process_nudge_response(
        self,
        opportunity_id: str,
        agent_role: str,
        response_text: str,
        *,
        session_id: str = "",
    ) -> MemoryEntry | None:
        """Process a nudge response from an Agent and store if applicable."""
        try:
            text = response_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                end_idx = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
                text = "\n".join(lines[1:end_idx])
            data = json.loads(text)
            nudge = NudgeResult(**data)
            if not nudge.should_remember or not nudge.content:
                return None
            entry = MemoryEntry(
                opportunity_id=opportunity_id,
                session_id=session_id,
                category=nudge.category or "lesson_learned",
                content=nudge.content[:500],
                source_agent=agent_role,
                relevance_score=0.7,
                tags=nudge.tags or [agent_role],
                nudge_source="agent_nudge",
            )
            self.store(entry)
            return entry
        except Exception:
            logger.debug("Failed to process nudge response", exc_info=True)
            return None

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        tags = []
        try:
            tags = json.loads(row["tags_json"])
        except Exception:
            pass
        return MemoryEntry(
            memory_id=row["memory_id"],
            opportunity_id=row["opportunity_id"],
            session_id=row["session_id"] if "session_id" in row.keys() else "",
            category=row["category"],
            content=row["content"],
            source_agent=row["source_agent"],
            relevance_score=row["relevance_score"],
            tags=tags,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(UTC),
            nudge_source=row["nudge_source"] if "nudge_source" in row.keys() else "",
        )
