"""Unified TAO paths via env — one store, one session, optional wallet id."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_ACCOUNTS = _ROOT / "data" / "tao_accounts"
_DEFAULT_SESSION = _ROOT / "data" / "tao_agent_session.json"
_E2E_ACCOUNTS = _ROOT / "data" / "tao_live_e2e" / "accounts"
_E2E_SESSION = _ROOT / "data" / "tao_live_e2e" / "agent_session.json"

# Scope → allowed_actions
SCOPE_ACTIONS = {
    "ALL": ["delegate", "undelegate", "transfer", "optimize", "status", "balance"],
    "STAKE_ONLY": ["delegate", "undelegate", "optimize", "status", "balance"],
    "TRANSFER_ONLY": ["transfer", "status", "balance"],
}


def resolve_store_dir(store_dir: Optional[str] = None, wallet_id: Optional[str] = None) -> str:
    if store_dir:
        return str(store_dir)
    env = os.environ.get("VIDA_TAO_STORE") or os.environ.get("VIDA_TAO_STORE_DIR")
    if env:
        return env
    wid = wallet_id or os.environ.get("VIDA_TAO_WALLET") or ""
    # Prefer e2e store if that wallet exists there
    if wid:
        cand = _E2E_ACCOUNTS / wid / "tao_account.json"
        if cand.is_file():
            return str(_E2E_ACCOUNTS)
    if _E2E_ACCOUNTS.is_dir() and any(_E2E_ACCOUNTS.iterdir()):
        # only if default empty and e2e has content
        if not _DEFAULT_ACCOUNTS.is_dir() or not any(_DEFAULT_ACCOUNTS.iterdir()):
            return str(_E2E_ACCOUNTS)
    return str(_DEFAULT_ACCOUNTS)


def resolve_session_path(session_path: Optional[str] = None) -> Optional[str]:
    if session_path:
        return session_path
    env = os.environ.get("VIDA_TAO_SESSION")
    if env:
        return env
    # Prefer default agent session only — do not auto-pick live e2e leftovers
    # (stale Finney sessions are an ops footgun). E2E must set VIDA_TAO_SESSION.
    if _DEFAULT_SESSION.is_file():
        return str(_DEFAULT_SESSION)
    return None


def resolve_wallet_id(wallet_id: Optional[str] = None) -> str:
    return (wallet_id or os.environ.get("VIDA_TAO_WALLET") or "").strip()


def actions_for_scope(scope: str) -> list[str]:
    s = (scope or "ALL").upper().replace("-", "_")
    if s not in SCOPE_ACTIONS:
        raise ValueError(f"unknown scope {scope!r}; use ALL|STAKE_ONLY|TRANSFER_ONLY")
    return list(SCOPE_ACTIONS[s])
