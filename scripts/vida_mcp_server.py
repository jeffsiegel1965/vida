"""Vida Wallet MCP Server — exposes wallet + oracle price feeds as MCP tools.

Conforms to the same pattern as the Vida Oracle MCP server (fastmcp, {status, ...} response format).
Informs from the Oracle MCP: wallet tools can query live oracle price data.

Usage:
    export VIDA_WALLET=~/.vida/wallet.json
    export VIDA_ORACLE_URL=http://127.0.0.1:8765
    python scripts/vida_mcp_server.py

Tools:
- Wallet: vida_status, vida_balance, vida_send, vida_covenant_plan_pot
- Oracle: get_price, list_oracle_pairs, get_oracle_node_status
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Any

from fastmcp import FastMCP

# Discovery — pointers to services + receptors for sensing agents
from vida.discovery import get_discovery

# ── Path Resolution ──
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Configuration ──
VIDA_WALLET = os.environ.get("VIDA_WALLET", "")
VIDA_SESSION = os.environ.get("VIDA_SESSION", "")
ORACLE_HTTP_URL = os.environ.get("VIDA_ORACLE_URL", "http://127.0.0.1:8765").rstrip("/")
MCP_API_KEY = os.environ.get("VIDA_WALLET_MCP_API_KEY", "")

# Oracle availability check
_ORACLE_AVAILABLE = False
try:
    from vida_oracle.config import ORACLE_PAIRS
    _ORACLE_AVAILABLE = True
except ImportError:
    ORACLE_PAIRS = []

# Wallet availability check
_WALLET_AVAILABLE = False
if VIDA_WALLET and Path(VIDA_WALLET).is_file():
    _WALLET_AVAILABLE = True

mcp = FastMCP("vida-wallet")


# ── Auth ──
def _require_api_key(args: dict) -> bool:
    if not MCP_API_KEY:
        return True
    return args.get("api_key", "") == MCP_API_KEY


# ── Oracle HTTP helpers (same pattern as Oracle MCP) ──
def quote_path(value: str) -> str:
    return quote(value, safe="")


def _oracle_get(path: str, timeout: float = 15.0) -> dict:
    request = Request(f"{ORACLE_HTTP_URL}{path}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _oracle_error_result(pair: str, error: Exception) -> dict:
    if isinstance(error, HTTPError) and error.code == 404:
        return {"status": "not_found", "pair": pair, "error": "No attestation available"}
    if isinstance(error, (URLError, TimeoutError)):
        return {"status": "unavailable", "pair": pair, "error": str(error)}
    return {"status": "error", "pair": pair, "error": str(error)}


# ═══════════════════════════════════════════════════════════════════
# Wallet Tools
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def vida_status() -> dict:
    """Check Wallet system health and Oracle availability."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "systems": {
            "wallet": {
                "available": _WALLET_AVAILABLE,
                "wallet_path": VIDA_WALLET if _WALLET_AVAILABLE else None,
                "session_set": bool(VIDA_SESSION),
            },
            "oracle": {
                "available": _ORACLE_AVAILABLE,
                "url": ORACLE_HTTP_URL,
                "pairs": ORACLE_PAIRS if _ORACLE_AVAILABLE else [],
            },
        },
    }


@mcp.tool()
def discovery_status() -> dict:
    """Show current discovery state — policy, receptors, connected services, approvals."""
    try:
        d = get_discovery()
        return d.status()
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def discovery_scan() -> dict:
    """Force a full discovery scan now. Returns services found."""
    try:
        d = get_discovery()
        d.scan()
        svcs = d.list_services()
        pending = d.pending_approvals()
        msg = f"Scan complete — {len(svcs)} services"
        if pending:
            msg += f", {len(pending)} pending approval"
        return {"status": "ok", "message": msg, "services": svcs, "pending_approvals": pending}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def discovery_services(filter_type: str = "") -> list:
    """List all discovered services, optionally filtered by type (oracle, mcp, agent, marketplace, custom)."""
    return get_discovery().list_services(filter_type)


@mcp.tool()
def discovery_pending() -> list:
    """Show services pending owner approval before the agent can connect."""
    return get_discovery().pending_approvals()


@mcp.tool()
def discovery_report(limit: int = 50) -> list:
    """Show the discovery audit log — scans, approvals, connections, blocks."""
    return get_discovery().report(limit)


@mcp.tool()
def discovery_set_policy(policy: str) -> dict:
    """Set discovery policy: manual (all need approval), balanced (trusted auto), permissive (everything auto)."""
    d = get_discovery()
    try:
        from vida.discovery import Policy
        p = Policy(policy.lower())
        d.policy = p
        return {"status": "ok", "policy": p.value,
                "message": f"Policy set to '{p.value}' — {'all connections need approval' if p.value == 'manual' else 'trusted services auto-connect' if p.value == 'balanced' else 'everything auto-connects'}"}
    except ValueError:
        return {"status": "error", "error": f"Invalid policy '{policy}'. Options: manual, balanced, permissive"}


