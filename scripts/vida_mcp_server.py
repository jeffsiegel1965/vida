#!/usr/bin/env python3
"""
Vida MCP Server — exposes Vida wallet operations as MCP tools.

Any MCP-compatible agent (Grok Build, Claude Code, Cursor, etc.)
can use this server to send KAS, check balances, and manage sessions.

Usage:
  export VIDA_SESSION=/path/to/session.json
  python scripts/vida_mcp_server.py

  # Or with Grok Build:
  grok --mcp-server "python scripts/vida_mcp_server.py"

Security:
  - Requires a granted session file (owner runs grant_session.py first)
  - Agent never sees the seed or password
  - All spends enforce session caps
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

    # Try Kaspa session
    try:
        from vida.secure_wallet import SecureVida

        # Need wallet path too — try VIDA_WALLET
        wallet_path = os.environ.get("VIDA_WALLET")
        if wallet_path and Path(wallet_path).is_file():
            agent = SecureVida(str(wallet_path), _session_file=str(sp))
            return {"ok": True, "type": "kaspa", "wallet": agent, "address": agent.address}
    except Exception as e:
        pass

    # Try TAO session
    try:
        from vida.plugins.tao import load_tao_session_secrets

        secrets = load_tao_session_secrets(str(sp))
        if secrets.get("ok"):
            return {
                "ok": True,
                "type": "tao",
                "secrets": secrets,
                "ss58_address": secrets.get("ss58_address"),
            }
    except Exception:
        pass

    return {"ok": False, "error": "failed to load session — check VIDA_SESSION and VIDA_WALLET"}


# ── MCP Tool handlers ──


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
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
                    "to_address": {"type": "string", "description": "Kaspa address"},
                    "amount_kas": {"type": "number", "description": "Amount in KAS"},
                    "asset": {
                        "type": "string",
                        "enum": ["kaspa", "tao"],
                        "description": "Asset to send",
                    },
                },
                "required": ["to_address", "amount_kas", "asset"],
            },
        ),
        types.Tool(
            name="vida_session_info",
            description="Show current session limits and expiry",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="vida_covenant_status",
            description="Check covenant module status",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="vida_covenant_plan_pot",
            description="Plan an agent covenant pot",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_kas_per_tx": {"type": "number", "description": "Max per tx"},
                    "max_kas_per_day": {"type": "number", "description": "Max per day"},
                    "network": {
                        "type": "string",
                        "enum": ["mainnet", "testnet-10"],
                        "description": "Network",
                    },
                },
                "required": ["max_kas_per_tx", "max_kas_per_day"],
            },
        ),
]
@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    if name == "vida_status":
        session = _load_session()
        if not session.get("ok"):
            return [types.TextContent(type="text", text=json.dumps(session, indent=2))]
        if session["type"] == "kaspa":
            wallet = session["wallet"]
            info = {
                "ok": True,
                "type": "kaspa",
                "address": session["address"],
                "network": getattr(wallet, "network", "unknown"),
                "session_expires_at": getattr(wallet, "session_expires_at", None),
                "session_daily_spent": getattr(wallet, "session_daily_spent", 0.0),
                "limits": getattr(wallet, "session_limits", {}),
            }
            return [types.TextContent(type="text", text=json.dumps(info, indent=2))]
        else:
            secrets = session["secrets"]
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "ok": True,
                            "type": "tao",
                            "ss58_address": secrets.get("ss58_address"),
                            "limits": secrets.get("limits"),
                            "daily_spent": secrets.get("daily_spent"),
                        },
                        indent=2,
                    ),
                )
            ]

    elif name == "vida_session_info":
        session = _load_session()
        if not session.get("ok"):
            return [types.TextContent(type="text", text=json.dumps(session, indent=2))]
        if session["type"] == "kaspa":
            wallet = session["wallet"]
            info = {
                "ok": True,
                "address": session["address"],
                "limits": getattr(wallet, "session_limits", {}),
                "daily_spent": getattr(wallet, "session_daily_spent", 0.0),
                "expires_at": getattr(wallet, "session_expires_at", None),
            }
            return [types.TextContent(type="text", text=json.dumps(info, indent=2))]
        else:
            secrets = session["secrets"]
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "ok": True,
                            "ss58_address": secrets.get("ss58_address"),
                            "limits": secrets.get("limits"),
                            "daily_spent": secrets.get("daily_spent"),
                        },
                        indent=2,
                    ),
                )
            ]

    elif name == "vida_balance":
        asset = (arguments or {}).get("asset", "kaspa")
        session = _load_session()
        if not session.get("ok"):
            return [types.TextContent(type="text", text=json.dumps(session, indent=2))]

        if asset == "kaspa" and session["type"] == "kaspa":
            try:
                from vida.transactions import VidaTransactor

                tx = VidaTransactor(session["wallet"])
                import asyncio

                balance = asyncio.run(tx.get_balance())
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {"ok": True, "asset": "KAS", "balance": balance, "address": session["address"]},
                            indent=2,
                        ),
                    )
                ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"ok": False, "error": str(e)}, indent=2),
                    )
                ]
        elif asset == "tao" and session["type"] == "tao":
            # Read-only balance check via public RPC
            try:
                from substrateinterface import SubstrateInterface

                sub = SubstrateInterface(url=os.environ.get(
                    "VIDA_FINNEY_RPC",
                    "wss://entrypoint-finney.opentensor.ai:443"
                ))
                addr = session["ss58_address"]
                result = sub.query("System", "Account", [addr])
                free = int(result.value["data"]["free"]) / 1e9
                sub.close()
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {"ok": True, "asset": "TAO", "balance": free, "address": addr},
                            indent=2,
                        ),
                    )
                ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"ok": False, "error": str(e)}, indent=2),
                    )
                ]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {"ok": False, "error": f"session type {session['type']} doesn't match asset {asset}"},
                        indent=2,
                    ),
                )
            ]

    elif name == "vida_send":
        args = arguments or {}
        to_address = args.get("to_address", "")
        amount_kas = float(args.get("amount_kas", 0))
        asset = args.get("asset", "kaspa")

        if not to_address or amount_kas <= 0:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"ok": False, "error": "to_address and amount_kas required"}, indent=2),
                )
            ]

        session = _load_session()
        if not session.get("ok"):
            return [types.TextContent(type="text", text=json.dumps(session, indent=2))]

        if asset == "kaspa" and session["type"] == "kaspa":
            try:
                from vida.transactions import VidaTransactor

                tx = VidaTransactor(session["wallet"])
                import asyncio

                result = asyncio.run(tx.send(to_address, amount_kas, confirm=True))
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "ok": result.success,
                                "txid": result.txid,
                                "amount_kas": result.amount_kas,
                                "to_address": result.to_address,
                                "fee_kas": result.fee_kas,
                                "error": result.error,
                                "explorer_url": result.explorer_url,
                            },
                            indent=2,
                        ),
                    )
                ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"ok": False, "error": str(e)}, indent=2),
                    )
                ]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {"ok": False, "error": f"send not supported for {asset} via this session type"},
                        indent=2,
                    ),
                )
            ]

    elif name == "vida_covenant_status":
        try:
            from vida.plugins.covenant.tools import covenant_describe

            result = covenant_describe()
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"ok": False, "error": f"covenant module not available: {e}"}, indent=2),
                )
            ]

    elif name == "vida_covenant_plan_pot":
        args = arguments or {}
        try:
            from vida.plugins.covenant.tools import covenant_plan_with_fees

            result = covenant_plan_with_fees(
                max_kas_per_tx=float(args.get("max_kas_per_tx", 0)),
                max_kas_per_day=float(args.get("max_kas_per_day", 0)),
                allowed_destinations=args.get("allowed_destinations"),
                network=args.get("network", "mainnet"),
            )
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"ok": False, "error": str(e)}, indent=2),
                )
            ]

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