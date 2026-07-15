"""MCP client wiring — the single point of contact between the LangGraph
agents and the external hotel/flight services.

Every tool call the graph makes goes through here. Nodes don't import
`requests`, they don't know the Convex API exists, and they never call an
MCP server directly by URL — they ask this module for a tool by name.

This is the boundary the SRS asks for: the MCP layer is the standardised
bridge, and swapping a service means changing one row of `MCP_SERVERS`,
not touching agent code.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


# Endpoints of the child MCP servers spawned by main.py on FastAPI startup.
# Overridable via env so a deployment can point at externally-hosted MCP
# servers without any code change.
HOTEL_MCP_URL = os.getenv("HOTEL_MCP_URL", "http://127.0.0.1:8001/mcp")
FLIGHT_MCP_URL = os.getenv("FLIGHT_MCP_URL", "http://127.0.0.1:8002/mcp")

MCP_SERVERS: dict[str, dict[str, Any]] = {
    "hotel": {
        "url": HOTEL_MCP_URL,
        "transport": "streamable_http",
    },
    "flight": {
        "url": FLIGHT_MCP_URL,
        "transport": "streamable_http",
    },
}


_client: Optional[MultiServerMCPClient] = None
_tools_by_name: Optional[dict[str, BaseTool]] = None


def _get_client() -> MultiServerMCPClient:
    global _client
    if _client is None:
        _client = MultiServerMCPClient(MCP_SERVERS)
    return _client


async def _load_tools() -> dict[str, BaseTool]:
    """Fetch the full tool catalog from all MCP servers, index by name.

    Called lazily by `mcp_tool()` on first use, then cached. Adding a new
    MCP server exposes its tools automatically — no agent-code edit.
    """
    global _tools_by_name
    if _tools_by_name is None:
        client = _get_client()
        tools = await client.get_tools()
        _tools_by_name = {t.name: t for t in tools}
    return _tools_by_name


class MCPToolUnavailable(RuntimeError):
    """The requested MCP tool is not registered on any connected server.

    Raised for genuinely missing tools (typo, server down, catalog stale),
    which the graph nodes catch to surface a graceful failure to the user.
    """


class MCPToolCallFailed(RuntimeError):
    """The MCP tool executed but the call raised — upstream unavailable,
    validation error, etc. Carries the original exception as `__cause__`."""


async def mcp_tool(name: str) -> BaseTool:
    """Return the MCP-backed LangChain tool with the given name.

    Nodes use this instead of importing hardcoded tools. If the tool isn't
    known (server down, name changed), an `MCPToolUnavailable` is raised
    with enough context for the caller to render a user-friendly error.
    """
    tools = await _load_tools()
    tool = tools.get(name)
    if tool is None:
        available = ", ".join(sorted(tools.keys())) or "(none)"
        raise MCPToolUnavailable(
            f"MCP tool {name!r} is not available. Loaded tools: {available}"
        )
    return tool


async def call_mcp(name: str, **kwargs: Any) -> Any:
    """Invoke an MCP tool by name and return its result.

    Any error inside the tool call is wrapped as `MCPToolCallFailed` so
    the caller has a single exception type to catch for "the external
    service didn't behave"—the SRS's graceful-failure requirement.
    """
    tool = await mcp_tool(name)
    try:
        return await tool.ainvoke(kwargs)
    except Exception as e:
        raise MCPToolCallFailed(f"MCP tool {name!r} failed: {e}") from e


async def prime_mcp_tools() -> list[str]:
    """Warm up the tool cache (used at FastAPI startup after MCP servers
    are ready). Returns the list of loaded tool names for logging."""
    tools = await _load_tools()
    return sorted(tools.keys())


def reset_mcp_cache() -> None:
    """Invalidate the tool cache — useful if MCP servers restart."""
    global _client, _tools_by_name
    _client = None
    _tools_by_name = None
