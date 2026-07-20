"""
TAO post-quantum identity (ML-DSA-65) — same model as Kaspa Vida.

Honest limits:
- Finney still verifies **sr25519** for transfers/stake. PQ does NOT secure
  on-chain TAO spends today.
- PQ keys are a **forward identity** (attestations, future chain upgrades).
- PQ secret is **not seed-derivable** (PQClean limitation) — backed up only
  inside the encrypted account file with the owner password.
- Agent sessions **never** receive the PQ secret (owner password unlock only).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# vida/ml_dsa_65.py lives next to secure_wallet
_VIDA_DIR = Path(__file__).resolve().parents[2]
if str(_VIDA_DIR) not in sys.path:
    sys.path.insert(0, str(_VIDA_DIR))

try:
    from ml_dsa_65 import (  # type: ignore
        PQ_AVAILABLE,
        PUBLIC_KEY_LEN,
        SECRET_KEY_LEN,
    )
    from ml_dsa_65 import (
        keygen as pq_keygen,
    )
    from ml_dsa_65 import (
        sign as pq_sign,
    )
    from ml_dsa_65 import (
        verify as pq_verify,
    )
except ImportError:
    PQ_AVAILABLE = False
    pq_keygen = pq_sign = pq_verify = None  # type: ignore
    PUBLIC_KEY_LEN = 1952
    SECRET_KEY_LEN = 4032

PQ_SCHEME = "ML-DSA-65"
PQ_NIST_LEVEL = 3


def generate_pq_identity() -> dict[str, Any]:
    """
    Generate ML-DSA-65 keypair.
    Returns {ok, pq_public_key_hex, pq_secret_key_bytes} or error.
    """
    if not PQ_AVAILABLE:
        return {
            "ok": False,
            "error": "ML-DSA-65 not available (install pqcrypto / use Kaspa venv)",
            "pq_available": False,
        }
    pk, sk = pq_keygen()
    if len(pk) != PUBLIC_KEY_LEN or len(sk) != SECRET_KEY_LEN:
        return {"ok": False, "error": "unexpected ML-DSA-65 key sizes"}
    return {
        "ok": True,
        "pq_available": True,
        "scheme": PQ_SCHEME,
        "nist_level": PQ_NIST_LEVEL,
        "pq_public_key_hex": pk.hex(),
        "pq_secret_key_bytes": sk,
    }


def sign_message(message: bytes, secret_key: bytes) -> bytes:
    if not PQ_AVAILABLE:
        raise RuntimeError("ML-DSA-65 not available")
    return pq_sign(message, secret_key)


def verify_message(message: bytes, signature: bytes, public_key_hex: str) -> bool:
    if not PQ_AVAILABLE:
        raise RuntimeError("ML-DSA-65 not available")
    return bool(pq_verify(message, signature, bytes.fromhex(public_key_hex)))


def pq_public_info(record_meta_or_record: Any) -> dict[str, Any]:
    """Safe public summary for status/logs."""
    if hasattr(record_meta_or_record, "pq_public_key"):
        pub = getattr(record_meta_or_record, "pq_public_key", None)
        has_enc = getattr(record_meta_or_record, "enc_pq_sk", None) is not None
    elif isinstance(record_meta_or_record, dict):
        pub = record_meta_or_record.get("pq_public_key")
        has_enc = record_meta_or_record.get("enc_pq_sk") is not None
    else:
        pub, has_enc = None, False
    return {
        "pq_ready": bool(pub and has_enc),
        "pq_scheme": PQ_SCHEME if pub else None,
        "pq_nist_level": PQ_NIST_LEVEL if pub else None,
        "pq_public_key": pub,
        "pq_on_chain": False,
        "pq_note": (
            "Forward identity only — Bittensor still uses sr25519 on-chain" if pub else "No PQ identity on this account"
        ),
    }
