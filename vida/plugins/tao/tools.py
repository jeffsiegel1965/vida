"""
Hermes-facing helpers for TAO plugin.

Security product rules:
- No mnemonics ever.
- Money actions (stake/transfer/optimize execute) are **session-only**.
  Password unlock is owner scripts only — not Hermes tool kwargs (chat leak surface).
- confirm=True required for state-changing actions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from ..base import VidaPluginContext
from .accounts import TaoAccountStore
from .config import load_tao_config
from .paths import resolve_session_path, resolve_store_dir
from .plugin import TaoPlugin


def _plugin(
    network: Optional[str] = None,
    store_dir: Optional[str] = None,
    wallet_id: Optional[str] = None,
) -> TaoPlugin:
    cfg = load_tao_config(network=network)
    store = TaoAccountStore(resolve_store_dir(store_dir, wallet_id=wallet_id))
    return TaoPlugin(config=cfg, account_store=store)


def _session_path(session_path: Optional[str]) -> Optional[str]:
    return resolve_session_path(session_path)


def _require_session(session_path: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
    sp = _session_path(session_path)
    if not sp:
        return None, {
            "ok": False,
            "error": (
                "Agent money actions require VIDA_TAO_SESSION or session_path "
                "(password is owner-script only — not a Hermes tool argument)"
            ),
        }
    if not Path(sp).is_file():
        return None, {"ok": False, "error": f"session file not found: {sp}"}
    return sp, None


def vida_tao_status(
    wallet_id: str,
    *,
    network: Optional[str] = None,
    store_dir: Optional[str] = None,
    mode: str = "COMMAND",
) -> dict[str, Any]:
    """Hermes tool: read-only TAO status + balance."""
    if not wallet_id or not isinstance(wallet_id, str):
        return {"ok": False, "error": "wallet_id required"}
    plugin = _plugin(network=network, store_dir=store_dir, wallet_id=wallet_id)
    ctx = VidaPluginContext(wallet_id=wallet_id, mode=mode, network=plugin.config.network.value)
    return plugin.status(ctx)


def vida_tao_balance(
    wallet_id: str,
    *,
    network: Optional[str] = None,
    store_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Hermes tool: balance only."""
    if not wallet_id or not isinstance(wallet_id, str):
        return {"ok": False, "error": "wallet_id required"}
    plugin = _plugin(network=network, store_dir=store_dir, wallet_id=wallet_id)
    ctx = VidaPluginContext(wallet_id=wallet_id, mode="COMMAND", network=plugin.config.network.value)
    return plugin.balance(ctx)