@mcp.tool()
def discovery_set_receptor(name: str, enabled: bool) -> dict:
    """Enable or disable a receptor (lan, network, agent)."""
    ok = get_discovery().set_receptor(name, enabled)
    if ok:
        return {"status": "ok", "message": f"Receptor '{name}' {'enabled' if enabled else 'disabled'}"}
    return {"status": "error", "error": f"Unknown receptor '{name}'. Options: lan, network, agent"}


@mcp.tool()
def discovery_approve(service_name: str) -> dict:
    """Approve a service — agent may connect to it."""
    ok = get_discovery().approve(service_name)
    if ok:
        return {"status": "ok", "message": f"Service '{service_name}' approved"}
    return {"status": "error", "error": f"Service '{service_name}' not found"}


@mcp.tool()
def discovery_block(service_name: str) -> dict:
    """Block a service — agent may never connect to it."""
    ok = get_discovery().block(service_name)
    if ok:
        return {"status": "ok", "message": f"Service '{service_name}' blocked"}
    return {"status": "error", "error": f"Service '{service_name}' not found"}


@mcp.tool()
def discovery_set_trust(service_name: str, trust: str) -> dict:
    """Set trust level for a service: trusted, known, unknown, blocked."""
    ok = get_discovery().set_trust(service_name, trust)
    if ok:
        return {"status": "ok", "message": f"Service '{service_name}' trust set to '{trust}'"}
    return {"status": "error", "error": f"Invalid service or trust level. Trust: trusted, known, unknown, blocked"}


@mcp.tool()
def discovery_check_connection(service_name: str) -> dict:
    """Check if the agent is allowed to connect to a service."""
    from vida.discovery import get_discovery
    allowed, reason = get_discovery().may_connect(service_name)
    svc = None
    for s in get_discovery().list_services():
        if s["name"] == service_name:
            svc = s
            break
    return {"service": service_name, "allowed": allowed, "reason": reason, "service_info": svc}


@mcp.tool()
def discovery_connect(service_name: str) -> dict:
    """Agent requests to connect to a service. May be blocked by policy."""
    allowed, reason = get_discovery().connect(service_name)
    if allowed:
        return {"status": "ok", "message": f"Connected to '{service_name}'", "reason": reason}
    return {"status": "error", "error": f"Connection blocked: {reason}", "policy_hint": "Set policy to permissive or approve the service"}


@mcp.tool()
def discovery_add_pointer(name: str, url: str, label: str = "") -> dict:
    """Add a custom service pointer (added as trusted)."""
    get_discovery().set_pointer(name, url, label)
    return {"status": "ok", "message": f"Pointer '{name}' added (trusted)"}


@mcp.tool()
def discovery_remove_pointer(name: str) -> dict:
    """Remove a service pointer by name."""
    ok = get_discovery().remove_pointer(name)
    if ok:
        return {"status": "ok", "message": f"Pointer '{name}' removed"}
    return {"status": "error", "error": f"Pointer '{name}' not found"}


@mcp.tool()
def vida_balance(asset: str = "kaspa") -> dict:
    """Check wallet balance (Kaspa or TAO).

    Args:
        asset: Asset to check (kaspa, tao)
    """
    if not _require_api_key({"api_key": ""}):
        if MCP_API_KEY:
            return {"status": "error", "error": "api_key parameter required"}
    # Fallback — wallet must be loaded by agent
    return {
        "status": "ok",
        "asset": asset,
        "note": "Pass wallet path via VIDA_WALLET env var and session via VIDA_SESSION",
        "hint": "Use the agent loop or send via the MCP companion server",
    }


