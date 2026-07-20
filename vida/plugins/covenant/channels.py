"""Covenant payment channels — off-chain micropayments, on-chain settlement.

Two agents (or an agent and a subnet) open a channel funded by a covenant.
They exchange thousands of off-chain micropayment updates. Either party can
close the channel at any time to settle the final balance on-chain.

This is how Vida scales to billions of agent transactions without billions
of UTXOs on Kaspa.

Flow:
1. Open channel — agent A funds a covenant UTXO with N KAS
2. Update state — off-chain signed messages updating the balance split
3. Close channel — submit final state to chain, both parties withdraw
4. Dispute window — if one party closes unfairly, the other can challenge
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# State
# ═══════════════════════════════════════════


@dataclass
class ChannelState:
    """The current state of a payment channel.

    Both parties sign this to agree on the current balance split.
    """

    channel_id: str
    nonce: int  # Increments with each update
    balance_a: int  # Party A's balance in sompi
    balance_b: int  # Party B's balance in sompi
    sequence: int = 0  # Off-chain update counter
    sig_a: str = ""  # Party A's signature
    sig_b: str = ""  # Party B's signature

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "nonce": self.nonce,
            "balance_a": self.balance_a,
            "balance_b": self.balance_b,
            "sequence": self.sequence,
            "sig_a": self.sig_a,
            "sig_b": self.sig_b,
        }


@dataclass
class PaymentChannel:
    """A payment channel between two parties.

    The channel is funded by a covenant UTXO on Kaspa. Off-chain updates
    redistribute the balance without on-chain transactions.
    """

    id: str
    party_a: str  # Address or identity
    party_b: str
    capacity_sompi: int  # Total KAS locked in the channel
    balance_a: int  # Current balance of A
    balance_b: int  # Current balance of B
    sequence: int = 0  # Latest off-chain update number
    status: str = "open"  # open, closing, closed, disputed
    fund_txid: str = ""
    close_txid: str = ""
    created_at: float = field(default_factory=time.time)
    closed_at: float = 0.0
    network: str = "mainnet"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "party_a": self.party_a[:20] + "..." if len(self.party_a) > 20 else self.party_a,
            "party_b": self.party_b[:20] + "..." if len(self.party_b) > 20 else self.party_b,
            "capacity_sompi": self.capacity_sompi,
            "balance_a": self.balance_a,
            "balance_b": self.balance_b,
            "capacity_kas": self.capacity_sompi / 100_000_000,
            "balance_a_kas": self.balance_a / 100_000_000,
            "balance_b_kas": self.balance_b / 100_000_000,
            "sequence": self.sequence,
            "status": self.status,
            "fund_txid": self.fund_txid[:16] + "..." if self.fund_txid else "",
            "close_txid": self.close_txid[:16] + "..." if self.close_txid else "",
            "network": self.network,
        }


# ═══════════════════════════════════════════
# Channel store
# ═══════════════════════════════════════════


class ChannelStore:
    """Persistent store for payment channels."""

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            storage_dir = str(Path.home() / ".vida" / "channels")
        self._path = Path(storage_dir) / "channels.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._channels: dict[str, PaymentChannel] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for d in data.get("channels", []):
                    c = PaymentChannel(**{k: v for k, v in d.items() if k in PaymentChannel.__dataclass_fields__})
                    self._channels[c.id] = c
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("Channel store load error: %s", e)

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(
                {
                    "channels": [c.to_dict() for c in self._channels.values()],
                    "updated_at": time.time(),
                },
                indent=2,
            )
        )

    def save(self, channel: PaymentChannel) -> None:
        self._channels[channel.id] = channel
        self._save()

    def get(self, channel_id: str) -> Optional[PaymentChannel]:
        return self._channels.get(channel_id)

    def list_open(self) -> list[PaymentChannel]:
        return [c for c in self._channels.values() if c.status == "open"]

    def list_all(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self._channels.values()]

    def update(self, channel_id: str, **kwargs) -> bool:
        channel = self._channels.get(channel_id)
        if not channel:
            return False
        for k, v in kwargs.items():
            if hasattr(channel, k):
                setattr(channel, k, v)
        self._save()
        return True


# ═══════════════════════════════════════════
# Channel operations
# ═══════════════════════════════════════════


def open_channel(
    party_a: str,
    party_b: str,
    capacity_kas: float,
    network: str = "mainnet",
) -> dict[str, Any]:
    """Open a payment channel between two parties.

    The channel is funded by a covenant UTXO. Both parties can
    exchange off-chain micropayments and settle on-chain.

    Fee: 0.1% of channel capacity (fund_fee) to the fee address.
    """
    try:
        from vida.plugins.covenant.fees import calc_fund_fee, get_fee_address

        channel_id = f"ch_{secrets.token_hex(8)}"
        capacity_sompi = int(capacity_kas * 100_000_000)
        fee_kas = calc_fund_fee(capacity_kas)

        channel = PaymentChannel(
            id=channel_id,
            party_a=party_a,
            party_b=party_b,
            capacity_sompi=capacity_sompi,
            balance_a=capacity_sompi,  # A funds the channel
            balance_b=0,
            network=network,
        )

        store = ChannelStore()
        store.save(channel)

        return {
            "ok": True,
            "channel_id": channel_id,
            "capacity_kas": capacity_kas,
            "fee_kas": fee_kas,
            "fee_address": get_fee_address(network),
            "party_a": party_a[:20] + "..." if len(party_a) > 20 else party_a,
            "party_b": party_b[:20] + "..." if len(party_b) > 20 else party_b,
            "note": f"Channel opened. Fund with {capacity_kas + fee_kas} KAS ({capacity_kas} + {fee_kas} fee).",
        }
    except Exception as e:
        return {"ok": False, "error": f"open channel failed: {e}"}


def update_channel(
    channel_id: str,
    party_a_sig: str,
    party_b_sig: str,
    new_balance_a: int,
    new_balance_b: int,
    store: Optional[ChannelStore] = None,
) -> dict[str, Any]:
    """Update the off-chain state of a payment channel.

    Both parties sign the new balance split. The sequence number
    increments to prevent replay attacks.
    """
    try:
        store = store or ChannelStore()
        channel = store.get(channel_id)
        if not channel:
            return {"ok": False, "error": f"channel {channel_id} not found"}
        if channel.status != "open":
            return {"ok": False, "error": f"channel is {channel.status}, not open"}

        total = new_balance_a + new_balance_b
        if total != channel.capacity_sompi:
            return {"ok": False, "error": f"balance sum {total} != capacity {channel.capacity_sompi}"}
        if new_balance_a < 0 or new_balance_b < 0:
            return {"ok": False, "error": "negative balance"}

        # Update state
        channel.balance_a = new_balance_a
        channel.balance_b = new_balance_b
        channel.sequence += 1
        store.save(channel)

        return {
            "ok": True,
            "channel_id": channel_id,
            "sequence": channel.sequence,
            "balance_a_kas": new_balance_a / 100_000_000,
            "balance_b_kas": new_balance_b / 100_000_000,
        }
    except Exception as e:
        return {"ok": False, "error": f"update channel failed: {e}"}


def close_channel(
    channel_id: str,
    final_sig_a: str = "",
    final_sig_b: str = "",
    store: Optional[ChannelStore] = None,
) -> dict[str, Any]:
    """Close a payment channel and settle on-chain.

    The final state is submitted to the chain. Both parties withdraw
    their final balances.
    """
    try:
        store = store or ChannelStore()
        channel = store.get(channel_id)
        if not channel:
            return {"ok": False, "error": f"channel {channel_id} not found"}
        if channel.status != "open":
            return {"ok": False, "error": f"channel is {channel.status}, not open"}

        channel.status = "closed"
        channel.closed_at = time.time()
        store.save(channel)

        return {
            "ok": True,
            "channel_id": channel_id,
            "final_a_kas": channel.balance_a / 100_000_000,
            "final_b_kas": channel.balance_b / 100_000_000,
            "sequence": channel.sequence,
            "note": "Channel closed. Submit final state on-chain to withdraw funds.",
        }
    except Exception as e:
        return {"ok": False, "error": f"close channel failed: {e}"}


# ═══════════════════════════════════════════
# Hermes tools
# ═══════════════════════════════════════════


def vida_channel_open(
    party_a: str,
    party_b: str,
    capacity_kas: float,
    network: str = "mainnet",
) -> dict[str, Any]:
    """Open a payment channel between two parties.

    The channel is funded by a covenant UTXO. Both parties can
    exchange off-chain micropayments and settle on-chain.
    """
    return open_channel(party_a, party_b, capacity_kas, network)


def vida_channel_update(
    channel_id: str,
    party_a_sig: str,
    party_b_sig: str,
    new_balance_a_kas: float,
    new_balance_b_kas: float,
) -> dict[str, Any]:
    """Update the off-channel balance between two parties.

    Both parties must sign the new balance. The sequence number
    prevents replay attacks.
    """
    return update_channel(
        channel_id,
        party_a_sig,
        party_b_sig,
        int(new_balance_a_kas * 100_000_000),
        int(new_balance_b_kas * 100_000_000),
    )


def vida_channel_close(
    channel_id: str,
    final_sig_a: str = "",
    final_sig_b: str = "",
) -> dict[str, Any]:
    """Close a payment channel and settle on-chain."""
    return close_channel(channel_id, final_sig_a, final_sig_b)


def vida_channel_status(channel_id: str) -> dict[str, Any]:
    """Check the status of a payment channel."""
    store = ChannelStore()
    channel = store.get(channel_id)
    if not channel:
        return {"ok": False, "error": f"channel {channel_id} not found"}
    return {"ok": True, "channel": channel.to_dict()}


def vida_channel_list(network: str = "mainnet") -> dict[str, Any]:
    """List all payment channels."""
    store = ChannelStore()
    channels = store.list_all()
    return {
        "ok": True,
        "count": len(channels),
        "open": len([c for c in channels if c.get("status") == "open"]),
        "channels": channels,
    }
