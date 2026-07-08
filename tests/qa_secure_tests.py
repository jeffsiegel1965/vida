#!/usr/bin/env python3
"""
QA Test Suite for Vida SECURE Wallet (secure_wallet.py)
Covers: 24-word seed, scrypt+AES-GCM encryption, wrong-password rejection,
seed restore determinism, agent sessions (grant/expiry/revoke/tamper),
PQ signing, and VidaTransactor compatibility.
"""

import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'vida'))

from secure_wallet import (
    SecureVida,
    create_secure_wallet,
    grant_agent_session,
    revoke_agent_session,
    _decrypt,
    _derive_key,
    _session_aad,
    SCRYPT_N,
    PQ_AVAILABLE,
)

passed, failed, errors = 0, 0, []
tmpdir = tempfile.mkdtemp(prefix="vida_secure_qa_")
PW = "correct-horse-battery"


def run_test(name, fn):
    global passed, failed
    print(f"\n━━━ {name} ━━━")
    try:
        if fn():
            print(f"  ✔ PASS")
            passed += 1
        else:
            print(f"  ✘ FAIL")
            failed += 1
            errors.append(name)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ✘ ERROR: {e}")
        failed += 1
        errors.append(f"{name} ({e})")


# S1: creation — 24 words, encrypted file, 0600, no plaintext secrets on disk
def s1_creation():
    p = os.path.join(tmpdir, "w1.json")
    res = create_secure_wallet(p, PW, network="mainnet")
    words = res["mnemonic"].split()
    assert len(words) == 24, f"expected 24 words, got {len(words)}"
    print(f"  24-word mnemonic ✓")
    assert res["address"].startswith("kaspa:")
    mode = os.stat(p).st_mode & 0o777
    assert mode == 0o600, f"perms {oct(mode)}"
    print(f"  file perms 0600 ✓")

    raw = open(p).read()
    data = json.loads(raw)
    # No mnemonic words, no seed hex, no private key material in plaintext
    for w in words:
        assert f'"{w}"' not in raw
    assert res["mnemonic"] not in raw
    # REAL assertions (not tautological): the actual secret VALUES must be absent
    w_unlocked = SecureVida(p, password=PW)
    assert w_unlocked._private_key_hex not in raw, "schnorr privkey leaked to disk!"
    seed_bytes = _decrypt(_derive_key(PW, bytes.fromhex(data["kdf"]["salt"])), data["enc_seed"])
    assert seed_bytes.hex() not in raw, "seed leaked to disk!"
    if w_unlocked._pq_sk:
        assert w_unlocked._pq_sk.hex() not in raw, "PQ secret leaked to disk!"
    w_unlocked.lock()
    assert set(data["enc_schnorr"].keys()) == {"nonce", "ct"}
    assert data["kdf"]["algo"] == "scrypt" and data["kdf"]["n"] == SCRYPT_N
    print(f"  actual secret values verified ABSENT from disk ✓")
    return True


# S2: unlock with correct password; wrong password must fail loudly
def s2_password():
    p = os.path.join(tmpdir, "w2.json")
    create_secure_wallet(p, PW)
    w = SecureVida(p, password=PW)
    sig = w.sign("hello")
    assert w.verify("hello", sig)
    print(f"  correct password: unlock + sign + verify ✓")
    w.lock()
    assert w._private_key_hex is None
    print(f"  lock() scrubs key ✓")

    try:
        SecureVida(p, password="wrong-password-123")
        return False
    except ValueError as e:
        assert "Wrong password" in str(e)
        print(f"  wrong password rejected ✓")
    return True


# S3: restore from the same 24 words -> same address (deterministic funds key)
def s3_restore():
    p1 = os.path.join(tmpdir, "w3a.json")
    res1 = create_secure_wallet(p1, PW)
    p2 = os.path.join(tmpdir, "w3b.json")
    res2 = create_secure_wallet(p2, "different-password-9", mnemonic_phrase=res1["mnemonic"])
    assert res1["address"] == res2["address"], "restore must reproduce address"
    print(f"  same 24 words -> same address ✓ ({res1['address'][:25]}...)")

    # And the restored wallet signs; original wallet verifies
    w1 = SecureVida(p1, password=PW)
    w2 = SecureVida(p2, password="different-password-9")
    sig = w2.sign("cross-check")
    assert w1.verify("cross-check", sig)
    print(f"  restored wallet signature verifies against original pubkey ✓")
    return True


