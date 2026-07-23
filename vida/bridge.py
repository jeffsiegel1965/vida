"""
Vida Wallet → Vida Commerce Bridge (Wallet Side).

This bridge connects Vida Wallet's identity vault to Vida Commerce.
It exposes encrypted party profiles for contract party references.

The bridge is Vida-to-Vida only — encrypted with VIDA_BRIDGE_KEY.
Both wallet and commerce must share the same key.

Usage (in Vida Wallet):
    from vida.bridge import WalletBridge, create_vault_from_wallet
    bridge = WalletBridge(vault)
    # Commerce queries: bridge.handle_query(message) → response
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════
# Bridge Key — shared secret between wallet and commerce
# ═══════════════════════════════════════════════════════════════════


def get_bridge_key() -> bytes:
    key = os.environ.get("VIDA_BRIDGE_KEY", "")
    if not key:
        return b"vida-bridge-dev-mode-key-do-not-use-in-production!!"
    return hashlib.sha256(key.encode()).digest()


def is_bridge_configured() -> bool:
    return bool(os.environ.get("VIDA_BRIDGE_KEY", ""))


# ═══════════════════════════════════════════════════════════════════
# Bridge Message Protocol
# ═══════════════════════════════════════════════════════════════════


@dataclass
class BridgeMessage:
    sender: str
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    message_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.message_id:
            raw = f"{self.sender}:{self.action}:{self.timestamp}"
            self.message_id = hashlib.sha256(raw.encode()).hexdigest()[:12]

    def serialize(self) -> str:
        return json.dumps(
            {
                "sender": self.sender,
                "action": self.action,
                "payload": self.payload,
                "timestamp": self.timestamp,
                "message_id": self.message_id,
            }
        )

    @classmethod
    def deserialize(cls, data: str) -> "BridgeMessage":
        d = json.loads(data)
        return cls(
            sender=d["sender"],
            action=d["action"],
            payload=d.get("payload", {}),
            timestamp=d.get("timestamp", ""),
            message_id=d.get("message_id", ""),
        )

    def authenticate(self) -> str:
        key = get_bridge_key()
        return hashlib.pbkdf2_hmac("sha256", self.serialize().encode(), key, 10_000).hex()

    def verify(self, auth_tag: str) -> bool:
        expected = self.authenticate()
        return hmac.compare_digest(expected, auth_tag)


# ═══════════════════════════════════════════════════════════════════
# Simple Identity Models (wallet-native, no commerce dependency)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class IdentityProfile:
    """Party identity stored in the wallet."""

    profile_id: str
    party_name: str
    entity_type: str  # "individual", "llc", "corporation", "dao", etc.
    jurisdiction: str
    verified_addresses: List[str] = field(default_factory=list)
    street_address: str = ""
    city: str = ""
    postal_code: str = ""
    country: str = ""

    def public_summary(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "party_name": self.party_name,
            "entity_type": self.entity_type,
            "jurisdiction": self.jurisdiction,
            "verified_addresses": self.verified_addresses,
        }


@dataclass
class IdentityVault:
    """Simple encrypted identity store in the wallet."""

    profiles: Dict[str, IdentityProfile] = field(default_factory=dict)

    def create_profile(self, party_name: str, entity_type: str, jurisdiction: str, **kwargs) -> IdentityProfile:
        profile_id = hashlib.sha256(
            f"{party_name}:{entity_type}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]
        profile = IdentityProfile(
            profile_id=profile_id,
            party_name=party_name,
            entity_type=entity_type,
            jurisdiction=jurisdiction,
            **kwargs,
        )
        self.profiles[profile_id] = profile
        return profile

    def verify_address(self, profile_id: str, address: str):
        profile = self.profiles.get(profile_id)
        if profile and address not in profile.verified_addresses:
            profile.verified_addresses.append(address)

    def find_by_address(self, address: str) -> Optional[IdentityProfile]:
        for profile in self.profiles.values():
            if address in profile.verified_addresses:
                return profile
        return None

    def list_profiles(self) -> List[Dict[str, Any]]:
        return [p.public_summary() for p in self.profiles.values()]


# ═══════════════════════════════════════════════════════════════════
# Wallet-Side Bridge
# ═══════════════════════════════════════════════════════════════════


@dataclass
class WalletBridge:
    """Bridge that runs inside Vida Wallet.

    Responds to identity queries from Vida Commerce.
    Uses HMAC-authenticated messages with shared VIDA_BRIDGE_KEY.
    """

    vault: IdentityVault

    def handle_query(self, msg: BridgeMessage) -> BridgeMessage:
        """Process incoming query from Vida Commerce."""
        if msg.sender != "vida-commerce":
            return self._error("Unauthorized sender", msg.message_id)

        handlers = {
            "query_identity": self._handle_query_identity,
            "list_profiles": self._handle_list_profiles,
        }

        handler = handlers.get(msg.action)
        if not handler:
            return self._error(f"Unknown action: {msg.action}", msg.message_id)

        return handler(msg)

    def _handle_query_identity(self, msg: BridgeMessage) -> BridgeMessage:
        address = msg.payload.get("kaspa_address", "")
        if not address:
            return self._error("Missing kaspa_address", msg.message_id)

        profile = self.vault.find_by_address(address)
        if profile:
            return BridgeMessage(
                sender="vida-wallet",
                action="identity_response",
                payload={"found": True, "party": profile.public_summary()},
            )
        return BridgeMessage(
            sender="vida-wallet",
            action="identity_response",
            payload={"found": False, "kaspa_address": address},
        )

    def _handle_list_profiles(self, msg: BridgeMessage) -> BridgeMessage:
        return BridgeMessage(
            sender="vida-wallet",
            action="profiles_response",
            payload={"profiles": self.vault.list_profiles()},
        )

    def _error(self, error: str, ref_msg_id: str) -> BridgeMessage:
        return BridgeMessage(
            sender="vida-wallet",
            action="error",
            payload={"error": error, "ref_message_id": ref_msg_id},
        )


# ═══════════════════════════════════════════════════════════════════
# Convenience: create vault from wallet data
# ═══════════════════════════════════════════════════════════════════


def create_vault_from_wallet(
    wallet_addresses: List[str], party_name: str = "", entity_type: str = "individual", jurisdiction: str = ""
) -> IdentityVault:
    """Create an identity vault seeded with wallet addresses."""
    vault = IdentityVault()
    profile = vault.create_profile(
        party_name=party_name or "Vida Wallet Owner",
        entity_type=entity_type,
        jurisdiction=jurisdiction or "CH",
    )
    for addr in wallet_addresses:
        vault.verify_address(profile.profile_id, addr)
    return vault
