"""Agent base class (Phase 4).

Agents are deterministic orchestrators: given an intent + inputs + context, they
call MCP tools (via the MCPClientManager) and persist results. They contain no
LLM/planning logic (that lives in the planner) and no transport logic.

``handle`` is async because MCP tool calls are async; the PlanExecutor (Phase 7)
awaits agents in dependency order.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.mcp_clients.mcp_client_manager import MCPClientManager
from backend.storage.db import Database


@dataclass
class AgentResult:
    """Uniform result returned by every agent step."""

    agent: str
    intent: str
    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "intent": self.intent,
            "success": self.success,
            "summary": self.summary,
            "data": self.data,
            "error": self.error,
        }


class BaseAgent(ABC):
    """Common wiring (MCP client + DB) and the agent contract."""

    name: str = "base_agent"

    def __init__(self, mcp: MCPClientManager, db: Database) -> None:
        self.mcp = mcp
        self.db = db

    @abstractmethod
    async def handle(
        self,
        intent: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        """Execute one step for ``intent`` and return an :class:`AgentResult`."""

    # -- helpers shared by concrete agents ------------------------------- #
    @staticmethod
    def _current_video(context: dict[str, Any]) -> Optional[dict[str, Any]]:
        return context.get("current_video")

    def _ok(self, intent: str, summary: str, data: dict[str, Any]) -> AgentResult:
        return AgentResult(self.name, intent, True, summary, data)

    def _fail(self, intent: str, error: str) -> AgentResult:
        return AgentResult(self.name, intent, False, error, {}, error=error)
