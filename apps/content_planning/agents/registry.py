"""AgentRegistry：注册、发现、按角色查找 Agent。"""

from __future__ import annotations

import logging

from apps.content_planning.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_registry: dict[str, BaseAgent] = {}


def register(agent: BaseAgent) -> None:
    _registry[agent.agent_role] = agent
    logger.debug("Registered agent: %s (%s)", agent.agent_name, agent.agent_role)


def get(role: str) -> BaseAgent | None:
    return _registry.get(role)


def list_agents() -> list[dict[str, str]]:
    return [
        {"agent_id": a.agent_id, "agent_name": a.agent_name, "agent_role": a.agent_role}
        for a in _registry.values()
    ]


def reset() -> None:
    _registry.clear()


class AgentRegistry:
    """与模块级函数等价的命名空间，便于统一导入。"""

    @staticmethod
    def register(agent: BaseAgent) -> None:
        register(agent)

    @staticmethod
    def get(role: str) -> BaseAgent | None:
        return get(role)

    @staticmethod
    def list_agents() -> list[dict[str, str]]:
        return list_agents()

    @staticmethod
    def reset() -> None:
        reset()
