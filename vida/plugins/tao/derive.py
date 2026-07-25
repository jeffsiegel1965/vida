"""
Owner-path TAO key derivation (sr25519 / SS58).

Rules:
- Call only from owner-run scripts / unlocked vault flows — never from agent tools
  that accept raw mnemonics over chat.
- Does not write files by itself; caller decides storage.
- Returns public fields + secret material for the caller to encrypt immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SR25519_CRYPTO_TYPE = 1
DEFAULT_SS58_PREFIX = 42
DERIVATION_METHOD = "substrate_uri_sr25519_v1"
# Coldkey: URI = mnemonic (root). Hotkey: mnemonic//hotkey
HOTKEY_SUFFIX = "//hotkey"


@dataclass
class TaoDerivedKeys:
    ss58_address: str  # coldkey address (funds)
    hotkey_ss58: str
    ss58_prefix: int
    derivation_method: str
    # Secrets — caller must encrypt or discard; never log
    cold_private_hex: str
    hot_private_hex: str
    public_key_hex: str
    hot_public_key_hex: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "ss58_address": self.ss58_address,
            "hotkey_ss58": self.hotkey_ss58,
            "ss58_prefix": self.ss58_prefix,
            "derivation_method": self.derivation_method,
            "public_key_hex": self.public_key_hex,
            "hot_public_key_hex": self.hot_public_key_hex,
        }


from substrateinterface import Keypair as _Keypair  # type: ignore


def _import_keypair():
    return _Keypair


def validate_mnemonic(mnemonic: str) -> str:
    words = " ".join(mnemonic.strip().split())
    if not words:
        raise ValueError("empty mnemonic")
    n = len(words.split())
    if n not in (12, 15, 18, 21, 24):
        raise ValueError(f"mnemonic must be 12–24 words, got {n}")
    # Prefer bip39 check if available
    try:
        from mnemonic import Mnemonic  # type: ignore

        if not Mnemonic("english").check(words):
            raise ValueError("invalid BIP39 mnemonic")
    except ImportError:
        pass  # substrate will still fail on bad URI
    return words


def derive_tao_keys(
    mnemonic: str,
    *,
    ss58_prefix: int = DEFAULT_SS58_PREFIX,
) -> TaoDerivedKeys:
    """
    Derive coldkey + hotkey from BIP39 mnemonic (Substrate URI style).

    Coldkey URI:  <mnemonic>
    Hotkey URI:   <mnemonic>//hotkey

    Same pattern as kaspa-suite TAOHDWallet — documented for Vida.
    """
    words = validate_mnemonic(mnemonic)
    Keypair = _import_keypair()
    cold = Keypair.create_from_uri(words, crypto_type=SR25519_CRYPTO_TYPE, ss58_format=ss58_prefix)
    hot = Keypair.create_from_uri(
        f"{words}{HOTKEY_SUFFIX}",
        crypto_type=SR25519_CRYPTO_TYPE,
        ss58_format=ss58_prefix,
    )

    def _priv_hex(kp: Any) -> str:
        # substrate-interface: private_key bytes or hex
        pk = getattr(kp, "private_key", None)
        if pk is None:
            raise RuntimeError("keypair missing private_key")
        if isinstance(pk, (bytes, bytearray)):
            return bytes(pk).hex()
        if isinstance(pk, str):
            return pk[2:] if pk.startswith("0x") else pk
        return bytes(pk).hex()

    def _pub_hex(kp: Any) -> str:
        pub = getattr(kp, "public_key", None)
        if pub is None:
            return ""
        if isinstance(pub, (bytes, bytearray)):
            return bytes(pub).hex()
        if isinstance(pub, str):
            return pub[2:] if pub.startswith("0x") else pub
        return bytes(pub).hex()

    return TaoDerivedKeys(
        ss58_address=cold.ss58_address,
        hotkey_ss58=hot.ss58_address,
        ss58_prefix=ss58_prefix,
        derivation_method=DERIVATION_METHOD,
        cold_private_hex=_priv_hex(cold),
        hot_private_hex=_priv_hex(hot),
        public_key_hex=_pub_hex(cold),
        hot_public_key_hex=_pub_hex(hot),
    )


def wipe_secrets(keys: TaoDerivedKeys) -> None:
    """Best-effort clear of secret hex strings on the object (Python string immutability limits)."""
    keys.cold_private_hex = ""
    keys.hot_private_hex = ""
