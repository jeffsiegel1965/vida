"""Vida MCP Server — exposes Vida wallet + agent operations as MCP tools.

Any MCP-compatible agent (Grok Build, Claude Code, Cursor, etc.)
can use this server to check balances, plan pots, and execute agent goals.

Usage:
  export VIDA_SESSION=/path/to/session.json
  python scripts/vida_mcp_server.py

  # With Claude Code:
  claude --mcp-server "python scripts/vida_mcp_server.py"

  # With Grok Build:
  grok --mcp-server "python scripts/vida_mcp_server.py"

The server exposes:
- Wallet tools: vida_status, vida_balance, vida_send, etc.
- Agent tools: vida_agent_goal (natural language goal execution)
- Resources: vida://tool-schema (OpenAI-compatible function calling schema)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# ── MCP imports ──
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# ── Vida imports ──
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

server = Server("vida-wallet")


# ── Wallet session loader ──


def _load_session() -> dict[str, Any]:
    """Load the Vida session from env var. Returns secrets dict."""
    session_path = os.environ.get("VIDA_SESSION")
    if not session_path:
        return {"ok": False, "error": "VIDA_SESSION environment variable not set"}
    sp = Path(session_path)
    if not sp.is_file():
        return {"ok": False, "error": f"session file not found: {session_path}"}

    try:
        from vida.secure_wallet import SecureVida

        wallet_path = os.environ.get("VIDA_WALLET")
        if not wallet_path:
            return {"ok": False, "error": "VIDA_SESSION set but VIDA_WALLET not set"}
        wp = Path(wallet_path)
        if not wp.is_file():
            return {"ok": False, "error": f"wallet not found: {wallet_path}"}
        wallet = SecureVida(wp)
        try:
            wallet.load_session(sp)
        except Exception:
            return {"ok": False, "error": "failed to load session"}
        return {"ok": True, "wallet": wallet, "session": wallet.session}
    except ImportError:
        return {"ok": False, "error": "SecureVida not available"}


# ── MCP Resource handlers ──


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="vida://tool-schema",
            name="Agent Tool Schema",
            description="OpenAI-compatible function calling schema for all Vida tools",
            mimeType="application/json",
        ),
        types.Resource(
            uri="vida://status",
            name="Vida Status",
            description="Current covenant module status and capabilities",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    if uri == "vida://tool-schema":
        from vida.agents.tool_schema import TOOL_SCHEMA

        return json.dumps(TOOL_SCHEMA, indent=2)
    elif uri == "vida://status":
        from vida.plugins.covenant.tools import covenant_status

        return json.dumps(covenant_status(), indent=2)
    return json.dumps({"ok": False, "error": f"unknown resource: {uri}"})


# ── MCP Tool handlers ──


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        # ── Wallet tools ──
        types.Tool(
            name="vida_status",
            description="Check wallet status and session info",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="vida_balance",
            description="Check wallet balance (Kaspa or TAO)",
            inputSchema={
                "type": "object",
                "properties": {
                    "asset": {
                        "type": "string",
                        "enum": ["kaspa", "tao"],
                        "description": "Asset to check balance for",
                    }
                },
                "required": ["asset"],
            },
        ),
        types.Tool(
            name="vida_send",
            description="Send KAS (requires session with caps)",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount in KAS"},
                    "destination": {"type": "string", "description": "Kaspa address"},
                },
                "required": ["amount", "destination"],
            },
        ),
        # ── Covenant tools ──
        types.Tool(
            name="vida_covenant_status",
            description="Check covenant module status",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="vida_covenant_describe",
            description="List available covenant capabilities",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="vida_covenant_live_gates",
            description="Check if live covenant deployment is available",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="vida_covenant_plan_pot",
            description="Plan an agent pot with spending limits",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_kas_per_tx": {"type": "number", "description": "Max KAS per transaction"},
                    "max_kas_per_day": {"type": "number", "description": "Max KAS per day"},
                    "allowed_destinations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Allowed destination addresses",
                    },
                },
                "required": ["max_kas_per_tx", "max_kas_per_day"],
            },
        ),
        types.Tool(
            name="vida_covenant_quine_info",
            description="Get QuineAgentPot contract details",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Agent tools ──
        types.Tool(
            name="vida_agent_goal",
            description="Execute a natural language goal using the agent loop. The agent will use K2.5 to plan and execute steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "Natural language goal (e.g. 'Stake 50 TAO, plan the pot, check covenants')",
                    },
                },
                "required": ["goal"],
            },
        ),
        types.Tool(
            name="vida_agent_tool_schema",
            description="Get the OpenAI-compatible function calling schema for all agent tools",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    args = arguments or {}

    # ── Wallet tools ──
    if name == "vida_status":
        session = _load_session()
        return [types.TextContent(type="text", text=json.dumps(session, indent=2))]

    elif name == "vida_balance":
        session = _load_session()
        if not session.get("ok"):
            return [types.TextContent(type="text", text=json.dumps(session, indent=2))]
        try:
            wallet = session["wallet"]
            kas = wallet.get_balance() if hasattr(wallet, "get_balance") else "unavailable"
            return [types.TextContent(type="text", text=json.dumps({"ok": True, "kaspa": kas}, indent=2))]
        except Exception as e:
            return [types.TextContent(type="text", text=json.dumps({"ok": False, "error": str(e)}, indent=2))]

    elif name == "vida_send":
        session = _load_session()
        if not session.get("ok"):
            return [types.TextContent(type="text", text=json.dumps(session, indent=2))]
        amount = args.get("amount", 0)
        dest = args.get("destination", "")
        try:
            wallet = session["wallet"]
            result = wallet.send(dest, int(float(amount) * 1e8))
            return [types.TextContent(type="text", text=json.dumps({"ok": True, "result": str(result)}, indent=2))]
        except Exception as e:
            return [types.TextContent(type="text", text=json.dumps({"ok": False, "error": str(e)}, indent=2))]

    # ── Covenant tools ──
    elif name == "vida_covenant_status":
        from vida.plugins.covenant.tools import covenant_status

        return [types.TextContent(type="text", text=json.dumps(covenant_status(), indent=2))]

    elif name == "vida_covenant_describe":
        from vida.plugins.covenant.tools import covenant_describe

        return [types.TextContent(type="text", text=json.dumps(covenant_describe(), indent=2))]

    elif name == "vida_covenant_live_gates":
        from vida.plugins.covenant.tools import covenant_live_gates

        return [types.TextContent(type="text", text=json.dumps(covenant_live_gates(), indent=2))]

    elif name == "vida_covenant_plan_pot":
        from vida.plugins.covenant.tools import covenant_plan_pot

        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    covenant_plan_pot(
                        max_kas_per_tx=float(args.get("max_kas_per_tx", 0)),
                        max_kas_per_day=float(args.get("max_kas_per_day", 0)),
                        allowed_destinations=args.get("allowed_destinations"),
                    ),
                    indent=2,
                ),
            )
        ]

    elif name == "vida_covenant_quine_info":
        from vida.plugins.covenant.tools import covenant_quine_info

        return [types.TextContent(type="text", text=json.dumps(covenant_quine_info(), indent=2))]

    # ── Agent tools ──
    elif name == "vida_agent_goal":
        goal = args.get("goal", "Check Vida status")
        import asyncio

        from vida.agents.orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        result = asyncio.run(orch.run(goal))
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "vida_agent_tool_schema":
        from vida.agents.tool_schema import TOOL_SCHEMA

        return [types.TextContent(type="text", text=json.dumps(TOOL_SCHEMA, indent=2))]

    return [
        types.TextContent(
            type="text",
            text=json.dumps({"ok": False, "error": f"unknown tool: {name}"}, indent=2),
        )
    ]


# ── Main ──


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="vida-wallet",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
