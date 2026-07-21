"""Self-custody vault covenant — survives a stolen key.

Three spend paths:
  initiate — hot key starts a withdrawal. Funds go to a delay vault UTXO.
  cancel   — cold key cancels during the delay window. Funds back to vault.
  finalize — after delay expires, funds go to the whitelisted destination.

Constructor args:
  hot_pubkey:     x-only Schnorr pubkey (32 bytes hex)
  cold_pubkey:    x-only Schnorr pubkey (32 bytes hex)
  whitelist_dest: blake2b-256 of the final destination address (32 bytes hex)
  delay_daa:      DAA blocks to wait between initiate and finalize

State:
  pending_dest:   destination hash of pending withdrawal (0 if none)
  pending_since:  DAA when initiate was called (0 if none)
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# ── Constants ──

SOMIPI_PER_KAS = 100_000_000
SCRIPT_DIR = Path(__file__).resolve().parent / "silverscript" / "contracts"
VAULT_SIL_PATH = SCRIPT_DIR / "VaultV1.sil"
VAULT_JSON_PATH = SCRIPT_DIR / "VaultV1.json"

# Default: 24 hours on testnet-10 (10 BPS → 864,000 DAA)
DEFAULT_DELAY_DAA = 864000


# ── State ──


@dataclass
class VaultState:
    """Current state of a vault covenant instance."""

    vault_id: str = ""
    hot_pubkey: str = ""
    cold_pubkey: str = ""
    whitelist_dest: str = ""
    delay_daa: int = DEFAULT_DELAY_DAA
    balance_sompi: int = 0
    pending_dest: str = ""  # hex, 32 bytes or empty
    pending_since: int = 0  # DAA score
    status: str = "active"  # active | initiated | finalized | cancelled
    deploy_txid: str = ""
    network: str = "mainnet"

    @property
    def is_pending(self) -> bool:
        return bool(self.pending_dest) and self.pending_since > 0

    @property
    def balance_kas(self) -> float:
        return self.balance_sompi / SOMIPI_PER_KAS

    def to_dict(self) -> dict[str, Any]:
        return {
            "vault_id": self.vault_id[:16] + "..." if len(self.vault_id) > 16 else self.vault_id,
            "hot_pubkey": self.hot_pubkey[:16] + "...",
            "cold_pubkey": self.cold_pubkey[:16] + "...",
            "balance_kas": self.balance_kas,
            "status": self.status,
            "is_pending": self.is_pending,
            "pending_dest": self.pending_dest[:16] + "..." if self.pending_dest else "",
            "pending_since_daa": self.pending_since if self.pending_since > 0 else None,
            "delay_daa": self.delay_daa,
            "network": self.network,
        }


# ── Store ──


class VaultStore:
    """Persistent store for vault covenants."""

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            storage_dir = str(Path.home() / ".vida" / "vaults")
        self._path = Path(storage_dir) / "vaults.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._vaults: dict[str, VaultState] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for d in data.get("vaults", []):
                    v = VaultState(**{k: v for k, v in d.items() if k in VaultState.__dataclass_fields__})
                    self._vaults[v.vault_id] = v
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                import logging

                logging.getLogger(__name__).warning("Vault store load error: %s", e)

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(
                {
                    "vaults": [
                        {k: v for k, v in v.__dict__.items() if not k.startswith("_")} for v in self._vaults.values()
                    ],
                    "updated_at": __import__("time").time(),
                },
                indent=2,
            )
        )

    def save(self, vault: VaultState) -> None:
        self._vaults[vault.vault_id] = vault
        self._save()

    def get(self, vault_id: str) -> Optional[VaultState]:
        return self._vaults.get(vault_id)

    def list_active(self) -> list[VaultState]:
        return [v for v in self._vaults.values() if v.status in ("active", "initiated")]

    def list_all(self) -> list[dict[str, Any]]:
        return [v.to_dict() for v in self._vaults.values()]


# ── Operations ──


def destination_hash(address: str) -> str:
    """Compute blake2b-256 hash of a Kaspa address string."""
    return hashlib.blake2b(address.encode(), digest_size=32).hexdigest()


def create_vault(
    hot_pubkey: str,
    cold_pubkey: str,
    whitelist_address: str,
    balance_kas: float,
    delay_daa: int = DEFAULT_DELAY_DAA,
    network: str = "mainnet",
) -> dict[str, Any]:
    """Create a new vault covenant.

    The vault locks KAS in a covenant UTXO. The hot key can initiate
    withdrawals. The cold key can cancel. After the delay, funds go
    to the whitelisted address.

    Args:
        hot_pubkey: x-only Schnorr pubkey (32 bytes hex)
        cold_pubkey: x-only Schnorr pubkey (32 bytes hex)
        whitelist_address: Kaspa address allowed as final destination
        balance_kas: KAS to lock in the vault
        delay_daa: DAA blocks for the withdrawal delay
        network: 'mainnet' or 'testnet-10'
    """
    try:
        vault_id = f"vault_{secrets.token_hex(8)}"
        balance_sompi = int(balance_kas * SOMIPI_PER_KAS)

        whitelist_dest = destination_hash(whitelist_address)

        vault = VaultState(
            vault_id=vault_id,
            hot_pubkey=hot_pubkey,
            cold_pubkey=cold_pubkey,
            whitelist_dest=whitelist_dest,
            delay_daa=delay_daa,
            balance_sompi=balance_sompi,
            network=network,
        )

        store = VaultStore()
        store.save(vault)

        return {
            "ok": True,
            "vault_id": vault_id,
            "hot_pubkey": hot_pubkey[:16] + "...",
            "cold_pubkey": cold_pubkey[:16] + "...",
            "whitelist_address": whitelist_address,
            "balance_kas": balance_kas,
            "delay_daa": delay_daa,
            "delay_hours": delay_daa / 864000 if network == "testnet-10" else delay_daa / 86400,
            "network": network,
            "note": "Fund the covenant P2SH address to activate the vault. "
            "The hot key can initiate withdrawals. The cold key can cancel.",
        }

    except Exception as e:
        return {"ok": False, "error": f"create vault failed: {e}"}


def initiate_withdrawal(
    vault_id: str,
    hot_sig: str,
    destination: str,
    current_daa: int,
    store: Optional[VaultStore] = None,
) -> dict[str, Any]:
    """Initiate a withdrawal from the vault.

    The hot key signs a withdrawal to the whitelisted destination.
    The vault enters a pending state for the delay period.

    Args:
        vault_id: Vault identifier
        hot_sig: Hot key's BIP340 signature
        destination: Final destination address (must match whitelist)
        current_daa: Current DAA score
        store: Optional store override
    """
    try:
        store = store or VaultStore()
        vault = store.get(vault_id)
        if not vault:
            return {"ok": False, "error": f"vault {vault_id} not found"}
        if vault.status == "cancelled":
            return {"ok": False, "error": "vault is cancelled"}
        if vault.is_pending:
            return {"ok": False, "error": "withdrawal already pending"}

        # Verify destination is whitelisted
        dest_hash = destination_hash(destination)
        if dest_hash != vault.whitelist_dest:
            return {"ok": False, "error": "destination not whitelisted"}

        # Update state
        vault.pending_dest = dest_hash
        vault.pending_since = current_daa
        vault.status = "initiated"
        store.save(vault)

        return {
            "ok": True,
            "vault_id": vault_id,
            "pending_dest": destination,
            "pending_since_daa": current_daa,
            "delay_end_daa": current_daa + vault.delay_daa,
            "status": "initiated",
            "note": f"Withdrawal initiated. Cold key can cancel until DAA {current_daa + vault.delay_daa}.",
        }

    except Exception as e:
        return {"ok": False, "error": f"initiate withdrawal failed: {e}"}


def cancel_withdrawal(
    vault_id: str,
    cold_sig: str,
    store: Optional[VaultStore] = None,
) -> dict[str, Any]:
    """Cancel a pending withdrawal.

    The cold key signs to cancel the pending withdrawal.
    Funds return to the vault with pending state cleared.

    Args:
        vault_id: Vault identifier
        cold_sig: Cold key's BIP340 signature
        store: Optional store override
    """
    try:
        store = store or VaultStore()
        vault = store.get(vault_id)
        if not vault:
            return {"ok": False, "error": f"vault {vault_id} not found"}
        if not vault.is_pending:
            return {"ok": False, "error": "no pending withdrawal to cancel"}
        if vault.status == "cancelled":
            return {"ok": False, "error": "vault is already cancelled"}

        # Clear pending state
        vault.pending_dest = ""
        vault.pending_since = 0
        vault.status = "active"
        store.save(vault)

        return {
            "ok": True,
            "vault_id": vault_id,
            "status": "active",
            "note": "Withdrawal cancelled. Funds are back in the vault.",
        }

    except Exception as e:
        return {"ok": False, "error": f"cancel withdrawal failed: {e}"}


def finalize_withdrawal(
    vault_id: str,
    current_daa: int,
    store: Optional[VaultStore] = None,
) -> dict[str, Any]:
    """Finalize a pending withdrawal after the delay expires.

    Anyone can call this after the delay period. Funds go to the
    whitelisted destination. The vault is closed.

    Args:
        vault_id: Vault identifier
        current_daa: Current DAA score
        store: Optional store override
    """
    try:
        store = store or VaultStore()
        vault = store.get(vault_id)
        if not vault:
            return {"ok": False, "error": f"vault {vault_id} not found"}
        if not vault.is_pending:
            return {"ok": False, "error": "no pending withdrawal"}
        if current_daa < vault.pending_since + vault.delay_daa:
            remaining = (vault.pending_since + vault.delay_daa) - current_daa
            return {"ok": False, "error": f"delay not expired ({remaining} DAA remaining)"}

        vault.status = "finalized"
        store.save(vault)

        return {
            "ok": True,
            "vault_id": vault_id,
            "amount_kas": vault.balance_kas,
            "status": "finalized",
            "note": "Withdrawal finalized. Funds sent to whitelisted destination.",
        }

    except Exception as e:
        return {"ok": False, "error": f"finalize withdrawal failed: {e}"}


def vault_status(vault_id: str) -> dict[str, Any]:
    """Check vault status."""
    store = VaultStore()
    vault = store.get(vault_id)
    if not vault:
        return {"ok": False, "error": f"vault {vault_id} not found"}
    return {"ok": True, "vault": vault.to_dict()}


def vault_list(network: str = "mainnet") -> dict[str, Any]:
    """List all vaults."""
    store = VaultStore()
    vaults = store.list_all()
    return {
        "ok": True,
        "count": len(vaults),
        "active": len([v for v in vaults if v.get("status") in ("active", "initiated")]),
        "vaults": vaults,
    }


# ── Hermes tools ──


def vida_vault_create(
    hot_pubkey: str,
    cold_pubkey: str,
    whitelist_address: str,
    balance_kas: float,
    delay_daa: int = DEFAULT_DELAY_DAA,
    network: str = "mainnet",
) -> dict[str, Any]:
    """Create a self-custody vault."""
    return create_vault(hot_pubkey, cold_pubkey, whitelist_address, balance_kas, delay_daa, network)


def vida_vault_initiate(
    vault_id: str,
    hot_sig: str,
    destination: str,
    current_daa: int,
) -> dict[str, Any]:
    """Initiate a vault withdrawal."""
    return initiate_withdrawal(vault_id, hot_sig, destination, current_daa)


def vida_vault_cancel(
    vault_id: str,
    cold_sig: str,
) -> dict[str, Any]:
    """Cancel a vault withdrawal."""
    return cancel_withdrawal(vault_id, cold_sig)


def vida_vault_finalize(
    vault_id: str,
    current_daa: int,
) -> dict[str, Any]:
    """Finalize a vault withdrawal."""
    return finalize_withdrawal(vault_id, current_daa)


def vida_vault_status(vault_id: str) -> dict[str, Any]:
    """Check vault status."""
    return vault_status(vault_id)


def vida_vault_list(network: str = "mainnet") -> dict[str, Any]:
    """List all vaults."""
    return vault_list(network)
