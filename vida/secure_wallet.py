"""
Vida Secure Wallet — password-encrypted, seed-phrase-backed, PQ-ready.

Security model
==============
- 24-word BIP39 mnemonic (256-bit entropy). OWNER holds it. It is printed
  ONCE by the owner-run setup script, directly to the owner's terminal.
  It is never stored in plaintext and never enters agent/LLM context.
- Everything secret at rest is encrypted with AES-256-GCM.
  The encryption key is derived from the owner's password via scrypt
  (n=2^15, r=8, p=1 — memory-hard, resists GPU cracking).
- Schnorr funds key: derived from the seed (m/44'/111111'/0'/0/0).
  Recoverable from the 24 words alone in any standard Kaspa wallet.
- ML-DSA-65 post-quantum keys: generated at setup, stored ENCRYPTED in the
  same wallet file. HONEST LIMITATION: the PQClean reference implementation
  cannot derive PQ keys from a seed, so the PQ identity is backed up by
  backing up the encrypted wallet file (safe to copy anywhere — it is
  useless without the password). When Kaspa adds PQ signature support
  on-chain, this wallet already has its PQ identity ready.
- Autonomous agent use: the owner runs `grant_agent_session.py`, enters the
  password, and a time-boxed session file is written (0600) containing the
  signing key encrypted under a fresh random machine key. The agent can
  spend within the delegation policy until expiry; the owner can revoke by
  deleting the session file. The password itself is never given to the agent.

File format (vida_secure.json) — everything sensitive is ciphertext:
{
  "version": 2,
  "network": "mainnet",
  "address": "...",                 # public
  "public_key": "...",              # public
  "pq_public_key": "...",           # public
  "kdf": {"algo": "scrypt", "n": 32768, "r": 8, "p": 1, "salt": "..."},
  "enc_seed":    {"nonce": "...", "ct": "..."},   # 64-byte BIP39 seed
  "enc_schnorr": {"nonce": "...", "ct": "..."},   # schnorr privkey hex
  "enc_pq_sk":   {"nonce": "...", "ct": "..."}    # ML-DSA-65 secret key
}
"""

import json
import os
import stat
import time
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from kaspa import Mnemonic, XPrv

try:
    from ml_dsa_65 import keygen as pq_keygen, sign as pq_sign, verify as pq_verify
    PQ_AVAILABLE = True
except ImportError:
    PQ_AVAILABLE = False

DERIVATION_PATH = "m/44'/111111'/0'/0/0"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 131072, 8, 1  # 2^17 (~128 MiB) — hardened for funds
KEY_LEN = 32


