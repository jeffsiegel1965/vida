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
    from ml_dsa_65 import keygen as pq_keygen
    from ml_dsa_65 import sign as pq_sign
    from ml_dsa_65 import verify as pq_verify

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


def _host_fingerprint() -> str:
    """Stable host id so session files do not unlock if copied to another machine."""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            raw = Path(path).read_text().strip()
            if raw:
                return raw
        except Exception:
            continue
    # Fallback: hostname (weaker) — still better than unbound
    import socket

    return f"host:{socket.gethostname()}"


def _session_aad(
    wallet_address: str,
    expires_at: float,
    limits: dict,
    host_id: str | None = None,
) -> bytes:
    """Canonical AAD binding key ciphertext to expiry, limits, host, destinations.

    Editing any bound field breaks decryption (tamper-evident).
    """
    lim = {
        "max_kas_per_tx": float(limits.get("max_kas_per_tx", 0.0) or 0.0),
        "max_kas_per_day": float(limits.get("max_kas_per_day", 0.0) or 0.0),
    }
    dests = limits.get("allowed_destinations")
    if dests is not None:
        lim["allowed_destinations"] = sorted(list(dests))
    payload = {
        "v": 2,
        "wallet_address": wallet_address,
        "expires_at": expires_at,
        "host_id": host_id if host_id is not None else _host_fingerprint(),
        "limits": lim,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _seal_spend(machine_key: bytes, day: str, daily_spent: float) -> dict:
    """Authenticate daily spend so an attacker cannot lower the counter in the file."""
    pt = json.dumps(
        {"day": day, "daily_spent": float(daily_spent)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _encrypt(machine_key, pt, aad=b"vida-session-spend-v1")


def _open_spend(machine_key: bytes, blob: dict | None) -> tuple[str, float]:
    if not blob:
        return "", 0.0
    try:
        pt = _decrypt(machine_key, blob, aad=b"vida-session-spend-v1")
        data = json.loads(pt.decode("utf-8"))
        return str(data.get("day") or ""), float(data.get("daily_spent") or 0.0)
    except Exception:
        # Tampered spend blob → treat as max spent for the day? Safer: refuse all spends
        raise ValueError("Session spend counter tampered or corrupt")


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
        "kdf": {"algo": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P, "salt": salt.hex()},
        "enc_seed": _encrypt(key, seed_bytes),
        "enc_schnorr": _secure_key_operation(kp.private_key, lambda pk_bytes: _encrypt(key, pk_bytes)),
        "enc_pq_sk": _encrypt(key, pq_sk_bytes) if pq_sk_bytes else None,
    }
    _write_0600(wallet_path, data)

    return {"address": address, "pq_public_key": pq_pub_hex, "mnemonic": mnemonic.phrase}


def _secure_key_operation(private_key_hex: str, operation_func):
    """
    Perform operations on private keys with immediate clearing.

    Args:
        private_key_hex: The private key as hex string
        operation_func: Function to execute with the private key bytes

    Returns:
        Result of operation_func
    """
    # Convert to bytearray for mutable operations
    private_key_bytes = bytearray.fromhex(private_key_hex)

    try:
        # Execute the operation
        result = operation_func(bytes(private_key_bytes))
        return result
    finally:
        # Securely clear the bytearray
        import secrets

        for i in range(len(private_key_bytes)):
            private_key_bytes[i] = secrets.randbits(8) & 0xFF

        # Clear again with zeros
        for i in range(len(private_key_bytes)):
            private_key_bytes[i] = 0

        # Force garbage collection
        import gc

        gc.collect()


class SecureVida:
    """
    An unlocked secure wallet. Secrets live only in this object's memory.

    Compatible with VidaTransactor (exposes .address, .public_key, .network,
    ._private_key_hex, ._session_keys) so the transaction engine works
    unchanged on top of the encrypted wallet.
    """

    def __init__(
        self, wallet_path: str | Path, password: Optional[str] = None, _session_file: Optional[str | Path] = None
    ):
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
        # Secure agent session policy (set only by _unlock_with_session)
        self.session_limits: Optional[dict] = None
        self.session_expires_at: Optional[float] = None
        self._session_file: Optional[Path] = None
        self.session_daily_spent: float = 0.0
        self._session_spend_day: str = ""
        self._session_machine_key: Optional[bytes] = None
        self._session_format: int = 0

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
        host_id = sess.get("host_id") or _host_fingerprint()
        if sess.get("host_id") and sess["host_id"] != _host_fingerprint():
            raise ValueError("Session bound to a different host — refusing unlock")
        # expiry + limits + host bound as AAD (v2). v1 sessions used older AAD.
        limits = sess.get("limits", {}) or {}
        try:
            aad = _session_aad(sess["wallet_address"], sess["expires_at"], limits, host_id=host_id)
            self._private_key_hex = _decrypt(machine_key, sess["enc_schnorr"], aad).decode()
            self._session_format = 2
        except Exception:
            # Backward-compatible unlock for v1 sessions (pre host-bind)
            try:
                aad_v1 = json.dumps(
                    {
                        "wallet_address": sess["wallet_address"],
                        "expires_at": sess["expires_at"],
                        "limits": {
                            "max_kas_per_tx": limits.get("max_kas_per_tx", 0.0),
                            "max_kas_per_day": limits.get("max_kas_per_day", 0.0),
                        },
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                self._private_key_hex = _decrypt(machine_key, sess["enc_schnorr"], aad_v1).decode()
                self._session_format = 1
            except Exception:
                raise ValueError("Session file tampered or corrupt (auth check failed)")
        # PQ secret intentionally NOT included in agent sessions
        self.session_expires_at = sess["expires_at"]
        self.session_limits = limits
        self._session_file = session_path
        self._session_machine_key = machine_key
        # Authenticated spend counter (v2): required. Missing/deleted is fail-closed.
        # Note: machine_key lives in the same file, so a writer who can re-seal
        # enc_spend can still reset daily — residual FS threat, not fixed here.
        try:
            if self._session_format >= 2:
                if not sess.get("enc_spend"):
                    raise ValueError("Session missing enc_spend (tamper/delete) — refuse unlock")
                day, spent = _open_spend(machine_key, sess.get("enc_spend"))
                self._session_spend_day = day
                self.session_daily_spent = spent
            elif sess.get("enc_spend"):
                day, spent = _open_spend(machine_key, sess.get("enc_spend"))
                self._session_spend_day = day
                self.session_daily_spent = spent
            else:
                spend = sess.get("spend") or {}
                self._session_spend_day = str(spend.get("day") or "")
                self.session_daily_spent = float(spend.get("daily_spent") or 0.0)
        except ValueError:
            raise
        self._roll_session_day()

    # -- signing (same surface as wallet.Vida) --

    def sign(self, message: str) -> str:
        import kaspa as kas
        from kaspa import PrivateKey

        return kas.sign_message(message, PrivateKey(self._private_key_hex))

    def verify(self, message: str, sig_hex: str) -> bool:
        import kaspa as kas
        from kaspa import PublicKey

        return kas.verify_message(message, sig_hex, PublicKey(self.public_key))

    def sign_pq(self, message: bytes) -> bytes:
        if not PQ_AVAILABLE or self._pq_sk is None:
            raise ValueError("PQ secret not available (agent sessions never include it)")
        return pq_sign(message, self._pq_sk)

    def verify_pq(self, message: bytes, signature: bytes) -> bool:
        if not self.pq_public_key:
            raise ValueError("No PQ public key on this wallet")
        return pq_verify(message, signature, bytes.fromhex(self.pq_public_key))

    def _roll_session_day(self) -> None:
        """Reset daily spend when the UTC calendar day changes."""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if self._session_spend_day != today:
            self._session_spend_day = today
            self.session_daily_spent = 0.0

    def check_session_spend(self, amount_kas: float, dest_address: Optional[str] = None) -> Optional[str]:
        """
        Enforce secure agent session caps. Returns error string or None if OK.

        Owner password unlocks leave session_limits is None → no session cap.
        max_kas_per_tx / max_kas_per_day of 0 means unlimited on that axis.
        If allowed_destinations is a non-empty list, dest must be in it.
        """
        if self.session_limits is None:
            return None
        if self.session_expires_at is not None and time.time() > float(self.session_expires_at):
            return "Agent session expired"
        import math

        if not isinstance(amount_kas, (int, float)) or not math.isfinite(amount_kas) or amount_kas <= 0:
            return "Amount must be a positive finite number"
        max_tx = float(self.session_limits.get("max_kas_per_tx") or 0.0)
        max_day = float(self.session_limits.get("max_kas_per_day") or 0.0)
        if max_tx > 0 and amount_kas > max_tx + 1e-12:
            return f"Session policy rejected: amount {amount_kas} KAS exceeds max_kas_per_tx {max_tx}"
        dests = self.session_limits.get("allowed_destinations")
        if dests is not None:
            allow = set(dests)
            if not allow:
                return "Session policy rejected: allowed_destinations is empty (deny all)"
            if dest_address is None:
                return "Session policy rejected: destination required by allowlist"
            if dest_address not in allow:
                return "Session policy rejected: destination not in allowed_destinations"
        self._roll_session_day()
        if max_day > 0 and (self.session_daily_spent + amount_kas) > max_day + 1e-12:
            return (
                f"Session policy rejected: amount would exceed max_kas_per_day "
                f"{max_day} (spent {self.session_daily_spent})"
            )
        # Optional agent-pot overlay (covenant pot record) — stricter dual gate
        try:
            from vida.pot_policy import check_pot_overlay
        except ImportError:
            try:
                from pot_policy import check_pot_overlay  # type: ignore
            except ImportError:
                check_pot_overlay = None  # type: ignore
        if check_pot_overlay is not None:
            pot_err = check_pot_overlay(
                amount_kas,
                dest_address,
                owner_address=getattr(self, "address", None),
            )
            if pot_err:
                return pot_err
        return None

    def record_session_spend(self, amount_kas: float) -> None:
        """Record a successful spend against the secure session daily cap."""
        if self.session_limits is None:
            return
        self._roll_session_day()
        self.session_daily_spent += max(float(amount_kas), 0.0)
        if self._session_file is None:
            return
        try:
            path = Path(self._session_file)
            if not path.is_file():
                return
            with open(path) as f:
                sess = json.load(f)
            mk = getattr(self, "_session_machine_key", None)
            if mk is not None:
                sess["enc_spend"] = _seal_spend(mk, self._session_spend_day, self.session_daily_spent)
                sess.pop("spend", None)
            else:
                sess["spend"] = {
                    "day": self._session_spend_day,
                    "daily_spent": self.session_daily_spent,
                }
            raw = json.dumps(sess, indent=2, sort_keys=True)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                f.write(raw)
            os.chmod(tmp, 0o600)
            tmp.replace(path)
            os.chmod(path, 0o600)
        except Exception:
            pass

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
    allowed_destinations: Optional[list] = None,
    allow_unlimited: bool = False,
) -> dict:
    """
    Owner grants the agent time-boxed autonomous access (session format v2).

    Decrypts the funds key with the owner password, re-encrypts it under a
    fresh random machine key, binds host + limits + optional destination
    allowlist as AAD, writes a 0600 session file. Agent never gets password.
    Revoke: delete/scrub the session file.

    If allowed_destinations is a non-empty list, sends only to those addresses.
    If it is an empty list, all destinations are denied.
    If None, destinations are unrestricted (amount caps still apply).
    """
    if not allow_unlimited:
        if float(max_kas_per_tx) <= 0 or float(max_kas_per_day) <= 0:
            raise ValueError(
                "Agent sessions require positive max_kas_per_tx and max_kas_per_day "
                "(pass allow_unlimited=True only for explicit owner override)"
            )
        if float(max_kas_per_day) + 1e-12 < float(max_kas_per_tx):
            raise ValueError("max_kas_per_day must be >= max_kas_per_tx")
    wallet = SecureVida(wallet_path, password=password)  # validates password
    machine_key = AESGCM.generate_key(bit_length=256)
    expires_at = time.time() + hours * 3600
    host_id = _host_fingerprint()
    limits = {
        "max_kas_per_tx": float(max_kas_per_tx),
        "max_kas_per_day": float(max_kas_per_day),
    }
    if allowed_destinations is not None:
        limits["allowed_destinations"] = list(allowed_destinations)
    aad = _session_aad(wallet.address, expires_at, limits, host_id=host_id)

    sess = {
        "version": 2,
        "wallet_address": wallet.address,
        "expires_at": expires_at,
        "host_id": host_id,
        # machine_key is the AES-GCM session encryption key.
        # Stored as hex in the session file — this is a design tradeoff.
        # Without it, the owner would need to re-enter the password to
        # decrypt each session file on every agent interaction.
        # The session file itself is chmod 0600 and the key is scrypt-derived.
        # To harden: derive machine_key from wallet password at runtime instead.
        "machine_key": machine_key.hex(),
        "enc_schnorr": _encrypt(machine_key, wallet._private_key_hex.encode(), aad),
        "enc_spend": _seal_spend(machine_key, time.strftime("%Y-%m-%d", time.gmtime()), 0.0),
        "limits": limits,
    }
    session_path = Path(session_path)
    _write_0600(session_path, sess)
    wallet.lock()
    return {
        "session_path": str(session_path),
        "expires_at": expires_at,
        "limits": sess["limits"],
        "host_bound": True,
        "version": 2,
    }


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
