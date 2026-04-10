"""MCP (Model Context Protocol) Adapter: dynamic external tool discovery.

Connects to MCP-compatible tool servers and registers their tools
into the unified ToolRegistry.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection."""
    name: str = ""
    url: str = ""
    transport: str = "stdio"  # stdio | http | sse
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    toolset_name: str = ""


class MCPToolSpec(BaseModel):
    """Tool specification from an MCP server."""
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    server_name: str = ""


class MCPAdapter:
    """Discovers and registers tools from MCP servers.

    Currently a structural placeholder -- actual MCP protocol communication
    requires the `mcp` Python SDK. This adapter defines the integration
    surface so that real MCP servers can be plugged in later.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._discovered_tools: dict[str, MCPToolSpec] = {}

    def add_server(self, config: MCPServerConfig) -> None:
        self._servers[config.name] = config
        logger.info("Added MCP server: %s (%s)", config.name, config.url or config.command)

    def remove_server(self, name: str) -> None:
        self._servers.pop(name, None)
        to_remove = [k for k, v in self._discovered_tools.items() if v.server_name == name]
        for k in to_remove:
            self._discovered_tools.pop(k, None)

    async def discover_tools(self, server_name: str | None = None) -> list[MCPToolSpec]:
        """Discover tools from one or all MCP servers.

        In the real implementation this would use the MCP SDK to
        call `tools/list` on each server. For now returns any
        manually pre-registered specs.
        """
        targets = [self._servers[server_name]] if server_name and server_name in self._servers else list(self._servers.values())
        all_tools: list[MCPToolSpec] = []
        for server in targets:
            if not server.enabled:
                continue
            tools = await self._discover_from_server(server)
            all_tools.extend(tools)
            for tool in tools:
                self._discovered_tools[f"{server.name}:{tool.name}"] = tool
        return all_tools

    async def _discover_from_server(self, server: MCPServerConfig) -> list[MCPToolSpec]:
        """Placeholder for actual MCP protocol communication."""
        logger.debug("MCP discovery for %s (placeholder -- no real connection yet)", server.name)
        return []

    def register_discovered_tools(self) -> int:
        """Register all discovered MCP tools into the global ToolRegistry."""
        from apps.content_planning.agents.tool_registry import tool_registry, ToolEntry
        count = 0
        for key, spec in self._discovered_tools.items():
            toolset = spec.server_name or "mcp"
            tool_registry.register(ToolEntry(
                name=f"mcp_{spec.name}",
                description=spec.description,
                parameters_schema=spec.input_schema or {"type": "object", "properties": {}},
                handler=self._make_handler(spec),
                toolset=f"mcp_{toolset}",
            ))
            count += 1
        logger.info("Registered %d MCP tools", count)
        return count

    def _make_handler(self, spec: MCPToolSpec) -> Any:
        """Create a handler function for an MCP tool.

        In real implementation, this would call the MCP server's `tools/call`
        endpoint. For now returns a placeholder.
        """
        def handler(**kwargs: Any) -> dict[str, Any]:
            return {
                "status": "mcp_not_connected",
                "tool": spec.name,
                "server": spec.server_name,
                "args": kwargs,
            }
        return handler

    def pre_register_tool(self, spec: MCPToolSpec) -> None:
        """Manually pre-register an MCP tool spec (for testing or static configs)."""
        key = f"{spec.server_name}:{spec.name}"
        self._discovered_tools[key] = spec

    @property
    def server_count(self) -> int:
        return len(self._servers)

    @property
    def tool_count(self) -> int:
        return len(self._discovered_tools)


# Singleton
mcp_adapter = MCPAdapter()