def vida_tao_delegate(
    wallet_id: str,
    amount_tao: float,
    netuid: int,
    *,
    hotkey: str = "",
    confirm: bool = False,
    session_path: str | None = None,
    network: Optional[str] = None,
    store_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Delegate TAO via agent session only."""
    sp, err = _require_session(session_path)
    if err:
        return err
    plugin = _plugin(network=network, store_dir=store_dir, wallet_id=wallet_id)
    # Mode/caps come from session file, not tool args (prevents agent raising its own limits)
    ctx = VidaPluginContext(wallet_id=wallet_id, mode="COMMAND", network=plugin.config.network.value)
    return plugin.delegate(
        ctx,
        amount_tao=float(amount_tao),
        netuid=int(netuid),
        hotkey=hotkey or "",
        confirm=confirm,
        password=None,
        session_path=sp,
    )


def vida_tao_undelegate(
    wallet_id: str,
    amount_tao: float,
    netuid: int,
    *,
    hotkey: str = "",
    confirm: bool = False,
    session_path: str | None = None,
    network: Optional[str] = None,
    store_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Undelegate TAO via agent session only."""
    sp, err = _require_session(session_path)
    if err:
        return err
    plugin = _plugin(network=network, store_dir=store_dir, wallet_id=wallet_id)
    ctx = VidaPluginContext(wallet_id=wallet_id, mode="COMMAND", network=plugin.config.network.value)
    return plugin.undelegate(
        ctx,
        amount_tao=float(amount_tao),
        netuid=int(netuid),
        hotkey=hotkey or "",
        confirm=confirm,
        password=None,
        session_path=sp,
    )


def vida_tao_transfer(
    wallet_id: str,
    dest_ss58: str,
    amount_tao: float,
    *,
    confirm: bool = False,
    keep_alive: bool = True,
    session_path: str | None = None,
    network: Optional[str] = None,
    store_dir: Optional[str] = None,
) -> dict[str, Any]:
    """P2P TAO transfer via agent session only."""
    sp, err = _require_session(session_path)
    if err:
        return err
    plugin = _plugin(network=network, store_dir=store_dir, wallet_id=wallet_id)
    ctx = VidaPluginContext(wallet_id=wallet_id, mode="COMMAND", network=plugin.config.network.value)
    return plugin.transfer(
        ctx,
        dest_ss58=dest_ss58,
        amount_tao=float(amount_tao),
        confirm=confirm,
        password=None,
        session_path=sp,
        keep_alive=keep_alive,
    )


def vida_tao_optimize(
    wallet_id: str,
    *,
    netuid: int = 1,
    reserve_tao: float = 0.01,
    min_stake: float = 0.01,
    execute: bool = False,
    confirm: bool = False,
    session_path: str | None = None,
    network: Optional[str] = None,
    store_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Yield plan (default) or execute via session. execute requires confirm + session."""
    plugin = _plugin(network=network, store_dir=store_dir, wallet_id=wallet_id)
    ctx = VidaPluginContext(wallet_id=wallet_id, mode="COMMAND", network=plugin.config.network.value)
    sp = None
    if execute:
        sp, err = _require_session(session_path)
        if err:
            return err
    return plugin.optimize_yield(
        ctx,
        netuid=int(netuid),
        reserve_tao=float(reserve_tao),
        min_stake=float(min_stake),
        execute=bool(execute),
        confirm=confirm,
        password=None,
        session_path=sp,
    )


def vida_tao_session_info(session_path: str | None = None) -> dict[str, Any]:
    """Read-only: whether VIDA_TAO_SESSION exists and is unexpired (no secrets)."""
    import time
    sp = _session_path(session_path)
    if not sp:
        return {"ok": False, "error": "no session path", "active": False}
    path = Path(sp)
    if not path.is_file():
        return {"ok": False, "error": "missing", "active": False, "path": sp}
    try:
        import json
        raw = json.loads(path.read_text())
        exp = float(raw.get("expires_at") or 0)
        return {
            "ok": True,
            "path": sp,
            "active": time.time() < exp,
            "expires_at": exp,
            "limits": raw.get("limits"),
            "version": raw.get("version"),
            "host_bound": bool(raw.get("host_id")),
            "wallet_id": raw.get("wallet_id"),
            "ss58_address": raw.get("ss58_address"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "active": False}


HERMES_TOOLS = {
    "vida_tao_status": {
        "fn": vida_tao_status,
        "description": "Read-only TAO wallet status and free balance",
        "mutating": False,
    },
    "vida_tao_balance": {
        "fn": vida_tao_balance,
        "description": "Read-only TAO free/reserved balance",
        "mutating": False,
    },
    "vida_tao_delegate": {
        "fn": vida_tao_delegate,
        "description": "Stake/delegate TAO (session + confirm=True)",
        "mutating": True,
    },
    "vida_tao_undelegate": {
        "fn": vida_tao_undelegate,
        "description": "Unstake/undelegate TAO (session + confirm=True)",
        "mutating": True,
    },
    "vida_tao_transfer": {
        "fn": vida_tao_transfer,
        "description": "Send TAO to another SS58 (session + confirm=True)",
        "mutating": True,
    },
    "vida_tao_optimize": {
        "fn": vida_tao_optimize,
        "description": "Plan or execute TAO yield rebalance (execute needs session)",
        "mutating": True,
    },
}
