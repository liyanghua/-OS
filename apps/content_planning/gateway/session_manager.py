"""Session Manager：多角色协同会话管理。"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentMessage(BaseModel):
    """协同会话中的单条消息。"""
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str = ""  # human_ceo / human_product / agent_trend_analyst / agent_lead / system
    sender_name: str = ""
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CoCreationSession(BaseModel):
    """绑定到 opportunity_id 的协同会话。"""
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    opportunity_id: str = ""
    messages: list[AgentMessage] = Field(default_factory=list)
    active_agent_role: str | None = None
    participants: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_message(self, role: str, content: str, sender_name: str = "", **meta: Any) -> AgentMessage:
        msg = AgentMessage(
            role=role,
            sender_name=sender_name,
            content=content,
            metadata=meta,
        )
        self.messages.append(msg)
        self.updated_at = datetime.now(UTC)
        if role not in self.participants:
            self.participants.append(role)
        return msg

    def recent_messages(self, limit: int = 20) -> list[AgentMessage]:
        return self.messages[-limit:]

    def messages_by_role(self, role_prefix: str) -> list[AgentMessage]:
        """Filter messages by role prefix (e.g., 'agent_' or 'human_')."""
        return [m for m in self.messages if m.role.startswith(role_prefix)]

    def agent_messages(self) -> list[AgentMessage]:
        return self.messages_by_role("agent_")

    def human_messages(self) -> list[AgentMessage]:
        return [m for m in self.messages if m.role.startswith("human") or m.role == "human"]

    def to_timeline(self) -> list[dict[str, Any]]:
        """Convert session to a serializable timeline for frontend."""
        items = []
        for m in self.messages:
            items.append({
                "message_id": m.message_id,
                "role": m.role,
                "sender_name": m.sender_name,
                "content": m.content,
                "metadata": m.metadata,
                "timestamp": m.timestamp.isoformat(),
                "is_agent": m.role.startswith("agent_"),
            })
        return items


class SessionManager:
    """管理多个 opportunity 的协同会话。"""

    def __init__(self) -> None:
        self._sessions: dict[str, CoCreationSession] = {}

    def get_or_create(self, opportunity_id: str) -> CoCreationSession:
        if opportunity_id not in self._sessions:
            self._sessions[opportunity_id] = CoCreationSession(opportunity_id=opportunity_id)
        return self._sessions[opportunity_id]

    def get(self, opportunity_id: str) -> CoCreationSession | None:
        return self._sessions.get(opportunity_id)

    def add_message(
        self,
        opportunity_id: str,
        role: str,
        content: str,
        sender_name: str = "",
        **meta: Any,
    ) -> AgentMessage:
        session = self.get_or_create(opportunity_id)
        return session.add_message(role, content, sender_name, **meta)

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": s.session_id,
                "opportunity_id": s.opportunity_id,
                "message_count": len(s.messages),
                "participants": s.participants,
                "updated_at": s.updated_at.isoformat(),
            }
            for s in self._sessions.values()
        ]

    def get_timeline(self, opportunity_id: str) -> list[dict[str, Any]]:
        """Get full timeline for an opportunity."""
        session = self.get(opportunity_id)
        if session is None:
            return []
        return session.to_timeline()

    def get_participants(self, opportunity_id: str) -> list[str]:
        """List all participants in a session."""
        session = self.get(opportunity_id)
        if session is None:
            return []
        return list(session.participants)

    def export_conversation(self, opportunity_id: str) -> dict[str, Any]:
        """Export full conversation for an opportunity."""
        session = self.get(opportunity_id)
        if session is None:
            return {"opportunity_id": opportunity_id, "messages": [], "participants": []}
        return {
            "session_id": session.session_id,
            "opportunity_id": opportunity_id,
            "messages": [m.model_dump(mode="json") for m in session.messages],
            "participants": session.participants,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }

    def clear(self, opportunity_id: str | None = None) -> None:
        if opportunity_id:
            self._sessions.pop(opportunity_id, None)
        else:
            self._sessions.clear()


# Singleton
session_manager = SessionManager()