# S4: refuses to overwrite an existing wallet; refuses short password
def s4_guards():
    p = os.path.join(tmpdir, "w4.json")
    create_secure_wallet(p, PW)
    try:
        create_secure_wallet(p, PW)
        return False
    except FileExistsError:
        print(f"  overwrite refused ✓")
    try:
        create_secure_wallet(os.path.join(tmpdir, "w4b.json"), "short")
        return False
    except ValueError:
        print(f"  short password refused ✓")
    return True


# S5: PQ keys — encrypted at rest, sign/verify round-trip after unlock
def s5_pq():
    if not PQ_AVAILABLE:
        print("  SKIP: ML-DSA-65 unavailable")
        return True
    p = os.path.join(tmpdir, "w5.json")
    create_secure_wallet(p, PW)
    w = SecureVida(p, password=PW)
    assert w.pq_public_key, "PQ pubkey missing"
    sig = w.sign_pq(b"pq message")
    assert len(sig) == 3309
    assert w.verify_pq(b"pq message", sig) is True
    assert w.verify_pq(b"tampered", sig) is False
    print(f"  PQ sign/verify round-trip, wrong msg rejected ✓")
    return True


# S6: agent session — grant, unlock without password, no PQ secret exposure
def s6_session_grant():
    p = os.path.join(tmpdir, "w6.json")
    create_secure_wallet(p, PW)
    sp = os.path.join(tmpdir, "sess6.json")
    info = grant_agent_session(p, PW, sp, hours=1, max_kas_per_tx=5, max_kas_per_day=20)
    assert os.stat(sp).st_mode & 0o777 == 0o600
    print(f"  session file 0600 ✓")

    agent = SecureVida(p, _session_file=sp)
    sig = agent.sign("agent spend")
    assert agent.verify("agent spend", sig)
    print(f"  agent unlocks WITHOUT password and can sign ✓")
    assert agent._pq_sk is None
    try:
        agent.sign_pq(b"x")
        return False
    except ValueError:
        print(f"  PQ secret NOT exposed to agent sessions ✓")
    assert agent.session_limits == {"max_kas_per_tx": 5, "max_kas_per_day": 20}
    print(f"  limits carried in session ✓")

    # Wrong password can't grant
    try:
        grant_agent_session(p, "bad-password-000", os.path.join(tmpdir, "x.json"), hours=1)
        return False
    except ValueError:
        print(f"  grant with wrong password refused ✓")
    return True


# S7: session expiry — expired session refuses and burns the file
def s7_session_expiry():
    p = os.path.join(tmpdir, "w7.json")
    create_secure_wallet(p, PW)
    sp = os.path.join(tmpdir, "sess7.json")
    grant_agent_session(p, PW, sp, hours=(0.3 / 3600))  # 0.3s
    time.sleep(0.6)
    try:
        SecureVida(p, _session_file=sp)
        return False
    except ValueError as e:
        assert "expired" in str(e)
        print(f"  expired session refused ✓")
    assert not os.path.exists(sp)
    print(f"  expired session file burned ✓")
    return True


# S8: revocation — file scrubbed with random bytes then deleted
def s8_revoke():
    p = os.path.join(tmpdir, "w8.json")
    create_secure_wallet(p, PW)
    sp = os.path.join(tmpdir, "sess8.json")
    grant_agent_session(p, PW, sp, hours=24)
    assert revoke_agent_session(sp) is True
    assert not os.path.exists(sp)
    print(f"  revoke deletes session ✓")
    try:
        SecureVida(p, _session_file=sp)
        return False
    except FileNotFoundError:
        print(f"  agent locked out after revoke ✓")
    assert revoke_agent_session(sp) is False  # idempotent
    return True


