"""
Agent pot spend policy — software enforcement (pre-broadcast).

Enforces max_tx + destination allowlist from a pot policy template
before any live spend helper runs. Not on-chain hard caps.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from .agent_pot import SOMPI_PER_KAS
from .agent_pot_script import verify_policy_hash


def check_spend_allowed(
    *,
    policy: dict[str, Any],
    amount_sompi: int,
    destination: str,
    owner_address: Optional[str] = None,
) -> dict[str, Any]:
    """
    Soft-hard check: reject if amount > max_tx or dest not allowlisted.

    Owner address is always allowed (return-to-owner / burn path).
    """
    if amount_sompi <= 0:
        return {"ok": False, "error": "amount_sompi must be positive", "enforcement": "soft_policy"}

    dest = (destination or "").strip()
    if not dest:
        return {"ok": False, "error": "destination required", "enforcement": "soft_policy"}

    owner = (owner_address or policy.get("owner_address") or "").strip()
    if owner and dest == owner:
        return {
            "ok": True,
            "allowed": True,
            "rule": "owner_return",
            "enforcement": "soft_policy",
            "on_chain_hard_cap": False,
            "amount_sompi": amount_sompi,
            "destination": dest,
        }

    max_tx = int(policy.get("max_tx_sompi") or 0)
    if max_tx > 0 and amount_sompi > max_tx:
        return {
            "ok": False,
            "error": f"amount {amount_sompi} exceeds max_tx_sompi {max_tx}",
            "enforcement": "soft_policy",
            "rule": "max_tx",
            "on_chain_hard_cap": False,
        }

    dests = list(policy.get("allowed_destinations") or [])
    require = bool(policy.get("require_dest_allowlist"))
    if require or dests:
        if dest not in dests:
            return {
                "ok": False,
                "error": f"destination not on allowlist ({len(dests)} entries)",
                "enforcement": "soft_policy",
                "rule": "dest_allowlist",
                "on_chain_hard_cap": False,
                "destination": dest,
            }

    return {
        "ok": True,
        "allowed": True,
        "rule": "max_tx_and_dest",
        "enforcement": "soft_policy",
        "on_chain_hard_cap": False,
        "amount_sompi": amount_sompi,
        "destination": dest,
        "max_tx_sompi": max_tx,
    }


def check_spend_kas(
    *,
    policy: dict[str, Any],
    amount_kas: float,
    destination: str,
    owner_address: Optional[str] = None,
) -> dict[str, Any]:
    sompi = int(round(float(amount_kas) * SOMPI_PER_KAS))
    return check_spend_allowed(
        policy=policy,
        amount_sompi=sompi,
        destination=destination,
        owner_address=owner_address,
    )


def pot_record_path(wallet_id: str, base: Optional[Path] = None) -> Path:
    root = base or Path.home() / ".vida" / "covenant_pots"
    root.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in wallet_id)[:64]
    return root / f"{safe}.json"


def save_pot_record(
    wallet_id: str,
    record: dict[str, Any],
    *,
    base: Optional[Path] = None,
) -> dict[str, Any]:
    """Persist pot funding metadata (policy + txids). No private keys."""
    path = pot_record_path(wallet_id, base=base)
    template = record.get("template") or record.get("policy_template")
    if template and not verify_policy_hash(template) and template.get("ok"):
        return {"ok": False, "error": "template policy_hash mismatch"}
    now = time.time()
    data = {
        "wallet_id": wallet_id,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "network": record.get("network") or "testnet-10",
        "covenant_id": record.get("covenant_id"),
        "fund_txid": record.get("txid") or record.get("fund_txid"),
        "pot_sompi": record.get("pot_sompi"),
        "address": record.get("address"),
        "template": template,
        "policy": (template or {}).get("policy") or record.get("policy"),
        "policy_hash": (template or {}).get("policy_hash") or record.get("policy_hash"),
        "hard_rules_attached": record.get("hard_rules_attached"),
        "subscription_interval_hours": record.get("subscription_interval_hours", 0),
        "auto_renew": record.get("auto_renew", False),
        "last_refill_at": record.get("last_refill_at", now),
        "next_refill_at": record.get("next_refill_at", 0),
        "note": "software pot record — not a private key store",
    }
    path.write_text(json.dumps(data, indent=2) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return {"ok": True, "path": str(path), "record": data}


def check_subscription_status(record: dict[str, Any]) -> dict[str, Any]:
    """Check if a pot is due for refill based on subscription interval.

    Returns:
      due: True if refill is due
      next_refill_at: timestamp of next refill
      auto_renew: whether the pot auto-renews
    """
    interval = record.get("subscription_interval_hours", 0) or 0
    last_refill = record.get("last_refill_at", 0) or 0
    auto_renew = record.get("auto_renew", False)
    now = time.time()

    if interval <= 0:
        return {"due": False, "auto_renew": False, "reason": "one_time"}

    next_refill = last_refill + interval * 3600
    due = now >= next_refill

    return {
        "due": due,
        "next_refill_at": next_refill,
        "auto_renew": auto_renew,
        "reason": "subscription_due" if due else "subscription_pending",
        "hours_until_refill": round(max(0, next_refill - now) / 3600, 1) if not due else 0,
    }


def load_pot_record(wallet_id: str, *, base: Optional[Path] = None) -> dict[str, Any]:
    path = pot_record_path(wallet_id, base=base)
    if not path.is_file():
        return {"ok": False, "error": f"no pot record for {wallet_id}", "path": str(path)}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"read pot record failed: {e}", "path": str(path)}
    return {"ok": True, "path": str(path), "record": data}
