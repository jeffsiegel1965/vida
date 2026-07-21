"""Covenant payment channels — KCC-0402 aligned.

KCC-0402: Covenant Payment Channels (draft, 2026-07)
  https://github.com/kaspanet/kccs/pull/4

Two modes:
  - kcc0402 (default): Unidirectional. Payer locks KAS, pays payee with
    off-chain BIP340 vouchers. On-chain: open + close (two transactions)
    carry an unbounded number of payments.
  - bidirectional (legacy): Vida's original. Both parties sign each update.

KCC-0402 voucher format:
  message = channel_id (32 bytes) || cumulative_total_sompi (8 bytes, LE)
  digest  = SHA-256(message)
  voucher = BIP340-Sign(payer_privkey, digest)  →  64-byte signature
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Kaspa SDK
from kaspa import (
    PrivateKey,
    PublicKey,
    sign_message,
)

# ══════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════

SOMIPI_PER_KAS = 100_000_000
HASH_FN = hashlib.sha256  # KCC-0402 uses SHA-256

# Minimum DAA delta for channel expiry
MIN_EXPIRY_DAA_DELTA = 864000  # ~1 day at 10 BPS


# ══════════════════════════════════════════════════════════
# KCC-0402 Voucher
# ══════════════════════════════════════════════════════════


def voucher_message(channel_id: str, cumulative_total_sompi: int) -> bytes:
    """Build the KCC-0402 voucher message.

    message = channel_id (32 bytes) || cumulative_total_sompi (8 bytes, LE)
    """
    cid = bytes.fromhex(channel_id)
    if len(cid) != 32:
        raise ValueError(f"channel_id must be 32 bytes (got {len(cid)})")
    if not 0 <= cumulative_total_sompi < 2**63:
        raise ValueError(f"cumulative_total out of range: {cumulative_total_sompi}")
    return cid + struct.pack("<Q", cumulative_total_sompi)


def voucher_digest(channel_id: str, cumulative_total_sompi: int) -> str:
    """SHA-256 digest of the voucher message, as hex string."""
    msg = voucher_message(channel_id, cumulative_total_sompi)
    return HASH_FN(msg).hexdigest()


def create_voucher(
    channel_id: str,
    cumulative_total_sompi: int,
    payer_privkey_hex: str,
) -> str:
    """Create a KCC-0402 voucher (BIP340 signature).

    Returns 64-byte signature as hex string.
    """
    digest = voucher_digest(channel_id, cumulative_total_sompi)
    priv = PrivateKey(payer_privkey_hex)
    sig = sign_message(digest, priv)
    return sig


def verify_voucher(
    channel_id: str,
    cumulative_total_sompi: int,
    voucher_hex: str,
    payer_pubkey_xonly: str,
) -> bool:
    """Verify a KCC-0402 voucher.

    Uses the Kaspa SDK's verify_message via sign/verify pattern.
    """
    # The SDK doesn't expose verify_message directly in all builds.
    # We reconstruct the digest and let the caller verify via the
    # blockchain or a BIP340 library.
    # For now, this is a placeholder — actual verification requires
    # a BIP340 verifier (rusty-kaspa's verify_message or external lib).
    #
    # TODO: wire KCC-0402 conformance vectors when verify is available.
    expected_sig_len = 128  # 64 bytes as hex
    if len(voucher_hex) != expected_sig_len:
        return False
    try:
        bytes.fromhex(voucher_hex)
    except ValueError:
        return False
    return True


# ══════════════════════════════════════════════════════════
# KCC-0402 Channel State
# ══════════════════════════════════════════════════════════


@dataclass
class KCC0402Channel:
    """A unidirectional payment channel per KCC-0402.

    The payer locks KAS in a covenant. The payee accumulates off-chain
    vouchers. Either party can close on-chain at any time.
    """

    # ── Constructor args ──
    payer_pubkey: str  # x-only hex (32 bytes)
    payee_pubkey: str  # x-only hex (32 bytes)
    expiry_daa: int  # DAA score after which refund is valid
    maxfee_sompi: int  # Maximum tx fee the close/refund may consume

    # ── Runtime state ──
    channel_id: str = ""  # Set on open
    capacity_sompi: int = 0
    cumulative_paid_sompi: int = 0  # Highest voucher total accepted
    last_voucher: str = ""  # Hex of the last accepted voucher
    status: str = "open"  # open | closed | refunded
    fund_txid: str = ""
    close_txid: str = ""
    network: str = "mainnet"
    created_at: float = field(default_factory=time.time)

    def payer_remainder(self) -> int:
        """Sompi returned to the payer if closed now."""
        return self.capacity_sompi - self.cumulative_paid_sompi - self.maxfee_sompi

    def verify_voucher(self, cumulative_total_sompi: int, voucher_hex: str) -> bool:
        """Verify a voucher is valid and advances the total."""
        if cumulative_total_sompi <= self.cumulative_paid_sompi:
            return False
        if cumulative_total_sompi > self.capacity_sompi - self.maxfee_sompi:
            return False  # Can't realize the payout after fee
        return verify_voucher(
            self.channel_id,
            cumulative_total_sompi,
            voucher_hex,
            self.payer_pubkey,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "payer_pubkey": self.payer_pubkey[:16] + "...",
            "payee_pubkey": self.payee_pubkey[:16] + "...",
            "capacity_kas": self.capacity_sompi / SOMIPI_PER_KAS,
            "paid_kas": self.cumulative_paid_sompi / SOMIPI_PER_KAS,
            "status": self.status,
            "fund_txid": self.fund_txid[:16] + "..." if self.fund_txid else "",
            "close_txid": self.close_txid[:16] + "..." if self.close_txid else "",
            "network": self.network,
        }

    @classmethod
    def offer(
        cls,
        payee_pubkey: str,
        price_sompi: int = 3_000_000,
        min_channel_sompi: int = 100_000_000,
        max_channel_sompi: int = 500_000_000,
        network: str = "mainnet",
    ) -> dict[str, Any]:
        """Generate a KCC-0402 offer object for discovery."""
        return {
            "scheme": "kaspa-channel",
            "network": network,
            "payee_pubkey": payee_pubkey,
            "price_sompi": str(price_sompi),
            "min_channel_sompi": str(min_channel_sompi),
            "max_channel_sompi": str(max_channel_sompi),
            "min_expiry_daa_delta": MIN_EXPIRY_DAA_DELTA,
            "maxfee_sompi": str(min_channel_sompi // 100),
        }


# ══════════════════════════════════════════════════════════
# KCC-0402 Channel Operations
# ══════════════════════════════════════════════════════════


def open_kcc0402(
    payer_pubkey: str,
    payee_pubkey: str,
    capacity_sompi: int,
    expiry_daa: int,
    payer_privkey_hex: str = "",
    network: str = "mainnet",
) -> dict[str, Any]:
    """Open a KCC-0402 payment channel.

    The payer locks KAS in a covenant. Returns the channel state
    and the covenant info needed to fund it on-chain.

    Args:
        payer_pubkey: Payer's x-only pubkey hex (32 bytes)
        payee_pubkey: Payee's x-only pubkey hex (32 bytes)
        capacity_sompi: KAS to lock in the covenant
        expiry_daa: DAA after which refund is valid
        payer_privkey_hex: Optional — to generate the first voucher
        network: 'mainnet' or 'testnet-10'
    """
    try:
        maxfee = max(capacity_sompi // 100, 10_000)  # 1% fee budget
        channel_id = secrets.token_hex(32)

        channel = KCC0402Channel(
            payer_pubkey=payer_pubkey,
            payee_pubkey=payee_pubkey,
            expiry_daa=expiry_daa,
            maxfee_sompi=maxfee,
        )
        channel.channel_id = channel_id
        channel.capacity_sompi = capacity_sompi
        channel.network = network

        store = KCC0402ChannelStore()
        store.save(channel)

        result = {
            "ok": True,
            "channel_id": channel_id,
            "payer_pubkey": payer_pubkey[:16] + "...",
            "payee_pubkey": payee_pubkey[:16] + "...",
            "capacity_sompi": capacity_sompi,
            "capacity_kas": capacity_sompi / SOMIPI_PER_KAS,
            "expiry_daa": expiry_daa,
            "maxfee_sompi": maxfee,
            "network": network,
            "note": "Fund the covenant P2SH address to activate the channel. "
            "Send capacity_sompi + tx_fee to the covenant address.",
        }

        # Create first voucher if payer key is provided
        if payer_privkey_hex:
            voucher = create_voucher(channel_id, 0, payer_privkey_hex)
            result["genesis_voucher"] = voucher

        return result

    except Exception as e:
        return {"ok": False, "error": f"open_kcc0402 failed: {e}"}


def pay_kcc0402(
    channel_id: str,
    cumulative_total_sompi: int,
    payer_privkey_hex: str,
    store: Optional[KCC0402ChannelStore] = None,
) -> dict[str, Any]:
    """Create and record a KCC-0402 voucher payment.

    The payer signs a new cumulative total. The payee accepts it if
    valid and advancing.

    Args:
        channel_id: Channel identifier
        cumulative_total_sompi: New cumulative total (monotonic)
        payer_privkey_hex: Payer's private key to sign the voucher
        store: Optional store override
    """
    try:
        store = store or KCC0402ChannelStore()
        channel = store.get(channel_id)
        if not channel:
            return {"ok": False, "error": f"channel {channel_id} not found"}
        if channel.status != "open":
            return {"ok": False, "error": f"channel is {channel.status}"}

        # Create voucher
        voucher = create_voucher(channel_id, cumulative_total_sompi, payer_privkey_hex)

        # Verify (simulated until full verifier is available)
        if not channel.verify_voucher(cumulative_total_sompi, voucher):
            return {"ok": False, "error": "voucher verification failed"}

        # Advance state
        channel.cumulative_paid_sompi = cumulative_total_sompi
        channel.last_voucher = voucher
        store.save(channel)

        return {
            "ok": True,
            "channel_id": channel_id,
            "cumulative_total_sompi": cumulative_total_sompi,
            "paid_kas": cumulative_total_sompi / SOMIPI_PER_KAS,
            "voucher": voucher,
            "payer_remainder_sompi": channel.payer_remainder(),
        }

    except Exception as e:
        return {"ok": False, "error": f"pay_kcc0402 failed: {e}"}


def close_kcc0402(
    channel_id: str,
    store: Optional[KCC0402ChannelStore] = None,
) -> dict[str, Any]:
    """Close a KCC-0402 channel.

    Submits the last voucher on-chain. The payee receives the signed
    total, the payer receives the remainder.

    Args:
        channel_id: Channel to close
        store: Optional store override
    """
    try:
        store = store or KCC0402ChannelStore()
        channel = store.get(channel_id)
        if not channel:
            return {"ok": False, "error": f"channel {channel_id} not found"}
        if channel.status != "open":
            return {"ok": False, "error": f"channel is {channel.status}"}

        channel.status = "closed"
        store.save(channel)

        return {
            "ok": True,
            "channel_id": channel_id,
            "payee_gets_kas": channel.cumulative_paid_sompi / SOMIPI_PER_KAS,
            "payer_gets_kas": channel.payer_remainder() / SOMIPI_PER_KAS,
            "last_voucher": channel.last_voucher[:32] + "..." if channel.last_voucher else "",
            "note": "Submit close transaction on-chain with the last voucher to settle.",
        }

    except Exception as e:
        return {"ok": False, "error": f"close_kcc0402 failed: {e}"}


# ══════════════════════════════════════════════════════════
# KCC-0402 Channel Store
# ══════════════════════════════════════════════════════════


class KCC0402ChannelStore:
    """Persistent store for KCC-0402 payment channels."""

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            storage_dir = str(Path.home() / ".vida" / "channels")
        self._path = Path(storage_dir) / "kcc0402_channels.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._channels: dict[str, KCC0402Channel] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for d in data.get("channels", []):
                    self._channels[d["channel_id"]] = KCC0402Channel(**d)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("KCC-0402 store load error: %s", e)

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(
                {
                    "channels": [
                        {
                            k: v
                            for k, v in c.__dict__.items()
                            if not k.startswith("_")
                        }
                        for c in self._channels.values()
                    ],
                    "updated_at": time.time(),
                },
                indent=2,
            )
        )

    def save(self, channel: KCC0402Channel) -> None:
        self._channels[channel.channel_id] = channel
        self._save()

    def get(self, channel_id: str) -> Optional[KCC0402Channel]:
        return self._channels.get(channel_id)

    def list_open(self) -> list[KCC0402Channel]:
        return [c for c in self._channels.values() if c.status == "open"]

    def list_all(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self._channels.values()]


# ══════════════════════════════════════════════════════════
# Legacy bidirectional mode (unchanged from original Vida)
# ══════════════════════════════════════════════════════════
# All functions below this line are the original Vida bidirectional
# channel implementation. They remain for backward compatibility.
# New development should use KCC-0402 mode above.

@dataclass
class ChannelState:
    """Bidirectional channel state (legacy). Both parties sign."""

    channel_id: str
    nonce: int
    balance_a: int
    balance_b: int
    sequence: int = 0
    sig_a: str = ""
    sig_b: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "nonce": self.nonce,
            "balance_a": self.balance_a,
            "balance_b": self.balance_b,
            "sequence": self.sequence,
            "sig_a": self.sig_a[:16] + "..." if self.sig_a else "",
            "sig_b": self.sig_b[:16] + "..." if self.sig_b else "",
        }


@dataclass
class PaymentChannel:
    """Bidirectional payment channel (legacy Vida model)."""

    id: str
    party_a: str
    party_b: str
    capacity_sompi: int
    balance_a: int
    balance_b: int
    sequence: int = 0
    status: str = "open"
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
            "capacity_kas": self.capacity_sompi / SOMIPI_PER_KAS,
            "balance_a_kas": self.balance_a / SOMIPI_PER_KAS,
            "balance_b_kas": self.balance_b / SOMIPI_PER_KAS,
            "sequence": self.sequence,
            "status": self.status,
            "fund_txid": self.fund_txid[:16] + "..." if self.fund_txid else "",
            "close_txid": self.close_txid[:16] + "..." if self.close_txid else "",
            "network": self.network,
        }


class ChannelStore:
    """Persistent store for legacy bidirectional channels."""

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
                logger.warning("Legacy channel store load error: %s", e)

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


def open_channel(party_a: str, party_b: str, capacity_kas: float, network: str = "mainnet") -> dict[str, Any]:
    """Open a legacy bidirectional payment channel."""
    try:
        from vida.plugins.covenant.fees import calc_fund_fee, get_fee_address

        channel_id = f"ch_{secrets.token_hex(8)}"
        capacity_sompi = int(capacity_kas * SOMIPI_PER_KAS)
        fee_kas = calc_fund_fee(capacity_kas)

        channel = PaymentChannel(
            id=channel_id,
            party_a=party_a,
            party_b=party_b,
            capacity_sompi=capacity_sompi,
            balance_a=capacity_sompi,
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
            "note": f"Fund with {capacity_kas + fee_kas} KAS ({capacity_kas} + {fee_kas} fee).",
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
    """Update legacy bidirectional channel off-chain state."""
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
        channel.balance_a = new_balance_a
        channel.balance_b = new_balance_b
        channel.sequence += 1
        store.save(channel)
        return {
            "ok": True,
            "channel_id": channel_id,
            "sequence": channel.sequence,
            "balance_a_kas": new_balance_a / SOMIPI_PER_KAS,
            "balance_b_kas": new_balance_b / SOMIPI_PER_KAS,
        }
    except Exception as e:
        return {"ok": False, "error": f"update channel failed: {e}"}


def close_channel(
    channel_id: str,
    final_sig_a: str = "",
    final_sig_b: str = "",
    store: Optional[ChannelStore] = None,
) -> dict[str, Any]:
    """Close a legacy bidirectional channel."""
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
            "final_a_kas": channel.balance_a / SOMIPI_PER_KAS,
            "final_b_kas": channel.balance_b / SOMIPI_PER_KAS,
            "sequence": channel.sequence,
            "note": "Channel closed. Submit final state on-chain to withdraw funds.",
        }
    except Exception as e:
        return {"ok": False, "error": f"close channel failed: {e}"}


# ══════════════════════════════════════════════════════════
# Hermes tools (compat wrapper — routes to KCC-0402 by default)
# ══════════════════════════════════════════════════════════


def vida_channel_open(
    party_a_or_payer: str,
    party_b_or_payee: str,
    capacity_kas_or_sompi: float,
    network: str = "mainnet",
    mode: str = "kcc0402",
    **kwargs,
) -> dict[str, Any]:
    """Open a payment channel.

    mode='kcc0402' (default): Unidirectional per KCC-0402 standard.
      Requires payer_pubkey, payee_pubkey (x-only hex), expiry_daa.
      capacity is in sompi.

    mode='bidirectional': Original Vida bidirectional.
      Accepts address strings. capacity is in KAS.
    """
    if mode == "kcc0402":
        payer_pubkey = kwargs.get("payer_pubkey", party_a_or_payer)
        payee_pubkey = kwargs.get("payee_pubkey", party_b_or_payee)
        expiry_daa = kwargs.get("expiry_daa", 0)
        return open_kcc0402(
            payer_pubkey=payer_pubkey,
            payee_pubkey=payee_pubkey,
            capacity_sompi=int(capacity_kas_or_sompi),
            expiry_daa=expiry_daa,
            network=network,
        )
    return open_channel(party_a_or_payer, party_b_or_payee, capacity_kas_or_sompi, network)


def vida_channel_pay(
    channel_id: str,
    cumulative_total_sompi: int,
    payer_privkey_hex: str,
) -> dict[str, Any]:
    """Pay via KCC-0402 channel. Creates and records a voucher."""
    return pay_kcc0402(channel_id, cumulative_total_sompi, payer_privkey_hex)


def vida_channel_close(
    channel_id: str,
    mode: str = "kcc0402",
    **kwargs,
) -> dict[str, Any]:
    """Close a payment channel."""
    if mode == "kcc0402":
        return close_kcc0402(channel_id)
    final_sig_a = kwargs.get("final_sig_a", "")
    final_sig_b = kwargs.get("final_sig_b", "")
    return close_channel(channel_id, final_sig_a, final_sig_b)


def vida_channel_status(channel_id: str) -> dict[str, Any]:
    """Check channel status. Checks both KCC-0402 and legacy stores."""
    store = KCC0402ChannelStore()
    ch = store.get(channel_id)
    if ch:
        return {"ok": True, "mode": "kcc0402", "channel": ch.to_dict()}
    legacy = ChannelStore()
    ch2 = legacy.get(channel_id)
    if ch2:
        return {"ok": True, "mode": "bidirectional", "channel": ch2.to_dict()}
    return {"ok": False, "error": f"channel {channel_id} not found"}


def vida_channel_list(network: str = "mainnet", mode: str = "") -> dict[str, Any]:
    """List all channels. mode='kcc0402', 'bidirectional', or '' (both)."""
    result: dict[str, Any] = {"ok": True, "kcc0402": [], "bidirectional": []}

    if mode in ("", "kcc0402"):
        store = KCC0402ChannelStore()
        result["kcc0402"] = store.list_all()

    if mode in ("", "bidirectional"):
        legacy = ChannelStore()
        result["bidirectional"] = legacy.list_all()

    result["total"] = len(result["kcc0402"]) + len(result["bidirectional"])
    return result


def vida_channel_offer(payee_pubkey: str, **kwargs) -> dict[str, Any]:
    """Generate a KCC-0402 channel offer for peer discovery."""
    return {
        "ok": True,
        "offer": KCC0402Channel.offer(payee_pubkey, **kwargs),
    }


def vida_channel_voucher(
    channel_id: str,
    cumulative_total_sompi: int,
    payer_privkey_hex: str,
) -> dict[str, Any]:
    """Create a KCC-0402 voucher without recording it.

    Useful for testing or building vouchers before submission.
    """
    try:
        voucher = create_voucher(channel_id, cumulative_total_sompi, payer_privkey_hex)
        return {
            "ok": True,
            "voucher": voucher,
            "channel_id": channel_id,
            "cumulative_total_sompi": cumulative_total_sompi,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}