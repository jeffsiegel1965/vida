"""
TAO agent sessions — Kaspa-style time-boxed unlock without owner password.

Owner runs grant with password once → 0600 session file holds coldkey material
re-encrypted under a random machine key + expiry + limits.

Agent uses the session file only. Revoke = scrub + delete file.
Mnemonic/password never go to the agent.
"""

from __future__ import annotations

import json
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .accounts import TaoAccountStore
from .provision import unlock_tao_secrets

SESSION_VERSION = 2


def _host_fingerprint() -> str:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            raw = Path(path).read_text().strip()
            if raw:
                return raw
        except Exception:
            continue
    import socket
    return f"host:{socket.gethostname()}"


def _seal_spend(machine_key: bytes, day: str, daily_spent: float) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pt = json.dumps({"day": day, "daily_spent": float(daily_spent)}, sort_keys=True, separators=(",", ":")).encode()
    nonce = os.urandom(12)
    ct = AESGCM(machine_key).encrypt(nonce, pt, b"vida-tao-session-spend-v1")
    return {"nonce": nonce.hex(), "ct": ct.hex()}


def _session_aad(
    ss58_address: str,
    wallet_id: str,
    expires_at: float,
    limits: dict[str, Any],
    host_id: str | None = None,
) -> bytes:
    # Canonical binding so tampering expiry/limits/host invalidates decrypt
    payload = json.dumps(
        {
            "v": 2,
            "ss58": ss58_address,
            "wallet_id": wallet_id,
            "expires_at": expires_at,
            "host_id": host_id or _host_fingerprint(),
            "limits": limits,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"vida-tao-session-v2|{payload}".encode("utf-8")


def _write_0600(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _encrypt(key: bytes, plaintext: bytes, aad: bytes) -> dict[str, str]:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return {"nonce": nonce.hex(), "ct": ct.hex()}


def _decrypt(key: bytes, blob: dict[str, str], aad: bytes) -> bytes:
    return AESGCM(key).decrypt(bytes.fromhex(blob["nonce"]), bytes.fromhex(blob["ct"]), aad)


def grant_tao_agent_session(
    *,
    store: TaoAccountStore,
    wallet_id: str,
    password: str,
    session_path: str | Path,
    hours: float = 24.0,
    mode: str = "FULL",
    max_tao_per_tx: float = 0.0,
    max_tao_per_day: float = 0.0,
    threshold: float = 0.0,
    allowed_subnets: Optional[list[int]] = None,
    allowed_actions: Optional[list[str]] = None,
    allowed_destinations: Optional[list[str]] = None,
    allow_unlimited: bool = False,
    scope: str = "ALL",
    allow_any_dest: bool = False,
    allow_long_session: bool = False,
) -> dict[str, Any]:
    """
    Owner-only: unlock coldkey with password, wrap into agent session file.

    scope: ALL | STAKE_ONLY | TRANSFER_ONLY (maps to allowed_actions).
    Transfers under a session require allowed_destinations unless allow_any_dest.
    hours capped at 24 unless allow_long_session.
    """
    rec = store.load(wallet_id)
    if rec is None or not rec.provisioned:
        return {"ok": False, "error": f"wallet_id={wallet_id} not provisioned"}

    try:
        from .paths import actions_for_scope
        scope_actions = actions_for_scope(scope)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    hours = float(hours)
    if not allow_long_session and hours > 24.0 + 1e-9:
        return {"ok": False, "error": "hours > 24 requires allow_long_session=True"}

    if not allow_unlimited:
        if float(max_tao_per_tx) <= 0 or float(max_tao_per_day) <= 0:
            return {
                "ok": False,
                "error": (
                    "Agent sessions require positive max_tao_per_tx and max_tao_per_day "
                    "(allow_unlimited=True for explicit override only)"
                ),
            }
        if float(max_tao_per_day) + 1e-12 < float(max_tao_per_tx):
            return {"ok": False, "error": "max_tao_per_day must be >= max_tao_per_tx"}

    unlocked = unlock_tao_secrets(rec, password, include_pq=False)  # never put PQ sk in agent sessions
    if not unlocked.get("ok"):
        return {"ok": False, "error": unlocked.get("error", "password unlock failed")}

    secrets = unlocked["secrets"]
    cold_hex = secrets.get("cold_private_hex") or ""
    hot_hex = secrets.get("hot_private_hex") or ""
    if not cold_hex:
        return {"ok": False, "error": "no cold_private_hex in vault"}

    expires_at = time.time() + float(hours) * 3600.0
    limits = {
        "mode": (mode or "FULL").upper(),
        "max_tao_per_tx": float(max_tao_per_tx),
        "max_tao_per_day": float(max_tao_per_day),
        "threshold": float(threshold),
        "allowed_subnets": list(allowed_subnets) if allowed_subnets is not None else None,
        "allowed_actions": list(allowed_actions)
        if allowed_actions is not None
        else list(scope_actions),
        "scope": (scope or "ALL").upper().replace("-", "_"),
        "allow_any_dest": bool(allow_any_dest),
    }
    # Transfer safety: require dest allowlist for agent sessions unless explicit any-dest
    acts = set(limits["allowed_actions"])
    if "transfer" in acts and not allow_any_dest:
        if not allowed_destinations:
            return {
                "ok": False,
                "error": (
                    "transfer-capable sessions require allowed_destinations "
                    "(or allow_any_dest=True for open P2P — dangerous)"
                ),
            }
        limits["allowed_destinations"] = list(allowed_destinations)
    elif allowed_destinations is not None:
        limits["allowed_destinations"] = list(allowed_destinations)
    machine_key = AESGCM.generate_key(bit_length=256)
    host_id = _host_fingerprint()
    aad = _session_aad(rec.ss58_address, wallet_id, expires_at, limits, host_id=host_id)
    secret_blob = json.dumps(
        {
            "cold_private_hex": cold_hex,
            "hot_private_hex": hot_hex,
            "hotkey_ss58": secrets.get("hotkey_ss58")
            or (rec.meta or {}).get("hotkey_ss58")
            or "",
        },
        sort_keys=True,
    ).encode("utf-8")

    sess = {
        "version": SESSION_VERSION,
        "plugin": "tao",
        "wallet_id": wallet_id,
        "ss58_address": rec.ss58_address,
        "network": rec.network,
        "expires_at": expires_at,
        "host_id": host_id,
        "machine_key": machine_key.hex(),
        "enc_secrets": _encrypt(machine_key, secret_blob, aad),
        "enc_spend": _seal_spend(machine_key, time.strftime("%Y-%m-%d", time.gmtime()), 0.0),
        "limits": limits,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = Path(session_path)
    _write_0600(path, sess)

    # wipe sensitive locals best-effort
    secrets.clear()
    cold_hex = ""
    hot_hex = ""

    return {
        "ok": True,
        "session_path": str(path),
        "wallet_id": wallet_id,
        "ss58_address": rec.ss58_address,
        "expires_at": expires_at,
        "expires_at_human": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(expires_at)),
        "limits": limits,
        "note": "Agent unlocks with this session file only — no owner password",
    }


def load_tao_session_secrets(session_path: str | Path) -> dict[str, Any]:
    """
    Agent path: load coldkey material from session if not expired.
    Burns file if expired.
    """
    path = Path(session_path)
    if not path.is_file():
        return {"ok": False, "error": "session file missing", "session_revoked": True}

    try:
        sess = json.loads(path.read_text())
    except Exception as e:
        return {"ok": False, "error": f"session unreadable: {e}"}

    expires_at = float(sess.get("expires_at") or 0)
    if time.time() >= expires_at:
        revoke_tao_agent_session(path)
        return {"ok": False, "error": "session expired", "session_revoked": True}

    if sess.get("host_id") and sess["host_id"] != _host_fingerprint():
        return {"ok": False, "error": "session bound to a different host", "session_revoked": True}

    limits = sess.get("limits") or {}
    host_id = sess.get("host_id") or _host_fingerprint()
    aad = _session_aad(
        sess.get("ss58_address", ""),
        sess.get("wallet_id", ""),
        expires_at,
        limits,
        host_id=host_id,
    )
    try:
        machine_key = bytes.fromhex(sess["machine_key"])
        pt = _decrypt(machine_key, sess["enc_secrets"], aad)
        secrets = json.loads(pt.decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"session decrypt failed (tamper?): {type(e).__name__}"}

    today = time.strftime("%Y-%m-%d", time.gmtime())
    daily_spent = 0.0
    if not sess.get("enc_spend"):
        return {
            "ok": False,
            "error": "session missing enc_spend (tamper/delete) — refuse load",
        }
    try:
        sp = AESGCM(machine_key).decrypt(
            bytes.fromhex(sess["enc_spend"]["nonce"]),
            bytes.fromhex(sess["enc_spend"]["ct"]),
            b"vida-tao-session-spend-v1",
        )
        spend = json.loads(sp.decode())
        if spend.get("day") == today:
            daily_spent = float(spend.get("daily_spent") or 0)
        # if day rolled, daily_spent stays 0 (counter resets)
    except Exception as e:
        return {"ok": False, "error": f"enc_spend invalid (tamper?): {type(e).__name__}"}

    return {
        "ok": True,
        "wallet_id": sess.get("wallet_id"),
        "ss58_address": sess.get("ss58_address"),
        "network": sess.get("network"),
        "expires_at": expires_at,
        "limits": limits,
        "secrets": secrets,
        "session_path": str(path),
        "daily_spent": daily_spent,
        "spend_day": today,
    }


# ── Cross-process session locking ──────────────────────────────────────────
# record_tao_session_spend() and load_tao_session_secrets() are separated by
# the entire broadcast in plugin.py (stake at L330-382, transfer at L524-596).
# Without a lock two agent processes sharing a TAO session file each read the
# same stale enc_spend counter and both pass the daily cap.
# Fix: reserve-then-record pattern with fcntl.flock, matching the Kaspa path.


def _tao_lock_path(session_path: str | Path) -> Path:
    return Path(str(session_path) + ".lock")


@contextmanager
def tao_session_lock(session_path: str | Path, timeout: float = 10.0):
    """Exclusive fcntl.flock on the session lockfile."""
    import fcntl

    lp = _tao_lock_path(session_path)
    lp.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lp), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.time() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() >= deadline:
                    raise RuntimeError(
                        f"Timed out acquiring TAO session lock {lp} after {timeout}s"
                    )
                time.sleep(0.01)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _read_tao_spend_from_disk(path: Path) -> tuple[str, float]:
    """Return (day, daily_spent) from the TAO session file.

    Returns ("", 0.0) if the file is missing, the counter hasn't started,
    or the day has rolled. Raises on decryption failure (tamper).
    """
    if not path.is_file():
        return ("", 0.0)
    sess = json.loads(path.read_text())
    mk = bytes.fromhex(sess["machine_key"])
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if not sess.get("enc_spend"):
        return (today, 0.0)
    sp = AESGCM(mk).decrypt(
        bytes.fromhex(sess["enc_spend"]["nonce"]),
        bytes.fromhex(sess["enc_spend"]["ct"]),
        b"vida-tao-session-spend-v1",
    )
    spend = json.loads(sp.decode())
    if spend.get("day") != today:
        return (today, 0.0)
    return (today, float(spend.get("daily_spent") or 0.0))


def reserve_tao_session_spend(
    session_path: str | Path, amount: float, daily_limit: float
) -> dict[str, Any]:
    """Atomically check the TAO session daily cap and reserve the amount.

    Returns {"ok": True} if the spend fits in the cap, or
    {"ok": False, "error": ...} if it would exceed.
    The reservation is published to disk so sibling processes observe it.
    Caller MUST later call record_tao_session_spend() on success or
    release_tao_session_spend() on failure.

    This is the concurrency-safe entry point. Never read daily_spent from
    load_tao_session_secrets() and check it yourself.
    """
    path = Path(session_path)
    with tao_session_lock(path):
        day, spent = _read_tao_spend_from_disk(path)
        if daily_limit > 0 and (spent + amount) > daily_limit + 1e-12:
            return {
                "ok": False,
                "error": (
                    f"Session policy rejected: amount {amount} would exceed "
                    f"max_tao_per_day {daily_limit} (spent {spent})"
                ),
            }
        # Publish the reservation so sibling processes see it.
        _write_tao_spend_encrypted(path, day, spent + amount)
        return {"ok": True, "reserved": amount, "day": day, "spent_before": spent}


def release_tao_session_spend(
    session_path: str | Path, amount: float
) -> dict[str, Any]:
    """Release a reservation that was never committed (failed broadcast)."""
    path = Path(session_path)
    with tao_session_lock(path):
        day, spent = _read_tao_spend_from_disk(path)
        new_spent = max(spent - amount, 0.0)
        _write_tao_spend_encrypted(path, day, new_spent)
        return {"ok": True, "day": day, "daily_spent": new_spent}


def _write_tao_spend_encrypted(path: Path, day: str, daily_spent: float) -> None:
    """Persist enc_spend. Must be called while holding tao_session_lock()."""
    if not path.is_file():
        raise FileNotFoundError(f"TAO session missing: {path}")
    import secrets as _sec

    sess = json.loads(path.read_text())
    mk = bytes.fromhex(sess["machine_key"])
    nonce = _sec.token_bytes(12)
    ct = AESGCM(mk).encrypt(
        nonce,
        json.dumps({"day": day, "daily_spent": daily_spent}).encode(),
        b"vida-tao-session-spend-v1",
    )
    sess["enc_spend"] = {"nonce": nonce.hex(), "ct": ct.hex()}
    _write_0600(path, sess)


def record_tao_session_spend(session_path: str | Path, amount: float) -> dict[str, Any]:
    """After a successful session-funded action: commit the daily spend.

    Holds an exclusive flock across the read-modify-write so concurrent
    processes cannot both pass the cap.
    """
    path = Path(session_path)
    if not path.is_file():
        return {"ok": False, "error": "session missing"}
    with tao_session_lock(path):
        day, spent = _read_tao_spend_from_disk(path)
        spent += float(amount)
        _write_tao_spend_encrypted(path, day, spent)
        return {"ok": True, "daily_spent": spent, "day": day}


def revoke_tao_agent_session(session_path: str | Path) -> bool:
    """Scrub + delete session file."""
    p = Path(session_path)
    if not p.exists():
        return False
    try:
        size = p.stat().st_size
        with open(p, "wb") as f:
            f.write(os.urandom(max(size, 64)))
        p.unlink()
        return True
    except Exception:
        try:
            p.unlink()
            return True
        except Exception:
            return False


def public_session_info(session_path: str | Path) -> dict[str, Any]:
    """Safe metadata for agents (no secrets)."""
    path = Path(session_path)
    if not path.is_file():
        return {"ok": False, "active": False, "error": "no session"}
    try:
        sess = json.loads(path.read_text())
    except Exception as e:
        return {"ok": False, "active": False, "error": str(e)}
    exp = float(sess.get("expires_at") or 0)
    active = time.time() < exp
    return {
        "ok": True,
        "active": active,
        "wallet_id": sess.get("wallet_id"),
        "ss58_address": sess.get("ss58_address"),
        "network": sess.get("network"),
        "expires_at": exp,
        "limits": sess.get("limits"),
        "session_revoked": not active,
    }