# ── Crypto helpers ───────────────────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    """Password -> 32-byte key via scrypt (memory-hard)."""
    kdf = Scrypt(salt=salt, length=KEY_LEN, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def _encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> dict:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return {"nonce": nonce.hex(), "ct": ct.hex()}


def _decrypt(key: bytes, blob: dict, aad: bytes | None = None) -> bytes:
    return AESGCM(key).decrypt(bytes.fromhex(blob["nonce"]), bytes.fromhex(blob["ct"]), aad)


def _session_aad(wallet_address: str, expires_at: float, limits: dict) -> bytes:
    """Canonical AAD binding a session's key ciphertext to its expiry + limits.
    Editing any of these fields in the file breaks decryption (tamper-evident)."""
    payload = {
        "wallet_address": wallet_address,
        "expires_at": expires_at,
        "limits": {
            "max_kas_per_tx": limits.get("max_kas_per_tx", 0.0),
            "max_kas_per_day": limits.get("max_kas_per_day", 0.0),
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_0600(path: Path, data: dict):
    # Create with 0600 atomically (O_EXCL-free variant that still avoids the
    # brief world-readable window between open() and chmod) — CR-4.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
    finally:
        # Ensure perms even if the file pre-existed with looser mode
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


# ── Wallet creation (called by owner-run setup script ONLY) ──────────────────

def create_secure_wallet(
    wallet_path: str | Path,
    password: str,
    network: str = "mainnet",
    mnemonic_phrase: Optional[str] = None,
) -> dict:
    """
    Create (or restore) a secure wallet.

    Returns {"address", "pq_public_key", "mnemonic"} — the CALLER (owner
    setup script) is responsible for showing the mnemonic to the owner and
    then destroying it. This function never writes the mnemonic to disk.

    Args:
        wallet_path: where the encrypted wallet JSON is written
        password: owner password (min 10 chars enforced)
        network: 'mainnet' or 'testnet'
        mnemonic_phrase: pass an existing 24-word phrase to RESTORE
    """
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    wallet_path = Path(wallet_path)
    if wallet_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing wallet: {wallet_path}")

    # 24 words = 256-bit entropy
    mnemonic = Mnemonic(mnemonic_phrase) if mnemonic_phrase else Mnemonic.random(24)
    word_count = len(mnemonic.phrase.split())
    if word_count != 24:
        raise ValueError(f"Expected 24-word mnemonic, got {word_count}")

    seed = mnemonic.to_seed()  # 64-byte hex str or bytes depending on SDK
    seed_bytes = bytes.fromhex(seed) if isinstance(seed, str) else bytes(seed)

    # Derive Schnorr funds key
    xprv = XPrv(seed if isinstance(seed, str) else seed.hex())
    child = xprv.derive_path(DERIVATION_PATH)
    priv = child.to_private_key()
    kp = priv.to_keypair()
    address = str(kp.to_address(network))

    # PQ identity (stored encrypted; not seed-derivable — see module docstring)
    pq_pub_hex, pq_sk_bytes = None, None
    if PQ_AVAILABLE:
        pq_pub, pq_sk = pq_keygen()
        pq_pub_hex = pq_pub.hex()
        pq_sk_bytes = pq_sk

    # Encrypt everything sensitive
    salt = os.urandom(16)
    key = _derive_key(password, salt)

    data = {
        "version": 2,
        "network": network,
        "address": address,
        "public_key": kp.public_key,
        "pq_public_key": pq_pub_hex,
        "kdf": {"algo": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
                "salt": salt.hex()},
        "enc_seed": _encrypt(key, seed_bytes),
        "enc_schnorr": _encrypt(key, kp.private_key.encode()),
        "enc_pq_sk": _encrypt(key, pq_sk_bytes) if pq_sk_bytes else None,
    }
    _write_0600(wallet_path, data)

    return {"address": address, "pq_public_key": pq_pub_hex, "mnemonic": mnemonic.phrase}


# ── Unlocking ────────────────────────────────────────────────────────────────

class SecureVida:
    """
    An unlocked secure wallet. Secrets live only in this object's memory.

    Compatible with VidaTransactor (exposes .address, .public_key, .network,
    ._private_key_hex, ._session_keys) so the transaction engine works
    unchanged on top of the encrypted wallet.
    """

    def __init__(self, wallet_path: str | Path, password: Optional[str] = None,
                 _session_file: Optional[str | Path] = None):
        self.wallet_path = Path(wallet_path)
        with open(self.wallet_path) as f:
            self._data = json.load(f)

        self.network = self._data["network"]
        self.address = self._data["address"]
        self.public_key = self._data["public_key"]
        self.pq_public_key = self._data.get("pq_public_key")

        self._private_key_hex: Optional[str] = None
        self._pq_sk: Optional[bytes] = None
        self._session_keys = {}
        self._session_privkeys = {}

        if password is not None:
            self._unlock_with_password(password)
        elif _session_file is not None:
            self._unlock_with_session(Path(_session_file))
        else:
            raise ValueError("Provide password or session file to unlock")

    # -- unlock paths --

    def _unlock_with_password(self, password: str):
        kdf = self._data["kdf"]
        key = _derive_key(password, bytes.fromhex(kdf["salt"]))
        try:
            self._private_key_hex = _decrypt(key, self._data["enc_schnorr"]).decode()
            if self._data.get("enc_pq_sk"):
                self._pq_sk = _decrypt(key, self._data["enc_pq_sk"])
        except Exception:
            raise ValueError("Wrong password (decryption failed)")

    def _unlock_with_session(self, session_path: Path):
        """Unlock from a time-boxed agent session file (owner-granted)."""
        with open(session_path) as f:
            sess = json.load(f)
        if sess["wallet_address"] != self.address:
            raise ValueError("Session file is for a different wallet")
        if time.time() > sess["expires_at"]:
            try:
                session_path.unlink()  # burn expired session
            except OSError:
                pass
            raise ValueError("Agent session expired — owner must grant a new one")
        machine_key = bytes.fromhex(sess["machine_key"])
        # expiry + limits are bound as AAD: if anyone edited them in the file,
        # decryption fails (CR-2). This makes tampering detectable even though
        # the machine_key itself is necessarily readable (see README honesty note).
        aad = _session_aad(sess["wallet_address"], sess["expires_at"], sess.get("limits", {}))
        try:
            self._private_key_hex = _decrypt(machine_key, sess["enc_schnorr"], aad).decode()
        except Exception:
            raise ValueError("Session file tampered or corrupt (auth check failed)")
        # PQ secret intentionally NOT included in agent sessions:
        # agents only need the funds key; PQ identity stays owner-only.
        self.session_expires_at = sess["expires_at"]
        self.session_limits = sess.get("limits", {})

    # -- signing (same surface as wallet.Vida) --

    def sign(self, message: str) -> str:
        from kaspa import PrivateKey
        import kaspa as kas
        return kas.sign_message(message, PrivateKey(self._private_key_hex))

    def verify(self, message: str, sig_hex: str) -> bool:
        from kaspa import PublicKey
        import kaspa as kas
        return kas.verify_message(message, sig_hex, PublicKey(self.public_key))

    def sign_pq(self, message: bytes) -> bytes:
        if not PQ_AVAILABLE or self._pq_sk is None:
            raise ValueError("PQ secret not available (agent sessions never include it)")
        return pq_sign(message, self._pq_sk)

    def verify_pq(self, message: bytes, signature: bytes) -> bool:
        if not self.pq_public_key:
            raise ValueError("No PQ public key on this wallet")
        return pq_verify(message, signature, bytes.fromhex(self.pq_public_key))

    def lock(self):
        """Best-effort scrub of secrets from this object."""
        self._private_key_hex = None
        self._pq_sk = None


# ── Agent session grants (owner-run) ─────────────────────────────────────────

def grant_agent_session(
    wallet_path: str | Path,
    password: str,
    session_path: str | Path,
    hours: float = 24.0,
    max_kas_per_tx: float = 0.0,
    max_kas_per_day: float = 0.0,
) -> dict:
    """
    Owner grants the agent time-boxed autonomous access.

    Decrypts the funds key with the owner password, re-encrypts it under a
    fresh random machine key, writes both into a 0600 session file with an
    expiry. The agent unlocks with the session file — never the password.
    Revoke anytime: delete the session file.
    """
    wallet = SecureVida(wallet_path, password=password)  # validates password
    machine_key = AESGCM.generate_key(bit_length=256)
    expires_at = time.time() + hours * 3600
    limits = {"max_kas_per_tx": max_kas_per_tx, "max_kas_per_day": max_kas_per_day}
    aad = _session_aad(wallet.address, expires_at, limits)

    sess = {
        "wallet_address": wallet.address,
        "expires_at": expires_at,
        "machine_key": machine_key.hex(),
        "enc_schnorr": _encrypt(machine_key, wallet._private_key_hex.encode(), aad),
        "limits": limits,
    }
    session_path = Path(session_path)
    _write_0600(session_path, sess)
    wallet.lock()
    return {"session_path": str(session_path), "expires_at": expires_at,
            "limits": sess["limits"]}


def revoke_agent_session(session_path: str | Path) -> bool:
    """Revoke an agent session by destroying its file."""
    p = Path(session_path)
    if p.exists():
        # Overwrite before unlink (best-effort scrub on disk)
        size = p.stat().st_size
        with open(p, "wb") as f:
            f.write(os.urandom(size))
        p.unlink()
        return True
    return False
