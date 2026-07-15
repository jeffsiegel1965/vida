"""
Owner-only TAO account provisioning.

Encrypts cold/hot private keys + optional ML-DSA-65 PQ identity at rest with
password-derived scrypt + AES-GCM.
Agent-facing code must only use TaoAccountRecord.to_public_dict().
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .accounts import TaoAccountRecord, TaoAccountStore
from .derive import DERIVATION_METHOD, derive_tao_keys, wipe_secrets
from .pq import PQ_AVAILABLE, PQ_SCHEME, generate_pq_identity, sign_message, verify_message

SCRYPT_N, SCRYPT_R, SCRYPT_P = 131072, 8, 1  # match Vida secure_wallet hardness
KEY_LEN = 32


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_LEN, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def _encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> dict[str, str]:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return {"nonce": nonce.hex(), "ct": ct.hex()}


def _decrypt(key: bytes, blob: dict[str, str], aad: bytes | None = None) -> bytes:
    return AESGCM(key).decrypt(
        bytes.fromhex(blob["nonce"]), bytes.fromhex(blob["ct"]), aad
    )


def provision_tao_account(
    *,
    wallet_id: str,
    mnemonic: str,
    password: str,
    network: str,
    store: TaoAccountStore,
    ss58_prefix: int = 42,
    overwrite: bool = False,
    with_pq: bool = True,
) -> dict[str, Any]:
    """
    Derive TAO keys from mnemonic, generate PQ identity, encrypt, save.

    Returns public-only result (never private keys, mnemonic, or PQ secret).
    """
    if not password:
        return {"ok": False, "error": "password required to encrypt cold material"}
    if store.exists(wallet_id) and not overwrite:
        return {
            "ok": False,
            "error": f"account already exists for wallet_id={wallet_id} (pass overwrite=True)",
        }

    try:
        keys = derive_tao_keys(mnemonic, ss58_prefix=ss58_prefix)
    except Exception as e:
        return {"ok": False, "error": f"derivation failed: {type(e).__name__}: {e}"}

    pq_pub_hex = None
    enc_pq = None
    pq_sk: bytes | None = None
    pq_info: dict[str, Any] = {"pq_available": PQ_AVAILABLE, "pq_ready": False}
    if with_pq:
        gen = generate_pq_identity()
        if gen.get("ok"):
            pq_pub_hex = gen["pq_public_key_hex"]
            pq_sk = gen["pq_secret_key_bytes"]
        elif not PQ_AVAILABLE:
            pq_info["pq_warning"] = gen.get("error", "PQ unavailable")
        else:
            wipe_secrets(keys)
            return {"ok": False, "error": gen.get("error", "PQ keygen failed")}

    salt = os.urandom(16)
    try:
        key = _derive_key(password, salt)
        secret_payload = json.dumps(
            {
                "cold_private_hex": keys.cold_private_hex,
                "hot_private_hex": keys.hot_private_hex,
                "public_key_hex": keys.public_key_hex,
                "hot_public_key_hex": keys.hot_public_key_hex,
                "hotkey_ss58": keys.hotkey_ss58,
            },
            sort_keys=True,
        ).encode("utf-8")
        aad = f"vida-tao-v1|{wallet_id}|{network}|{keys.ss58_address}".encode("utf-8")
        enc = _encrypt(key, secret_payload, aad=aad)
        enc_blob = {
            "kdf": {
                "algo": "scrypt",
                "n": SCRYPT_N,
                "r": SCRYPT_R,
                "p": SCRYPT_P,
                "salt": salt.hex(),
            },
            "cipher": "aes-256-gcm",
            "aad": aad.decode("utf-8"),
            "enc": enc,
        }
        if pq_pub_hex is not None and pq_sk is not None:
            pq_aad = f"vida-tao-pq-v1|{wallet_id}|{network}|{keys.ss58_address}|{PQ_SCHEME}".encode(
                "utf-8"
            )
            enc_pq = {
                "kdf_salt": salt.hex(),  # same password-derived key
                "cipher": "aes-256-gcm",
                "aad": pq_aad.decode("utf-8"),
                "enc": _encrypt(key, pq_sk, aad=pq_aad),
                "scheme": PQ_SCHEME,
            }
            pq_info = {
                "pq_available": True,
                "pq_ready": True,
                "pq_scheme": PQ_SCHEME,
                "pq_on_chain": False,
            }
            pq_sk = b"\x00" * len(pq_sk)
    finally:
        wipe_secrets(keys)

    rec = TaoAccountRecord(
        wallet_id=wallet_id,
        network=network,
        ss58_address=keys.ss58_address,
        ss58_prefix=ss58_prefix,
        provisioned=True,
        derivation_method=DERIVATION_METHOD,
        enc_cold_material=enc_blob,
        pq_public_key=pq_pub_hex,
        enc_pq_sk=enc_pq,
        meta={
            "hotkey_ss58": keys.hotkey_ss58,
            "public_key_hex": keys.public_key_hex,
            "hot_public_key_hex": keys.hot_public_key_hex,
            "pq_scheme": PQ_SCHEME if pq_pub_hex else None,
        },
    )
    path = store.save(rec)
    return {
        "ok": True,
        "wallet_id": wallet_id,
        "network": network,
        "ss58_address": rec.ss58_address,
        "hotkey_ss58": keys.hotkey_ss58,
        "derivation_method": DERIVATION_METHOD,
        "path": str(path),
        "public": rec.to_public_dict(),
        **pq_info,
    }


def unlock_tao_secrets(
    record: TaoAccountRecord,
    password: str,
    *,
    include_pq: bool = True,
) -> dict[str, Any]:
    """
    Owner-only unlock of encrypted cold/hot material (+ PQ secret if present).
    Do not call from agent session paths for PQ — sessions must never get pq_sk.
    """
    if not record.enc_cold_material:
        return {"ok": False, "error": "no encrypted material on record"}
    blob = record.enc_cold_material
    try:
        kdf = blob["kdf"]
        salt = bytes.fromhex(kdf["salt"])
        key = _derive_key(password, salt)
        aad = blob.get("aad", "").encode("utf-8") or None
        pt = _decrypt(key, blob["enc"], aad=aad)
        data = json.loads(pt.decode("utf-8"))
        out: dict[str, Any] = {"ok": True, "secrets": data}
        if include_pq and record.enc_pq_sk and record.pq_public_key:
            pq_blob = record.enc_pq_sk
            pq_aad = pq_blob.get("aad", "").encode("utf-8") or None
            # Prefer salt stored on pq blob; fallback to cold kdf salt
            pq_salt_hex = pq_blob.get("kdf_salt") or salt.hex()
            pq_key = _derive_key(password, bytes.fromhex(pq_salt_hex))
            pq_sk = _decrypt(pq_key, pq_blob["enc"], aad=pq_aad)
            out["pq_secret_key_bytes"] = pq_sk
            out["pq_public_key"] = record.pq_public_key
            out["pq_scheme"] = pq_blob.get("scheme") or PQ_SCHEME
        return out
    except Exception as e:
        return {"ok": False, "error": f"unlock failed: {type(e).__name__}: {e}"}


def ensure_tao_pq_identity(
    *,
    wallet_id: str,
    password: str,
    store: TaoAccountStore,
) -> dict[str, Any]:
    """
    Upgrade an existing provisioned account with ML-DSA-65 if missing.
    Owner-only. Does not change ss58 funds keys.
    """
    rec = store.load(wallet_id)
    if rec is None or not rec.provisioned:
        return {"ok": False, "error": "account not provisioned"}
    if rec.pq_public_key and rec.enc_pq_sk:
        return {
            "ok": True,
            "already": True,
            "pq_ready": True,
            "pq_public_key": rec.pq_public_key,
            "pq_on_chain": False,
        }
    if not PQ_AVAILABLE:
        return {"ok": False, "error": "ML-DSA-65 not available in this environment"}

    # Verify password against cold material first
    unlocked = unlock_tao_secrets(rec, password, include_pq=False)
    if not unlocked.get("ok"):
        return {"ok": False, "error": unlocked.get("error", "bad password")}

    gen = generate_pq_identity()
    if not gen.get("ok"):
        return {"ok": False, "error": gen.get("error", "PQ keygen failed")}

    blob = rec.enc_cold_material or {}
    salt = bytes.fromhex(blob["kdf"]["salt"])
    key = _derive_key(password, salt)
    pq_sk = gen["pq_secret_key_bytes"]
    pq_pub = gen["pq_public_key_hex"]
    pq_aad = f"vida-tao-pq-v1|{wallet_id}|{rec.network}|{rec.ss58_address}|{PQ_SCHEME}".encode(
        "utf-8"
    )
    rec.pq_public_key = pq_pub
    rec.enc_pq_sk = {
        "kdf_salt": salt.hex(),
        "cipher": "aes-256-gcm",
        "aad": pq_aad.decode("utf-8"),
        "enc": _encrypt(key, pq_sk, aad=pq_aad),
        "scheme": PQ_SCHEME,
    }
    rec.meta = dict(rec.meta or {})
    rec.meta["pq_scheme"] = PQ_SCHEME
    path = store.save(rec)
    pq_sk = b"\x00" * len(pq_sk)
    return {
        "ok": True,
        "upgraded": True,
        "pq_ready": True,
        "pq_public_key": pq_pub,
        "pq_scheme": PQ_SCHEME,
        "pq_on_chain": False,
        "path": str(path),
        "public": rec.to_public_dict(),
    }


def owner_sign_pq(
    record: TaoAccountRecord,
    password: str,
    message: bytes,
) -> dict[str, Any]:
    """Owner-only: unlock PQ secret, sign message, do not retain sk."""
    unlocked = unlock_tao_secrets(record, password, include_pq=True)
    if not unlocked.get("ok"):
        return unlocked
    sk = unlocked.get("pq_secret_key_bytes")
    pub = unlocked.get("pq_public_key") or record.pq_public_key
    if not sk or not pub:
        return {"ok": False, "error": "no PQ identity on account"}
    try:
        sig = sign_message(message, sk)
        ok = verify_message(message, sig, pub)
        return {
            "ok": True,
            "signature_hex": sig.hex(),
            "pq_public_key": pub,
            "scheme": PQ_SCHEME,
            "verified": ok,
            "pq_on_chain": False,
        }
    finally:
        # best-effort scrub
        if isinstance(sk, (bytes, bytearray)):
            ba = bytearray(sk)
            for i in range(len(ba)):
                ba[i] = 0
