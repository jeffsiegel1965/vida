#!/usr/bin/env python3
"""
QA Test Suite for Vida Wallet
Tests all wallet functionality: creation, signing, PQ signatures, session keys, delegation modes.
"""

import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

# Ensure vida directory is in path for ml_dsa_65 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'vida'))

from wallet import (
    PQ_AVAILABLE,
    DelegationMode,
    Vida,
    create_wallet,
)

# ─── Test harness ───────────────────────────────────────────────────────────

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


passed = 0
failed = 0
errors = []


def run_test(name: str, test_func):
    global passed, failed
    print(f"\n{Colors.BOLD}{Colors.BLUE}━━━ {name} ━━━{Colors.RESET}")
    try:
        result = test_func()
        if result:
            print(f"  {Colors.GREEN}✔ PASS{Colors.RESET}: {name}")
            passed += 1
        else:
            print(f"  {Colors.RED}✘ FAIL{Colors.RESET}: {name}")
            failed += 1
            errors.append(name)
    except Exception as e:
        print(f"  {Colors.RED}✘ ERROR{Colors.RESET}: {name}")
        print(f"    Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
        errors.append(f"{name} (exception: {e})")


# ─── Fixtures ────────────────────────────────────────────────────────────────

tmpdir = tempfile.mkdtemp(prefix='vida_qa_')


def cleanup_tmpdir():
    """Cleanup temp directory after tests — it holds plaintext test keys."""
    shutil.rmtree(tmpdir, ignore_errors=True)


# ─── T1: create_wallet writes file, has kaspa:/kaspatest: address, chmod 0600 ─

def test_t1_wallet_creation():
    """Create wallet on both mainnet and testnet, verify file + address + perms."""

    # Test mainnet
    main_path = os.path.join(tmpdir, 'wallet_main.json')
    w_main = create_wallet(main_path, network='mainnet')

    assert os.path.exists(main_path), "Wallet file does not exist"
    assert w_main.address.startswith('kaspa:'), f"Mainnet address should start with 'kaspa:', got: {w_main.address}"
    print(f"  Mainnet address: {w_main.address}")

    # Test testnet
    test_path = os.path.join(tmpdir, 'wallet_test.json')
    w_test = create_wallet(test_path, network='testnet')

    assert w_test.address.startswith('kaspatest:'), f"Testnet address should start with 'kaspatest:', got: {w_test.address}"
    print(f"  Testnet address: {w_test.address}")

    # Check chmod 0600
    file_mode = os.stat(main_path).st_mode
    expected_mode = stat.S_IRUSR | stat.S_IWUSR
    assert (file_mode & 0o777) == 0o600, f"Expected 0600 permissions, got {oct(file_mode & 0o777)}"
    print(f"  File permissions: {oct(file_mode & 0o777)} (0600)")

    # Verify JSON has expected fields
    import json
    with open(main_path) as f:
        data = json.load(f)
    assert 'address' in data
    assert 'public_key' in data
    assert 'private_key_hex' in data
    print("  JSON has required fields: address, public_key, private_key_hex")

    return True


# ─── T2: cold sign produces valid 128-char hex sig, verify succeeds, reject wrong message ─

def test_t2_cold_signing():
    """Cold wallet Schnorr signing: 128-char hex, verify passes for correct msg, fails for wrong msg."""

    wallet_path = os.path.join(tmpdir, 'wallet_t2.json')
    w = create_wallet(wallet_path, network='mainnet')

    message = "test message for signing"
    sig_hex = w.sign(message)

    # Check signature is 128-char hex
    assert isinstance(sig_hex, str), f"Signature should be str, got {type(sig_hex)}"
    assert len(sig_hex) == 128, f"Expected 128-char hex signature, got {len(sig_hex)}"
    # Check it's valid hex
    int(sig_hex, 16)  # raises if not hex
    print(f"  Signature (128 hex chars): {sig_hex[:32]}...{sig_hex[-32:]}")

    # Verify correct message
    ok = w.verify(message, sig_hex)
    assert ok is True, "Verification should pass for correct message"
    print(f"  Verify (correct message): {ok}")

    # Verify wrong message
    ok_wrong = w.verify("wrong message", sig_hex)
    assert ok_wrong is False, "Verification should fail for wrong message"
    print(f"  Verify (wrong message): {ok_wrong}")

    return True


# ─── T3: verify_pq round-trip on PQ-enabled wallet ─

def test_t3_pq_signing():
    """Post-quantum ML-DSA-65 signature round-trip."""

    wallet_path = os.path.join(tmpdir, 'wallet_t3_pq.json')
    w = create_wallet(wallet_path, network='mainnet', mldsa=True)

    assert w.pq_pubkey is not None, "PQ public key should be set"
    assert w._pq_privkey is not None, "PQ private key should be set"
    print(f"  PQ public key length: {len(w.pq_pubkey)} hex chars ({len(bytes.fromhex(w.pq_pubkey))} bytes)")

    message = b"post-quantum test message"
    sig_bytes = w.sign_pq(message)

    assert isinstance(sig_bytes, bytes), f"PQ signature should be bytes, got {type(sig_bytes)}"
    assert len(sig_bytes) == 3309, f"Expected 3309-byte PQ signature, got {len(sig_bytes)}"
    print(f"  PQ signature: {len(sig_bytes)} bytes")

    # Verify
    ok = w.verify_pq(message, sig_bytes)
    assert ok is True, "PQ verification should pass"
    print(f"  Verify PQ (correct message): {ok}")

    # Wrong message
    ok_wrong = w.verify_pq(b"wrong message", sig_bytes)
    assert ok_wrong is False, "PQ verification should fail for wrong message"
    print(f"  Verify PQ (wrong message): {ok_wrong}")

    return True


# ─── T4: FULL-mode session key signs any amount ─

def test_t4_full_mode():
    """FULL delegation: session key can sign any amount."""

    wallet_path = os.path.join(tmpdir, 'wallet_t4.json')
    w = create_wallet(wallet_path, network='testnet')

    session = w.create_session_key(mode=DelegationMode.FULL)
    print(f"  Session pubkey: {session.public_key_hex[:16]}... (FULL mode)")
    print(f"  is_active: {session.is_active}")

    # Can sign any amount
    sig_0 = w.sign_with_session(session.public_key_hex, "msg_0", 0.0)
    assert sig_0 is not None, "FULL mode should sign 0 KAS"
    assert isinstance(sig_0, str) and len(sig_0) == 128, "Should be 128-char hex sig"
    print(f"  sign(0 KAS): OK (sig={sig_0[:16]}...)")

    sig_large = w.sign_with_session(session.public_key_hex, "msg_large", 999999.99)
    assert sig_large is not None, "FULL mode should sign 999999.99 KAS"
    print(f"  sign(999999.99 KAS): OK (sig={sig_large[:16]}...)")

    # Negative amounts must ALWAYS be rejected (security fix)
    sig_negative = w.sign_with_session(session.public_key_hex, "msg_neg", -1.0)
    assert sig_negative is None, "Negative amounts must be rejected in ALL modes"
    print("  sign(-1 KAS) -> None ✓ (negative rejected)")

    return True


# ─── T5: COMMAND-mode session key ALWAYS returns None (even at 0 KAS) ─

def test_t5_command_mode():
    """COMMAND delegation: session key ALWAYS returns None (owner must approve)."""

    wallet_path = os.path.join(tmpdir, 'wallet_t5.json')
    w = create_wallet(wallet_path, network='testnet')

    session = w.create_session_key(mode=DelegationMode.COMMAND)
    print(f"  Session pubkey: {session.public_key_hex[:16]}... (COMMAND mode)")

    # Must return None even at 0 KAS
    sig_0 = w.sign_with_session(session.public_key_hex, "msg", 0.0)
    assert sig_0 is None, f"COMMAND mode should return None at 0 KAS, got: {sig_0}"
    print("  sign(0 KAS) -> None ✓")

    sig_1 = w.sign_with_session(session.public_key_hex, "msg", 1.0)
    assert sig_1 is None, f"COMMAND mode should return None at 1 KAS, got: {sig_1}"
    print("  sign(1 KAS) -> None ✓")

    sig_large = w.sign_with_session(session.public_key_hex, "msg", 999999.99)
    assert sig_large is None, f"COMMAND mode should return None at 999999.99 KAS, got: {sig_large}"
    print("  sign(999999.99 KAS) -> None ✓")

    return True


# ─── T6: HYBRID-mode signs at/below threshold, rejects above ─

def test_t6_hybrid_mode():
    """HYBRID delegation: signs up to threshold, rejects above."""

    wallet_path = os.path.join(tmpdir, 'wallet_t6.json')
    w = create_wallet(wallet_path, network='testnet')

    threshold = 10.0
    session = w.create_session_key(mode=DelegationMode.HYBRID, threshold=threshold)
    print(f"  Session pubkey: {session.public_key_hex[:16]}... (HYBRID, threshold={threshold})")

    # At threshold: should succeed
    sig_at = w.sign_with_session(session.public_key_hex, "msg", threshold)
    assert sig_at is not None, f"HYBRID should sign at threshold ({threshold} KAS)"
    print(f"  sign({threshold} KAS) [at threshold]: OK (sig={sig_at[:16]}...)")

    # Below threshold: should succeed
    sig_below = w.sign_with_session(session.public_key_hex, "msg", threshold - 0.01)
    assert sig_below is not None, f"HYBRID should sign below threshold ({threshold - 0.01} KAS)"
    print(f"  sign({threshold - 0.01} KAS) [below]: OK")

    # Zero: should succeed
    sig_zero = w.sign_with_session(session.public_key_hex, "msg", 0.0)
    assert sig_zero is not None, "HYBRID should sign 0 KAS"
    print("  sign(0.0 KAS) [below]: OK")

    # Above threshold: should fail
    sig_above = w.sign_with_session(session.public_key_hex, "msg", threshold + 0.01)
    assert sig_above is None, f"HYBRID should reject above threshold ({threshold + 0.01} KAS)"
    print(f"  sign({threshold + 0.01} KAS) [above] -> None ✓")

    # Well above: should fail
    sig_far = w.sign_with_session(session.public_key_hex, "msg", 999999.0)
    assert sig_far is None, "HYBRID should reject 999999 KAS"
    print("  sign(999999 KAS) [above] -> None ✓")

    return True


# ─── T7: revoke_session_key makes previously-working session return None ─

def test_t7_revoke():
    """Revoking a session key makes it immediately unusable."""

    wallet_path = os.path.join(tmpdir, 'wallet_t7.json')
    w = create_wallet(wallet_path, network='testnet')

    session = w.create_session_key(mode=DelegationMode.FULL)
    print(f"  Session pubkey: {session.public_key_hex[:16]}... ")

    # Should work before revoke
    sig_before = w.sign_with_session(session.public_key_hex, "msg", 100.0)
    assert sig_before is not None, "Should work before revoke"
    print("  Before revoke: sign OK ✓")

    # Revoke
    w.revoke_session_key(session.public_key_hex)
    assert session.revoked is True, "Session should be marked revoked"
    assert session.is_active is False, "Revoked session should not be active"
    print(f"  Revoked (is_active={session.is_active})")

    # Should NOT work after revoke
    sig_after = w.sign_with_session(session.public_key_hex, "msg", 100.0)
    assert sig_after is None, f"Should return None after revoke, got: {sig_after}"
    print("  After revoke: sign -> None ✓")

    return True


# ─── T8: expired session returns None ─

def test_t8_expiry():
    """Expired session key cannot sign."""

    wallet_path = os.path.join(tmpdir, 'wallet_t8.json')
    w = create_wallet(wallet_path, network='testnet')

    # Create session with 0 hours expiry (immediately expired)
    session = w.create_session_key(mode=DelegationMode.FULL, expires_hours=0)
    print("  Created session with expires_hours=0")
    print(f"  is_active immediately: {session.is_active}")

    # Wait a bit to ensure we're past the expiry moment
    time.sleep(0.1)

    print(f"  After sleep(0.1s), is_active: {session.is_active}")
    assert session.is_active is False, "Session with 0h lifetime should be expired after sleep"

    # Try to sign
    sig = w.sign_with_session(session.public_key_hex, "msg", 1.0)
    assert sig is None, f"Expired session should return None, got: {sig}"
    print("  sign -> None ✓")

    # Also test: non-zero expiry that we DON'T wait for should still work
    session2 = w.create_session_key(mode=DelegationMode.FULL, expires_hours=24)
    print("  Created session with expires_hours=24")
    assert session2.is_active is True, "24h session should be active"
    sig2 = w.sign_with_session(session2.public_key_hex, "msg", 1.0)
    assert sig2 is not None, "24h session should work"
    print("  24h session sign OK ✓")

    return True


# ─── T9: list_session_keys output NEVER contains 'private_key' substring ─

def test_t9_no_private_key_leak():
    """list_session_keys must never include private key material."""

    wallet_path = os.path.join(tmpdir, 'wallet_t9.json')
    w = create_wallet(wallet_path, network='testnet')

    # Create various session keys
    s1 = w.create_session_key(mode=DelegationMode.FULL)
    s2 = w.create_session_key(mode=DelegationMode.COMMAND)
    s3 = w.create_session_key(mode=DelegationMode.HYBRID, threshold=5.0)

    print(f"  Created {len(w.list_session_keys())} session keys")

    # Get the listing
    listing = w.list_session_keys()
    assert len(listing) == 3, f"Expected 3 session keys, got {len(listing)}"

    # Serialize to JSON string and check
    import json
    listing_json = json.dumps(listing)

    has_private = 'private_key' in listing_json.lower()
    assert not has_private, f"listing contains 'private_key'! Content: {listing_json}"
    print("  Listing JSON: NO 'private_key' substring ✓")

    # Also check individual dicts
    for i, entry in enumerate(listing):
        keys_lower = [k.lower() for k in entry.keys()]
        assert 'private_key_hex' not in keys_lower, f"Entry {i} has private_key_hex"
        assert 'privkey' not in ' '.join(keys_lower), f"Entry {i} has privkey"

    # Check no private key hex value is leaked either.
    # REAL assertion (T-2 fix): every session private key hex must be ABSENT
    # from the listing output — the old `A or B` form could never fail.
    for pub, priv in w._session_privkeys.items():
        assert priv not in listing_json, f"private key hex leaked in listing for {pub[:12]}"
    # And every listed pubkey must actually be one we created
    listed_pubs = {e['public_key_hex'] for e in listing}
    assert s1.public_key_hex in listed_pubs
    assert s2.public_key_hex in listed_pubs
    assert s3.public_key_hex in listed_pubs

    print(f"  Keys in listing entries: {list(listing[0].keys())}")

    return True


# ─── Unknown session key returns None ─

def test_t10_unknown_session():
    """Signing with an unknown session key returns None (defensive)."""

    wallet_path = os.path.join(tmpdir, 'wallet_t10.json')
    w = create_wallet(wallet_path, network='testnet')

    fake_pubkey = "abcdef0123456789" * 4  # not a real session key
    sig = w.sign_with_session(fake_pubkey, "msg", 1.0)
    assert sig is None, "Unknown session should return None"
    print("  Unknown session -> None ✓")

    return True


# ─── Wallet reload from disk preserves signing ability ─

def test_t11_reload():
    """Wallet can be reloaded from disk and still sign."""

    wallet_path = os.path.join(tmpdir, 'wallet_t11.json')
    w1 = create_wallet(wallet_path, network='mainnet')
    addr1 = w1.address
    pubkey1 = w1.public_key

    # Sign something
    msg = "persistence test"
    sig1 = w1.sign(msg)

    # Reload
    w2 = Vida(wallet_path, network='mainnet')
    assert w2.address == addr1, "Reloaded address should match"
    assert w2.public_key == pubkey1, "Reloaded pubkey should match"

    # Old signature still verifies
    assert w2.verify(msg, sig1) is True, "Reloaded wallet should verify old sig"

    # Can sign fresh
    sig2 = w2.sign(msg)
    assert sig2 is not None
    # Note: Schnorr signatures may or may not be deterministic; just check they work
    assert w2.verify(msg, sig2) is True

    print(f"  Address after reload: {w2.address[:20]}...")
    print("  Reloaded wallet signs and verifies ✓")

    return True


# ─── T12: daily cumulative limit is enforced ─

def test_t12_daily_limit():
    """Daily cumulative limit: session stops signing once cap is reached."""

    wallet_path = os.path.join(tmpdir, 'wallet_t12.json')
    w = create_wallet(wallet_path, network='testnet')

    # HYBRID: 10 KAS per tx, 25 KAS per day
    session = w.create_session_key(mode=DelegationMode.HYBRID, threshold=10.0, daily_limit=25.0)
    print("  HYBRID session: threshold=10, daily_limit=25")

    # Spend 10 + 10 = 20 (under cap)
    assert w.sign_with_session(session.public_key_hex, "tx1", 10.0) is not None, "1st 10 KAS should sign"
    assert w.sign_with_session(session.public_key_hex, "tx2", 10.0) is not None, "2nd 10 KAS should sign"
    print("  Spent 20/25 KAS: OK")

    # Next 10 would push to 30 > 25 → reject
    assert w.sign_with_session(session.public_key_hex, "tx3", 10.0) is None, "3rd 10 KAS should be rejected (over daily cap)"
    print("  3rd 10 KAS -> None ✓ (would exceed 25 daily cap)")

    # But a 5 KAS spend (exactly hitting the cap) is fine
    assert w.sign_with_session(session.public_key_hex, "tx4", 5.0) is not None, "5 KAS should sign (hits cap exactly)"
    print("  5 KAS (exactly to cap): OK")

    # Now fully at cap: even tiny spend is rejected
    assert w.sign_with_session(session.public_key_hex, "tx5", 0.1) is None, "0.1 KAS should be rejected (at cap)"
    print("  0.1 KAS at cap -> None ✓")

    # FULL mode with a daily limit is also enforced
    s_full = w.create_session_key(mode=DelegationMode.FULL, daily_limit=50.0)
    assert w.sign_with_session(s_full.public_key_hex, "big", 50.0) is not None, "FULL should sign up to its daily cap"
    assert w.sign_with_session(s_full.public_key_hex, "big2", 1.0) is None, "FULL over daily cap should be rejected"
    print("  FULL mode daily cap enforced ✓")

    return True


# ─── T13: revoked session key's private key is wiped from memory ─

def test_t13_revoke_wipes_privkey():
    """Revoking a session key destroys its private key, not just flags it."""

    wallet_path = os.path.join(tmpdir, 'wallet_t13.json')
    w = create_wallet(wallet_path, network='testnet')

    session = w.create_session_key(mode=DelegationMode.FULL)
    pub = session.public_key_hex

    assert pub in w._session_privkeys, "Privkey should exist before revoke"
    w.revoke_session_key(pub)
    assert pub not in w._session_privkeys, "Privkey must be wiped after revoke"
    print("  Private key wiped from memory after revoke ✓")

    # And of course it can't sign
    assert w.sign_with_session(pub, "msg", 1.0) is None
    print("  Revoked session sign -> None ✓")

    return True


# ─── Run all tests ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print("  VIDA WALLET QA TEST SUITE")
    print(f"  PQ (ML-DSA-65) available: {PQ_AVAILABLE}")
    print(f"{'='*70}{Colors.RESET}")

    run_test("T1:  create_wallet writes file, address format, chmod 0600", test_t1_wallet_creation)
    run_test("T2:  cold sign: 128-char hex sig, verify ± wrong msg", test_t2_cold_signing)

    if PQ_AVAILABLE:
        run_test("T3:  verify_pq round-trip on PQ-enabled wallet", test_t3_pq_signing)
    else:
        print(f"\n{Colors.YELLOW}  ⚠ Skipping T3: ml_dsa_65 not available{Colors.RESET}")

    run_test("T4:  FULL-mode session key signs any amount", test_t4_full_mode)
    run_test("T5:  COMMAND-mode session key ALWAYS returns None", test_t5_command_mode)
    run_test("T6:  HYBRID-mode: at/below threshold → sign, above → None", test_t6_hybrid_mode)
    run_test("T7:  revoke_session_key makes session return None", test_t7_revoke)
    run_test("T8:  expired session (expires_hours=0, sleep 0.1s) → None", test_t8_expiry)
    run_test("T9:  list_session_keys NEVER contains 'private_key'", test_t9_no_private_key_leak)
    run_test("T10: unknown session key returns None", test_t10_unknown_session)
    run_test("T11: wallet reload from disk preserves signing", test_t11_reload)
    run_test("T12: daily cumulative limit enforced", test_t12_daily_limit)
    run_test("T13: revoke wipes session private key from memory", test_t13_revoke_wipes_privkey)

    print(f"\n{Colors.BLUE}{'━'*70}{Colors.RESET}")
    print(f"{Colors.BOLD}SUMMARY{Colors.RESET}:")
    print(f"  {Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"  {Colors.RED}Failed: {failed}{Colors.RESET}")
    print(f"  Total:  {passed + failed}")

    if errors:
        print(f"\n{Colors.RED}{Colors.BOLD}FAILURES:{Colors.RESET}")
        for e in errors:
            print(f"  {Colors.RED}✘{Colors.RESET} {e}")

    print(f"\n{'='*70}\n")

    # Cleanup
    cleanup_tmpdir()

    sys.exit(0 if failed == 0 else 1)