@mcp.tool()
def vida_send(amount: float, destination: str, api_key: str = "") -> dict:
    """Send KAS (requires session with caps).

    Args:
        amount: Amount in KAS
        destination: Kaspa address
        api_key: MCP API key (if configured)
    """
    if not _require_api_key({"api_key": api_key}):
        return {"status": "error", "error": "Unauthorized: invalid or missing API key"}
    if not _WALLET_AVAILABLE:
        return {"status": "error", "error": "Wallet not available. Set VIDA_WALLET env var."}
    try:
        from vida.secure_wallet import SecureVida
        wallet = SecureVida(VIDA_WALLET)
        if VIDA_SESSION:
            wallet.load_session(Path(VIDA_SESSION))
        result = wallet.send(destination, int(amount * 1e8))
        return {"status": "ok", "result": str(result), "amount": amount, "destination": destination}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def vida_covenant_plan_pot(
    max_kas_per_tx: float,
    max_kas_per_day: float,
    allowed_destinations: list[str] | None = None,
    api_key: str = "",
) -> dict:
    """Plan an agent pot with spending limits.

    Args:
        max_kas_per_tx: Max KAS per transaction
        max_kas_per_day: Max KAS per day
        allowed_destinations: Allowed destination addresses
        api_key: MCP API key (if configured)
    """
    if not _require_api_key({"api_key": api_key}):
        return {"status": "error", "error": "Unauthorized: invalid or missing API key"}
    try:
        from vida.plugins.covenant.tools import covenant_plan_pot
        return covenant_plan_pot(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations,
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# Oracle Tools (inform from Oracle MCP — same pattern as Oracle MCP)
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def get_price(pair: str) -> dict:
    """Get current oracle price for a trading pair.

    Wires through to the Vida Oracle HTTP API — same data as the Oracle MCP server.

    Args:
        pair: Trading pair in format BASE/QUOTE (e.g., "KAS/USD", "BTC/USD")
    """
    if not _ORACLE_AVAILABLE:
        return {"status": "unavailable", "pair": pair, "error": "Oracle system not available"}
    try:
        base, quote = (part.strip().upper() for part in pair.split("/", 1))
        if not base or not quote:
            raise ValueError("pair must be BASE/QUOTE")
        payload = _oracle_get(f"/attest/{quote_path(base)}/{quote_path(quote)}")
        attestations = payload.get("attestations")
        if attestations is None:
            if "price" in payload or "price_float" in payload:
                return {
                    "status": "ok",
                    "pair": payload.get("pair", f"{base}/{quote}"),
                    "price": payload.get("price_float", payload.get("price")),
                    "attestation_time": payload.get("timestamp"),
                    "grade": payload.get("grade", "D"),
                    "signatures": len(payload.get("signatures", [])),
                    "stale": payload.get("stale", False),
                    "age_seconds": payload.get("age_seconds"),
                    "latency_ms": payload.get("latency_ms"),
                    "nodes": payload.get("nodes", []),
                }
            return {"status": "not_found", "pair": pair, "error": "No attestation available"}
        if not attestations:
            return {"status": "not_found", "pair": pair, "error": "No attestation available"}
        price_data = attestations[-1]
        return {
            "status": "ok",
            "pair": payload.get("pair", f"{base}/{quote}"),
            "price": price_data.get("price_float", price_data.get("price")),
            "attestation_time": price_data.get("timestamp"),
            "grade": price_data.get("grade", "D"),
            "signatures": 1 if price_data.get("signature") else 0,
            "stale": payload.get("stale", False),
            "age_seconds": payload.get("age_seconds"),
        }
    except Exception as e:
        return _oracle_error_result(pair, e)


@mcp.tool()
def list_oracle_pairs() -> dict:
    """List all trading pairs supported by Vida Oracle."""
    if not _ORACLE_AVAILABLE:
        return {"status": "unavailable", "pairs": [], "error": "Oracle system not available"}
    return {"status": "ok", "pairs": ORACLE_PAIRS, "count": len(ORACLE_PAIRS)}


@mcp.tool()
def get_oracle_node_status() -> dict:
    """Check Vida Oracle network health and node status."""
    if not _ORACLE_AVAILABLE:
        return {"status": "unavailable", "nodes": [], "error": "Oracle system not available"}
    try:
        health = _oracle_get("/health")
        return {
            "status": "ok" if health.get("status") == "running" else "degraded",
            "total_nodes": 1,
            "healthy_nodes": 1 if health.get("status") == "running" else 0,
            "nodes": [{
                "id": "oracle-http",
                "location": ORACLE_HTTP_URL,
                "healthy": health.get("status") == "running",
                "last_attestation": health.get("timestamp"),
            }],
            "pairs": health.get("pairs", 0),
            "errors_5m": health.get("errors_5m", 0),
            "pair_failures": health.get("pair_failures", []),
        }
    except Exception as e:
        return _oracle_error_result("oracle", e)


# ═══════════════════════════════════════════════════════════════════
# Resources
# ═══════════════════════════════════════════════════════════════════


@mcp.resource("vida-wallet://status")
def get_wallet_status() -> str:
    """Wallet system status."""
    return json.dumps(vida_status(), indent=2)


@mcp.resource("vida-wallet://pairs")
def get_wallet_pairs() -> str:
    """Oracle pairs available via wallet."""
    return json.dumps(list_oracle_pairs(), indent=2)


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Rate limiting state for send tool
    _send_calls: list[float] = []
    _original_send = vida_send

    @mcp.tool()
    def vida_send(amount: float, destination: str, api_key: str = "") -> dict:
        """Send KAS (requires session with caps). Rate limited to 3 calls per minute."""
        import time
        now = time.time()
        cutoff = now - 60
        # Prune old entries
        while _send_calls and _send_calls[0] < cutoff:
            _send_calls.pop(0)
        if len(_send_calls) >= 3:
            return {"status": "error", "error": "Rate limited — max 3 send calls per minute"}
        _send_calls.append(now)
        return _original_send(amount, destination, api_key)

    # Update the tool's name in the registry
    mcp._tool_manager._tools["vida_send"] = vida_send

    mcp.run()