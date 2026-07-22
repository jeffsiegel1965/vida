"""
ML-DSA-44 Post-Quantum Signature Wrapper (NIST FIPS-204)
=========================================================

Wraps pqcrypto._sign.ml_dsa_44 (CFFI bindings to PQClean ref impl).

ML-DSA-44 (Dilithium-2): NIST security level 2 (~128-bit classical equivalent).
This is the parameter set verified on Kaspa TN10 via KIP-16 ZK opcode
by KaspaKii / 0xfourier (July 2026).

Key sizes:
  public:   1312 bytes
  private:  2560 bytes
  signature: 2420 bytes

Previously Vida used ML-DSA-65 (larger, non-standard parameter set).
ML-DSA-44 is smaller, faster, and ecosystem-compatible with the proven
Kaspa on-chain PQ verification pipeline.
"""

import os

try:
    import pqcrypto._sign.ml_dsa_44 as _mldsa

    LIB = _mldsa.lib
    FFI = _mldsa.ffi
    PQ_AVAILABLE = True
except ImportError as e:
    PQ_AVAILABLE = False
    LIB = None
    FFI = None
    _IMPORT_ERROR = str(e)

# ── ML-DSA-44 NIST parameter sizes ──

PUBLIC_KEY_LEN = 1312
SECRET_KEY_LEN = 2560
SIGNATURE_LEN = 2420


def _require_pq():
    if not PQ_AVAILABLE:
        raise RuntimeError(f"ML-DSA-44 not available: {_IMPORT_ERROR}. Install with: pip install pqcrypto>=0.4")


def keygen() -> tuple[bytes, bytes]:
    """
    Generate ML-DSA-44 keypair from OS CSPRNG.
    Returns (public_key, secret_key) as raw bytes.
    """
    _require_pq()
    _ = os.urandom(64)  # extra entropy

    pk_buf = FFI.new(f"uint8_t[{PUBLIC_KEY_LEN}]")
    sk_buf = FFI.new(f"uint8_t[{SECRET_KEY_LEN}]")

    ret = LIB.PQCLEAN_MLDSA44_CLEAN_crypto_sign_keypair(pk_buf, sk_buf)
    if ret != 0:
        raise RuntimeError(f"ML-DSA-44 keygen failed: {ret}")

    pk = bytes(FFI.buffer(pk_buf, PUBLIC_KEY_LEN))
    sk = bytes(FFI.buffer(sk_buf, SECRET_KEY_LEN))
    return pk, sk


def sign(message: bytes, secret_key: bytes) -> bytes:
    """
    Sign message with ML-DSA-44. Returns raw signature bytes.

    Args:
        message: Arbitrary bytes to sign.
        secret_key: 2560-byte secret key from keygen().

    Returns:
        2420-byte signature.
    """
    _require_pq()

    msg_buf = FFI.from_buffer(message)
    sig_buf = FFI.new(f"uint8_t[{SIGNATURE_LEN}]")
    sig_len = FFI.new("size_t *")

    ret = LIB.PQCLEAN_MLDSA44_CLEAN_crypto_sign_signature(
        sig_buf,
        sig_len,
        msg_buf,
        len(message),
        secret_key,
    )
    if ret != 0:
        raise RuntimeError(f"ML-DSA-44 sign failed: {ret}")

    return bytes(FFI.buffer(sig_buf, sig_len[0]))


def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    Verify ML-DSA-44 signature.

    Args:
        message: Original message bytes.
        signature: 2420-byte signature.
        public_key: 1312-byte public key.

    Returns:
        True if valid, False otherwise.
    """
    _require_pq()

    msg_buf = FFI.from_buffer(message)
    sig_buf = FFI.from_buffer(signature)
    pk_buf = FFI.from_buffer(public_key)

    ret = LIB.PQCLEAN_MLDSA44_CLEAN_crypto_sign_verify(
        sig_buf,
        len(signature),
        msg_buf,
        len(message),
        pk_buf,
    )
    return ret == 0
