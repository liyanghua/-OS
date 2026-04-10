"""轻量 SQLite 存储 —— 内容规划会话（可查询列 + JSON 载荷列）。"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 逻辑字段名 -> 表列名（update_field 可用）
_FIELD_TO_COLUMN: dict[str, str] = {
    "session_status": "session_status",
    "workspace_id": "workspace_id",
    "brand_id": "brand_id",
    "campaign_id": "campaign_id",
    "created_by": "created_by",
    "updated_by": "updated_by",
    "visibility": "visibility",
    "version": "version",
    "brief": "brief_json",
    "brief_json": "brief_json",
    "match_result": "match_json",
    "match_json": "match_json",
    "strategy": "strategy_json",
    "strategy_json": "strategy_json",
    "plan": "plan_json",
    "plan_json": "plan_json",
    "titles": "titles_json",
    "titles_json": "titles_json",
    "body": "body_json",
    "body_json": "body_json",
    "image_briefs": "image_briefs_json",
    "image_briefs_json": "image_briefs_json",
    "asset_bundle": "asset_bundle_json",
    "asset_bundle_json": "asset_bundle_json",
    "pipeline_run_id": "pipeline_run_id",
    "stale_flags": "stale_flags_json",
    "stale_flags_json": "stale_flags_json",
    "agent_actions": "agent_actions_json",
    "agent_actions_json": "agent_actions_json",
}

_JSON_COLUMNS = frozenset(
    {
        "brief_json",
        "match_json",
        "strategy_json",
        "plan_json",
        "titles_json",
        "body_json",
        "image_briefs_json",
        "asset_bundle_json",
        "stale_flags_json",
        "agent_actions_json",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(value: Any) -> str:
    """Pydantic v2 用 model_dump_json，否则 json.dumps。"""
    dump_json = getattr(value, "model_dump_json", None)
    if callable(dump_json):
        return dump_json()
    return json.dumps(value, ensure_ascii=False)


def _deserialize(raw: str | None) -> Any:
    if raw is None or raw == "":
        return None
    return json.loads(raw)


class ContentPlanStore:
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
                CREATE TABLE IF NOT EXISTS planning_sessions (
                    opportunity_id TEXT PRIMARY KEY,
                    session_status TEXT NOT NULL DEFAULT 'draft',
                    workspace_id TEXT,
                    brand_id TEXT,
                    campaign_id TEXT,
                    created_by TEXT,
                    updated_by TEXT,
                    visibility TEXT NOT NULL DEFAULT 'workspace',
                    version INTEGER NOT NULL DEFAULT 1,
                    brief_json TEXT,
                    match_json TEXT,
                    strategy_json TEXT,
                    plan_json TEXT,
                    titles_json TEXT,
                    body_json TEXT,
                    image_briefs_json TEXT,
                    brief_versions_json TEXT,
                    strategy_versions_json TEXT,
                    plan_versions_json TEXT,
                    asset_bundle_versions_json TEXT,
                    asset_bundle_json TEXT,
                    pipeline_run_id TEXT,
                    stale_flags_json TEXT,
                    agent_actions_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    eval_type TEXT NOT NULL DEFAULT 'pipeline',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    run_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    opportunity_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    run_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stage_discussions (
                    discussion_id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    proposal_id TEXT,
                    run_id TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stage_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposal_decisions (
                    decision_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_opp ON evaluations(opportunity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_opp ON agent_tasks(opportunity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_opp ON agent_runs(opportunity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discussions_opp ON stage_discussions(opportunity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_proposals_opp ON stage_proposals(opportunity_id)")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_planning_sessions_status
                ON planning_sessions(session_status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_planning_sessions_updated_at
                ON planning_sessions(updated_at DESC)
            """)
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(planning_sessions)").fetchall()
            }
            for column, ddl in {
                "workspace_id": "TEXT",
                "brand_id": "TEXT",
                "campaign_id": "TEXT",
                "created_by": "TEXT",
                "updated_by": "TEXT",
                "visibility": "TEXT NOT NULL DEFAULT 'workspace'",
                "version": "INTEGER NOT NULL DEFAULT 1",
                "asset_bundle_json": "TEXT",
                "brief_versions_json": "TEXT",
                "strategy_versions_json": "TEXT",
                "plan_versions_json": "TEXT",
                "asset_bundle_versions_json": "TEXT",
                "agent_actions_json": "TEXT",
            }.items():
                if column not in existing_columns:
                    conn.execute(f"ALTER TABLE planning_sessions ADD COLUMN {column} {ddl}")

    def save_session(
        self,
        opportunity_id: str,
        *,
        session_status: str = "draft",
        workspace_id: str | None = None,
        brand_id: str | None = None,
        campaign_id: str | None = None,
        created_by: str | None = None,
        updated_by: str | None = None,
        visibility: str | None = None,
        version: int | None = None,
        brief: Any = None,
        match_result: Any = None,
        strategy: Any = None,
        plan: Any = None,
        titles: Any = None,
        body: Any = None,
        image_briefs: Any = None,
        asset_bundle: Any = None,
        pipeline_run_id: str | None = None,
        stale_flags: dict[str, bool] | None = None,
    ) -> None:
        """UPSERT：更新时仅写入非 None 的 JSON/关联字段；session_status 每次均写入。"""
        now = _utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT opportunity_id FROM planning_sessions WHERE opportunity_id = ?",
                (opportunity_id,),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO planning_sessions (
                        opportunity_id, session_status,
                        workspace_id, brand_id, campaign_id, created_by, updated_by, visibility, version,
                        brief_json, match_json, strategy_json, plan_json,
                        titles_json, body_json, image_briefs_json, asset_bundle_json,
                        pipeline_run_id, stale_flags_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        opportunity_id,
                        session_status,
                        workspace_id,
                        brand_id,
                        campaign_id,
                        created_by,
                        updated_by,
                        visibility or "workspace",
                        version or 1,
                        _serialize(brief) if brief is not None else None,
                        _serialize(match_result) if match_result is not None else None,
                        _serialize(strategy) if strategy is not None else None,
                        _serialize(plan) if plan is not None else None,
                        _serialize(titles) if titles is not None else None,
                        _serialize(body) if body is not None else None,
                        _serialize(image_briefs) if image_briefs is not None else None,
                        _serialize(asset_bundle) if asset_bundle is not None else None,
                        pipeline_run_id,
                        _serialize(stale_flags) if stale_flags is not None else None,
                        now,
                        now,
                    ),
                )
                return

            assignments: list[str] = []
            params: list[Any] = []

            assignments.append("session_status = ?")
            params.append(session_status)
            if workspace_id is not None:
                assignments.append("workspace_id = ?")
                params.append(workspace_id)
            if brand_id is not None:
                assignments.append("brand_id = ?")
                params.append(brand_id)
            if campaign_id is not None:
                assignments.append("campaign_id = ?")
                params.append(campaign_id)
            if created_by is not None:
                assignments.append("created_by = ?")
                params.append(created_by)
            if updated_by is not None:
                assignments.append("updated_by = ?")
                params.append(updated_by)
            if visibility is not None:
                assignments.append("visibility = ?")
                params.append(visibility)
            if version is not None:
                assignments.append("version = ?")
                params.append(version)

            if brief is not None:
                assignments.append("brief_json = ?")
                params.append(_serialize(brief))
            if match_result is not None:
                assignments.append("match_json = ?")
                params.append(_serialize(match_result))
            if strategy is not None:
                assignments.append("strategy_json = ?")
                params.append(_serialize(strategy))
            if plan is not None:
                assignments.append("plan_json = ?")
                params.append(_serialize(plan))
            if titles is not None:
                assignments.append("titles_json = ?")
                params.append(_serialize(titles))
            if body is not None:
                assignments.append("body_json = ?")
                params.append(_serialize(body))
            if image_briefs is not None:
                assignments.append("image_briefs_json = ?")
                params.append(_serialize(image_briefs))
            if asset_bundle is not None:
                assignments.append("asset_bundle_json = ?")
                params.append(_serialize(asset_bundle))
            if pipeline_run_id is not None:
                assignments.append("pipeline_run_id = ?")
                params.append(pipeline_run_id)
            if stale_flags is not None:
                assignments.append("stale_flags_json = ?")
                params.append(_serialize(stale_flags))

            assignments.append("updated_at = ?")
            params.append(now)
            params.append(opportunity_id)

            conn.execute(
                f"UPDATE planning_sessions SET {', '.join(assignments)} WHERE opportunity_id = ?",
                params,
            )

    def load_session(self, opportunity_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT opportunity_id, session_status,
                       workspace_id, brand_id, campaign_id, created_by, updated_by, visibility, version,
                       brief_json, match_json, strategy_json, plan_json,
                       titles_json, body_json, image_briefs_json,
                       brief_versions_json, strategy_versions_json, plan_versions_json, asset_bundle_versions_json,
                       asset_bundle_json,
                       pipeline_run_id, stale_flags_json, agent_actions_json,
                       created_at, updated_at
                FROM planning_sessions WHERE opportunity_id = ?
                """,
                (opportunity_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "opportunity_id": row["opportunity_id"],
            "session_status": row["session_status"],
            "workspace_id": row["workspace_id"],
            "brand_id": row["brand_id"],
            "campaign_id": row["campaign_id"],
            "created_by": row["created_by"],
            "updated_by": row["updated_by"],
            "visibility": row["visibility"],
            "version": row["version"],
            "brief": _deserialize(row["brief_json"]),
            "match_result": _deserialize(row["match_json"]),
            "strategy": _deserialize(row["strategy_json"]),
            "plan": _deserialize(row["plan_json"]),
            "titles": _deserialize(row["titles_json"]),
            "body": _deserialize(row["body_json"]),
            "image_briefs": _deserialize(row["image_briefs_json"]),
            "brief_versions": _deserialize(row["brief_versions_json"]),
            "strategy_versions": _deserialize(row["strategy_versions_json"]),
            "plan_versions": _deserialize(row["plan_versions_json"]),
            "asset_bundle_versions": _deserialize(row["asset_bundle_versions_json"]),
            "asset_bundle": _deserialize(row["asset_bundle_json"]),
            "pipeline_run_id": row["pipeline_run_id"],
            "stale_flags": _deserialize(row["stale_flags_json"]),
            "agent_actions": _deserialize(row["agent_actions_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def update_field(self, opportunity_id: str, field: str, value: Any) -> None:
        column = _FIELD_TO_COLUMN.get(field)
        if column is None:
            raise ValueError(f"未知字段: {field}")

        if column in _JSON_COLUMNS:
            db_value = _serialize(value) if value is not None else None
        else:
            db_value = value

        now = _utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE planning_sessions SET {column} = ?, updated_at = ? WHERE opportunity_id = ?",
                (db_value, now, opportunity_id),
            )
            if cur.rowcount == 0:
                logger.warning(
                    "update_field: 未找到 opportunity_id=%s，跳过更新", opportunity_id
                )

    def update_stale_flags(self, opportunity_id: str, flags: dict[str, bool]) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE planning_sessions
                SET stale_flags_json = ?, updated_at = ?
                WHERE opportunity_id = ?
                """,
                (_serialize(flags), now, opportunity_id),
            )
            if cur.rowcount == 0:
                logger.warning(
                    "update_stale_flags: 未找到 opportunity_id=%s，跳过更新", opportunity_id
                )

    def append_version(self, opportunity_id: str, object_type: str, version_data: Any) -> None:
        """Append a version snapshot to the versions list."""
        col_map = {
            "brief": "brief_versions_json",
            "strategy": "strategy_versions_json",
            "plan": "plan_versions_json",
            "asset_bundle": "asset_bundle_versions_json",
        }
        column = col_map.get(object_type)
        if column is None:
            raise ValueError(f"Unknown object_type: {object_type}")

        session = self.load_session(opportunity_id)
        if session is None:
            return

        versions_key = f"{object_type}_versions"
        existing = []
        raw = session.get(versions_key)
        if isinstance(raw, list):
            existing = raw

        new_ver = version_data.model_dump(mode="json") if hasattr(version_data, "model_dump") else version_data
        existing.append(new_ver)

        # Keep max 10 versions
        if len(existing) > 10:
            existing = existing[-10:]

        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                f"UPDATE planning_sessions SET {column} = ?, updated_at = ? WHERE opportunity_id = ?",
                (_serialize(existing), now, opportunity_id),
            )

    def load_versions(self, opportunity_id: str, object_type: str) -> list[dict]:
        """Load all version snapshots for an object type."""
        session = self.load_session(opportunity_id)
        if session is None:
            return []
        versions_key = f"{object_type}_versions"
        raw = session.get(versions_key)
        if isinstance(raw, list):
            return raw
        return []

    def save_strategy(self, opportunity_id: str, strategy: Any) -> None:
        """Append a strategy to the strategy list for this opportunity."""
        existing = self.load_session(opportunity_id)
        if existing is None:
            self.save_session(opportunity_id, strategy=strategy)
            return

        current_strategies = existing.get("strategy")
        strategies_list: list = []
        if isinstance(current_strategies, list):
            strategies_list = current_strategies
        elif isinstance(current_strategies, dict):
            strategies_list = [current_strategies]

        new_strategy = strategy.model_dump(mode="json") if hasattr(strategy, "model_dump") else strategy
        strategies_list.append(new_strategy)

        self.update_field(opportunity_id, "strategy_json", strategies_list)

    def load_strategies(self, opportunity_id: str) -> list[dict]:
        """Load all strategies for an opportunity."""
        session = self.load_session(opportunity_id)
        if session is None:
            return []
        raw = session.get("strategy")
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return [raw]
        return []

    def list_sessions(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        filters: list[str] = []
        params: list[Any] = []
        if status is not None:
            filters.append("session_status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        page = max(page, 1)
        page_size = max(page_size, 1)
        offset = (page - 1) * page_size

        with self._connect() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM planning_sessions {where}",
                params,
            ).fetchone()
            total = int(total_row["c"]) if total_row else 0

            rows = conn.execute(
                f"""
                SELECT opportunity_id, session_status,
                       workspace_id, brand_id, campaign_id, created_by, updated_by, visibility, version,
                       brief_json, match_json, strategy_json, plan_json,
                       titles_json, body_json, image_briefs_json, asset_bundle_json,
                       pipeline_run_id, stale_flags_json,
                       created_at, updated_at
                FROM planning_sessions {where}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, offset],
            ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "opportunity_id": row["opportunity_id"],
                    "session_status": row["session_status"],
                    "workspace_id": row["workspace_id"],
                    "brand_id": row["brand_id"],
                    "campaign_id": row["campaign_id"],
                    "created_by": row["created_by"],
                    "updated_by": row["updated_by"],
                    "visibility": row["visibility"],
                    "version": row["version"],
                    "brief": _deserialize(row["brief_json"]),
                    "match_result": _deserialize(row["match_json"]),
                    "strategy": _deserialize(row["strategy_json"]),
                    "plan": _deserialize(row["plan_json"]),
                    "titles": _deserialize(row["titles_json"]),
                    "body": _deserialize(row["body_json"]),
                    "image_briefs": _deserialize(row["image_briefs_json"]),
                    "asset_bundle": _deserialize(row["asset_bundle_json"]),
                    "pipeline_run_id": row["pipeline_run_id"],
                    "stale_flags": _deserialize(row["stale_flags_json"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def delete_session(self, opportunity_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM planning_sessions WHERE opportunity_id = ?",
                (opportunity_id,),
            )
            return cur.rowcount > 0

    def session_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM planning_sessions").fetchone()
            return int(row["c"]) if row else 0

    def save_evaluation(self, evaluation_id: str, opportunity_id: str,
                        eval_type: str, payload: Any) -> None:
        """Store an evaluation result."""
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO evaluations
                   (evaluation_id, opportunity_id, eval_type, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (evaluation_id, opportunity_id, eval_type, _serialize(payload), now),
            )

    def load_evaluations(self, opportunity_id: str, eval_type: str | None = None,
                         limit: int = 20) -> list[dict[str, Any]]:
        """Load evaluation results for an opportunity."""
        clauses = ["opportunity_id = ?"]
        params: list[Any] = [opportunity_id]
        if eval_type:
            clauses.append("eval_type = ?")
            params.append(eval_type)
        where = " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM evaluations WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        results = []
        for row in rows:
            payload = _deserialize(row["payload_json"])
            results.append({
                "evaluation_id": row["evaluation_id"],
                "opportunity_id": row["opportunity_id"],
                "eval_type": row["eval_type"],
                "payload": payload,
                "created_at": row["created_at"],
            })
        return results

    def save_agent_task(self, task_id: str, opportunity_id: str, stage: str, run_mode: str, status: str, payload: Any) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agent_tasks
                   (task_id, opportunity_id, stage, run_mode, status, payload_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, opportunity_id, stage, run_mode, status, _serialize(payload), now, now),
            )

    def load_agent_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "opportunity_id": row["opportunity_id"],
            "stage": row["stage"],
            "run_mode": row["run_mode"],
            "status": row["status"],
            "payload": _deserialize(row["payload_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def save_agent_run(self, run_id: str, task_id: str, opportunity_id: str, stage: str, run_mode: str, status: str, payload: Any) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agent_runs
                   (run_id, task_id, opportunity_id, stage, run_mode, status, payload_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, task_id, opportunity_id, stage, run_mode, status, _serialize(payload), now, now),
            )

    def load_agent_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row["run_id"],
            "task_id": row["task_id"],
            "opportunity_id": row["opportunity_id"],
            "stage": row["stage"],
            "run_mode": row["run_mode"],
            "status": row["status"],
            "payload": _deserialize(row["payload_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def save_discussion(self, discussion_id: str, opportunity_id: str, stage: str, proposal_id: str, run_id: str, payload: Any) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO stage_discussions
                   (discussion_id, opportunity_id, stage, proposal_id, run_id, payload_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (discussion_id, opportunity_id, stage, proposal_id, run_id, _serialize(payload), now, now),
            )

    def load_discussion(self, discussion_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM stage_discussions WHERE discussion_id = ?",
                (discussion_id,),
            ).fetchone()
        if row is None:
            return None
        payload = _deserialize(row["payload_json"]) or {}
        payload.update(
            {
                "discussion_id": row["discussion_id"],
                "opportunity_id": row["opportunity_id"],
                "stage": row["stage"],
                "proposal_id": row["proposal_id"],
                "run_id": row["run_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def save_proposal(self, proposal_id: str, opportunity_id: str, stage: str, status: str, payload: Any) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO stage_proposals
                   (proposal_id, opportunity_id, stage, status, payload_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (proposal_id, opportunity_id, stage, status, _serialize(payload), now, now),
            )

    def load_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM stage_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        payload = _deserialize(row["payload_json"]) or {}
        payload.update(
            {
                "proposal_id": row["proposal_id"],
                "opportunity_id": row["opportunity_id"],
                "stage": row["stage"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return payload

    def save_proposal_decision(self, decision_id: str, proposal_id: str, decision: str, payload: Any) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO proposal_decisions
                   (decision_id, proposal_id, decision, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (decision_id, proposal_id, decision, _serialize(payload), now),
            )
