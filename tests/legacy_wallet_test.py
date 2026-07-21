"""
Legacy Wallet Test - Only for testing purposes.
This file is a security risk and must not be used in production.
"""

import os
import sys

# Enable legacy wallet for testing
os.environ["VIDA_LEGACY_WALLET_ALLOWED"] = "1"

import json
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Optional

import kaspa as kas
from kaspa import Keypair, NetworkType, PrivateKey, PublicKey

try:
    from ml_dsa_65 import (  # noqa: F401 — imported for availability detection
        PUBLIC_KEY_LEN,
        SECRET_KEY_LEN,
        SIGNATURE_LEN,
        keygen,
        sign,
        verify,
    )

    PQ_AVAILABLE = True
except ImportError:
    PQ_AVAILABLE = False


class DelegationMode(Enum):
    """Delegation mode for session keys."""

    FULL = "FULL"  # Can sign any amount without approval
    COMMAND = "COMMAND"  # Always requires owner explicit approval
    HYBRID = "HYBRID"  # Can sign up to threshold_kas, above requires approval


@dataclass
class SessionKey:
    """Ephemeral session key (in-memory only, never persisted)."""

    public_key_hex: str
    mode: DelegationMode
    created_at: datetime
    expires_at: datetime
    threshold_kas: float = 0.0
    lifetime_hours: int = 24
    revoked: bool = False
    daily_spent: float = 0.0
    daily_limit_kas: float = 0.0  # 0 = no cumulative cap (FULL default); HYBRID sets one
    _spend_day: str = ""  # YYYY-MM-DD the daily_spent counter belongs to

    @property
    def is_active(self) -> bool:
        """Check if session key is valid and not expired."""
        if self.revoked:
            return False
        return datetime.now() < self.expires_at

    def _roll_day(self):
        """Reset the daily spend counter when the calendar day changes."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._spend_day != today:
            self._spend_day = today
            self.daily_spent = 0.0

    def can_sign(self, amount_kas: float) -> bool:
        """
        Returns True if this session key can sign for the given amount.
        Negative amounts are ALWAYS rejected.
        FULL: True if active (subject to daily_limit_kas if set)
        COMMAND: always False (owner must explicitly approve)
        HYBRID: True iff amount_kas <= threshold_kas AND cumulative
                daily spend stays within daily_limit_kas
        """
        if amount_kas < 0:
            return False
        if not self.is_active:
            return False
        self._roll_day()
        if self.mode == DelegationMode.COMMAND:
            return False
        # Cumulative daily cap applies to FULL and HYBRID when set
        if self.daily_limit_kas > 0 and (self.daily_spent + amount_kas) > self.daily_limit_kas:
            return False
        if self.mode == DelegationMode.FULL:
            return True
        if self.mode == DelegationMode.HYBRID:
            return amount_kas <= self.threshold_kas
        return False

    def record_spend(self, amount_kas: float):
        """Add a successful spend to the daily counter."""
        self._roll_day()
        self.daily_spent += max(amount_kas, 0.0)


class Vida:
    """
    Vida Wallet - Kaspa wallet with optional post-quantum signatures and delegation.

    Cold wallet persists to JSON with chmod 0600.
    Session keys are ephemeral (in-memory only).
    """

    def __init__(self, wallet_path: str | Path, network: str = "mainnet"):
        """
        Load an existing wallet from JSON file.

        Args:
            wallet_path: Path to the wallet JSON file
            network: 'mainnet' or 'testnet'
        """
        self.wallet_path = Path(wallet_path)
        self.network = network

        if not self.wallet_path.exists():
            raise FileNotFoundError(f"Wallet file not found: {wallet_path}")

        with open(self.wallet_path, "r") as f:
            data = json.load(f)

        self.address = data["address"]
        self.public_key = data["public_key"]
        self._private_key_hex = data["private_key_hex"]  # Plaintext — legacy only. Use secure_wallet.py for real funds.

        # Optional post-quantum keys
        self.pq_pubkey = data.get("pq_pubkey")
        self._pq_privkey = data.get("pq_privkey")

        # Network type
        self._network_type = NetworkType.Mainnet if network == "mainnet" else NetworkType.Testnet

        # Session key registry (in-memory only)
        self._session_keys: dict[str, SessionKey] = {}
        self._session_privkeys: dict[str, str] = {}  # map pubkey_hex -> privkey_hex

    def sign(self, message: str) -> str:
        """
        Sign a message with the cold wallet's Schnorr key.

        Args:
            message: Message string to sign

        Returns:
            Signature as hex string (128 chars)
        """
        priv = PrivateKey(self._private_key_hex)
        return kas.sign_message(message, priv)

    def verify(self, message: str, sig_hex: str) -> bool:
        """
        Verify a Schnorr signature.

        Args:
            message: Original message string
            sig_hex: Signature hex string (128 chars)

        Returns:
            True if signature is valid
        """
        pub = PublicKey(self.public_key)
        return kas.verify_message(message, sig_hex, pub)

    def sign_pq(self, message: bytes) -> bytes:
        """
        Sign a message with the post-quantum ML-DSA-65 key.

        Args:
            message: Message bytes to sign

        Returns:
            Signature as bytes (3309 bytes)

        Raises:
            ValueError: If PQ keys not available
        """
        if not PQ_AVAILABLE or not self._pq_privkey:
            raise ValueError("Post-quantum keys not available for this wallet")

        # Decode hex to bytes
        privkey_bytes = bytes.fromhex(self._pq_privkey)
        return sign(message, privkey_bytes)

    def verify_pq(self, message: bytes, signature: bytes) -> bool:
        """
        Verify a post-quantum ML-DSA-65 signature.

        Args:
            message: Original message bytes
            signature: Signature bytes (3309 bytes)

        Returns:
            True if signature is valid
        """
        if not PQ_AVAILABLE or not self.pq_pubkey:
            raise ValueError("Post-quantum keys not available for this wallet")

        # Decode hex to bytes
        pubkey_bytes = bytes.fromhex(self.pq_pubkey)
        return verify(message, signature, pubkey_bytes)

    def create_session_key(
        self,
        mode: DelegationMode,
        threshold: float = 0.0,
        expires_hours: int = 24,
        daily_limit: float = 0.0,
    ) -> SessionKey:
        """
        Create a new ephemeral session key.

        Args:
            mode: DelegationMode (FULL, COMMAND, HYBRID)
            threshold: For HYBRID mode, max KAS amount per single transaction
            expires_hours: Hours until session key expires
            daily_limit: Max cumulative KAS per day (0 = no cap)

        Returns:
            SessionKey dataclass instance
        """
        # Generate new Keypair for session
        kp = Keypair.random()
        now = datetime.now()
        expires = now + timedelta(hours=expires_hours)

        session_key = SessionKey(
            public_key_hex=kp.public_key,
            mode=mode,
            created_at=now,
            expires_at=expires,
            threshold_kas=threshold,
            lifetime_hours=expires_hours,
            daily_limit_kas=daily_limit,
        )

        # Store in registry (in-memory only)
        self._session_keys[kp.public_key] = session_key
        self._session_privkeys[kp.public_key] = kp.private_key

        return session_key

    def sign_with_session(
        self,
        session_pubkey: str,
        message: str,
        amount_kas: float = 0.0,
    ) -> Optional[str]:
        """
        Sign with a session key if policy allows.

        Args:
            session_pubkey: Session key's public key hex
            message: Message to sign
            amount_kas: Amount of KAS being spent (for policy check)

        Returns:
            Signature hex string if allowed, None if policy rejects
        """
        session = self._session_keys.get(session_pubkey)
        if not session:
            return None

        if not session.can_sign(amount_kas):
            return None

        # Get the session's private key
        privkey_hex = self._session_privkeys.get(session_pubkey)
        if not privkey_hex:
            return None

        priv = PrivateKey(privkey_hex)
        sig = kas.sign_message(message, priv)
        # Count this spend against the daily limit
        session.record_spend(amount_kas)
        return sig

    def revoke_session_key(self, session_pubkey: str):
        """
        Revoke a session key and wipe its private key from memory.

        Args:
            session_pubkey: Session key's public key hex
        """
        if session_pubkey in self._session_keys:
            self._session_keys[session_pubkey].revoked = True
        # Destroy the secret so a revoked key can never sign again,
        # even if policy checks were somehow bypassed
        self._session_privkeys.pop(session_pubkey, None)

    def list_session_keys(self) -> List[dict]:
        """
        List all session keys (without private keys).

        Returns:
            List of dicts with session key info (no private_key_hex)
        """
        result = []
        for pub_hex, session in self._session_keys.items():
            result.append(
                {
                    "public_key_hex": session.public_key_hex,
                    "mode": session.mode.value,
                    "created_at": session.created_at.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                    "threshold_kas": session.threshold_kas,
                    "daily_limit_kas": session.daily_limit_kas,
                    "lifetime_hours": session.lifetime_hours,
                    "revoked": session.revoked,
                    "is_active": session.is_active,
                    "daily_spent": session.daily_spent,
                }
            )
        return result


def create_wallet(
    wallet_path: str | Path,
    network: str = "mainnet",
    mldsa: bool = False,
) -> Vida:
    """
    Create a new wallet and persist it to disk with chmod 0600.

    Args:
        wallet_path: Path where wallet JSON will be saved
        network: 'mainnet' or 'testnet'
        mldsa: Whether to generate post-quantum ML-DSA-65 keys

    Returns:
        Vida wallet instance
    """
    import sys as _sys

    print("!" * 60, file=_sys.stderr)
    print("!!! WARNING: PLAINTEXT PRIVATE KEY STORAGE !!!", file=_sys.stderr)
    print("!!! This wallet saves keys in plaintext JSON. !!!", file=_sys.stderr)
    print("!!! Use secure_wallet.py for real funds.      !!!", file=_sys.stderr)
    print("!" * 60, file=_sys.stderr)
    import time as _time

    _time.sleep(3)

    wallet_path = Path(wallet_path)

    # Generate Kaspa keypair
    kp = Keypair.random()

    # Derive address
    network_lower = network.lower()
    if network_lower not in ("mainnet", "testnet"):
        raise ValueError(f"Invalid network: {network}. Must be 'mainnet' or 'testnet'")

    address = str(kp.to_address(network_lower))

    # Build wallet data
    data = {
        "address": address,
        "public_key": kp.public_key,
        "private_key_hex": kp.private_key,
        "network": network_lower,
    }

    # Optional: generate post-quantum keys
    if mldsa and PQ_AVAILABLE:
        pq_pub, pq_priv = keygen()
        data["pq_pubkey"] = pq_pub.hex()
        data["pq_privkey"] = pq_priv.hex()

    # Write to disk
    with open(wallet_path, "w") as f:
        json.dump(data, f, indent=2)

    # Set permissions to 0600 (owner read/write only)
    os.chmod(wallet_path, stat.S_IRUSR | stat.S_IWUSR)

    # Return Vida instance (will reload from disk)
    return Vida(wallet_path, network_lower)