# S9: tampered session file (wrong wallet / corrupted key) is rejected
def s9_tamper():
    p = os.path.join(tmpdir, "w9.json")
    create_secure_wallet(p, PW)
    sp = os.path.join(tmpdir, "sess9.json")
    grant_agent_session(p, PW, sp, hours=24)

    sess = json.load(open(sp))
    # Corrupt the machine key
    sess["machine_key"] = os.urandom(32).hex()
    json.dump(sess, open(sp, "w"))
    try:
        SecureVida(p, _session_file=sp)
        return False
    except Exception:
        print(f"  corrupted machine key rejected (AES-GCM auth) ✓")

    # Session for a different wallet
    p2 = os.path.join(tmpdir, "w9b.json")
    create_secure_wallet(p2, PW)
    sp2 = os.path.join(tmpdir, "sess9b.json")
    grant_agent_session(p2, PW, sp2, hours=24)
    try:
        SecureVida(p, _session_file=sp2)
        return False
    except ValueError as e:
        assert "different wallet" in str(e)
        print(f"  session for different wallet rejected ✓")
    return True


# S10: VidaTransactor compatibility — SecureVida slots into the tx engine
def s10_transactor_compat():
    from transactions import VidaTransactor
    p = os.path.join(tmpdir, "w10.json")
    create_secure_wallet(p, PW, network="testnet")
    w = SecureVida(p, password=PW)
    tx = VidaTransactor(w)
    assert tx.network == "testnet-10"
    # Offline checks only (no funds on this fresh wallet): validation gates
    import asyncio
    r = asyncio.run(tx.send("kaspatest:qpu63f6hy3l99pkphhfcvpgl5lxpv25fg5nn53cpykef5kygc0g0w9fly8vmu", -5))
    assert not r.success and "positive" in r.error
    r = asyncio.run(tx.send("kaspa:wrongnet", 1.0))
    assert not r.success and "prefix" in r.error
    print(f"  SecureVida works with VidaTransactor; validation gates fire ✓")
    return True


# S11: AAD binding — editing expiry or limits in the session file breaks unlock
def s11_aad_tamper():
    p = os.path.join(tmpdir, "w11.json")
    create_secure_wallet(p, PW, network="testnet")
    sp = os.path.join(tmpdir, "sess11.json")
    grant_agent_session(p, PW, sp, hours=1, max_kas_per_tx=5, max_kas_per_day=20)

    # Baseline: unlocks fine
    SecureVida(p, _session_file=sp)
    print("  clean session unlocks ✓")

    # Attacker extends expiry to the far future
    sess = json.load(open(sp))
    sess["expires_at"] = sess["expires_at"] + 10**9
    json.dump(sess, open(sp, "w"))
    try:
        SecureVida(p, _session_file=sp)
        return False
    except ValueError as e:
        assert "tamper" in str(e).lower()
        print("  extended-expiry tamper rejected (AAD) ✓")

    # Attacker raises the daily limit
    grant_agent_session(p, PW, os.path.join(tmpdir, "sess11b.json"),
                        hours=1, max_kas_per_tx=5, max_kas_per_day=20)
    spb = os.path.join(tmpdir, "sess11b.json")
    sess = json.load(open(spb))
    sess["limits"]["max_kas_per_day"] = 999999
    json.dump(sess, open(spb, "w"))
    try:
        SecureVida(p, _session_file=spb)
        return False
    except ValueError:
        print("  raised-limit tamper rejected (AAD) ✓")
    return True


if __name__ == "__main__":
    print("=" * 64)
    print("  VIDA SECURE WALLET QA")
    print(f"  PQ available: {PQ_AVAILABLE}")
    print("=" * 64)

    run_test("S1:  creation — 24 words, ciphertext-only, 0600", s1_creation)
    run_test("S2:  password unlock; wrong password rejected", s2_password)
    run_test("S3:  24-word restore reproduces address", s3_restore)
    run_test("S4:  overwrite + weak password guards", s4_guards)
    run_test("S5:  PQ keys encrypted at rest, sign/verify", s5_pq)
    run_test("S6:  agent session grant (no password, no PQ)", s6_session_grant)
    run_test("S7:  session expiry burns file", s7_session_expiry)
    run_test("S8:  revocation locks agent out", s8_revoke)
    run_test("S9:  tampered/mismatched sessions rejected", s9_tamper)
    run_test("S10: transactor compatibility + gates", s10_transactor_compat)
    run_test("S11: AAD tamper on expiry/limits rejected", s11_aad_tamper)

    # Cleanup: destroy the temp dir — it holds plaintext test keys (T-4)
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

    print("\n" + "━" * 64)
    print(f"SUMMARY: {passed} passed, {failed} failed, {passed+failed} total")
    if errors:
        for e in errors:
            print(f"  ✘ {e}")
    sys.exit(0 if failed == 0 else 1)
