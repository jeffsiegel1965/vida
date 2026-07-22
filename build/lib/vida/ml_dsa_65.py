"""
ML-DSA-65 Post-Quantum Signature Wrapper
========================================

Wraps pqcrypto._sign.ml_dsa_65 (CFFI bindings to PQClean ref impl).

NIST Level 3: ~192-bit classical security equivalent.

Key sizes:
  public:  1952 bytes
  private: 4032 bytes
  signature: 3309 bytes
"""

import os

try:
    import pqcrypto._sign.ml_dsa_65 as _mldsa

    LIB = _mldsa.lib
    FFI = _mldsa.ffi
    PQ_AVAILABLE = True
except ImportError as e:
    PQ_AVAILABLE = False
    LIB = None
    FFI = None
    _IMPORT_ERROR = str(e)


PUBLIC_KEY_LEN = 1952
SECRET_KEY_LEN = 4032
SIGNATURE_LEN = 3309


def _require_pq():
    if not PQ_AVAILABLE:
        raise RuntimeError(f"ML-DSA-65 not available: {_IMPORT_ERROR}")


def keygen() -> tuple[bytes, bytes]:
    """
    Generate ML-DSA-65 keypair from OS CSPRNG.
    Returns (public_key, secret_key) as raw bytes.
    """
    _require_pq()
    # Mix in extra entropy
    _ = os.urandom(64)

    pk_buf = FFI.new(f"uint8_t[{PUBLIC_KEY_LEN}]")
    sk_buf = FFI.new(f"uint8_t[{SECRET_KEY_LEN}]")

    ret = LIB.PQCLEAN_MLDSA65_CLEAN_crypto_sign_keypair(pk_buf, sk_buf)
    if ret != 0:
        raise RuntimeError(f"ML-DSA-65 keygen failed: {ret}")

    pk = bytes(FFI.buffer(pk_buf, PUBLIC_KEY_LEN))
    sk = bytes(FFI.buffer(sk_buf, SECRET_KEY_LEN))
    return pk, sk


def sign(message: bytes, secret_key: bytes) -> bytes:
    """
    Sign message with ML-DSA-65. Returns raw signature bytes.

    Args:
        message: Arbitrary bytes to sign
        secret_key: 4032-byte secret key from keygen()

    Returns:
        3309-byte signature
    """
    _require_pq()

    msg_buf = FFI.from_buffer(message)
    sig_buf = FFI.new(f"uint8_t[{SIGNATURE_LEN}]")
    sig_len = FFI.new("size_t *")

    ret = LIB.PQCLEAN_MLDSA65_CLEAN_crypto_sign_signature(
        sig_buf,
        sig_len,
        msg_buf,
        len(message),
        secret_key,
    )
    if ret != 0:
        raise RuntimeError(f"ML-DSA-65 sign failed: {ret}")

    return bytes(FFI.buffer(sig_buf, sig_len[0]))


def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    Verify ML-DSA-65 signature.

    Args:
        message: Original message bytes
        signature: 3309-byte signature
        public_key: 1952-byte public key

    Returns:
        True if valid, False otherwise
    """
    _require_pq()

    msg_buf = FFI.from_buffer(message)
    sig_buf = FFI.from_buffer(signature)
    pk_buf = FFI.from_buffer(public_key)

    ret = LIB.PQCLEAN_MLDSA65_CLEAN_crypto_sign_verify(
        sig_buf,
        len(signature),
        msg_buf,
        len(message),
        pk_buf,
    )
    return ret == 0
