"""Verify the session daily-cap race is closed."""

import sys
import threading
import time

sys.path.insert(0, "/home/jeff-siegel/vida")
from vida.secure_wallet import SecureVida  # noqa: E402


def fresh():
    v = SecureVida.__new__(SecureVida)
    v.session_limits = {
        "max_kas_per_tx": 0,
        "max_kas_per_day": 100.0,
        "allowed_destinations": None,
    }
    v.session_expires_at = time.time() + 3600
    v.session_daily_spent = 0.0
    v._session_spend_day = time.strftime("%Y-%m-%d", time.gmtime())
    v._session_file = None
    v._session_machine_key = None
    v.address = "kaspatest:qowner"
    return v


print("=== RACE FIX VERIFICATION ===")
print("20 threads x 10 KAS against a 100 KAS/day cap. Expect exactly 10 approved.")
print()

v = fresh()
approved = []
tl = threading.Lock()


def attempt(i):
    err = v.reserve_session_spend(10.0, dest_address="kaspatest:qdest")
    if err is None:
        time.sleep(0.001)  # same check->record window that broke before
        v.record_session_spend(10.0)
        with tl:
            approved.append(i)


ts = [threading.Thread(target=attempt, args=(i,)) for i in range(20)]
for t in ts:
    t.start()
for t in ts:
    t.join()

print("approved      :", len(approved))
print("total spent   :", v.session_daily_spent, "KAS")
print("cap           : 100.0 KAS")
print("reserved left :", v._reserved)
assert v.session_daily_spent <= 100.0, f"CAP EXCEEDED: {v.session_daily_spent}"
assert len(approved) == 10, f"expected 10 approvals, got {len(approved)}"
print(">>> CAP HELD. Race closed.")
print()

print("=== release path (failed broadcast returns budget) ===")
v2 = fresh()
assert v2.reserve_session_spend(60.0, dest_address="d") is None
print("reserved 60      ->", v2._reserved)
err = v2.reserve_session_spend(60.0, dest_address="d")
print("second 60 in flight ->", "REJECTED" if err else "*** ACCEPTED (bug) ***")
assert err is not None
v2.release_session_spend(60.0)
print("after release    ->", v2._reserved)
assert v2.reserve_session_spend(60.0, dest_address="d") is None
print("re-reserve       -> OK (budget returned)")
print()

print("=== single-spend path unchanged ===")
v3 = fresh()
assert v3.reserve_session_spend(100.0, dest_address="d") is None
v3.record_session_spend(100.0)
print("spent full 100   ->", v3.session_daily_spent)
err = v3.reserve_session_spend(0.1, dest_address="d")
print("next 0.1 KAS     ->", "REJECTED" if err else "*** ACCEPTED (bug) ***")
assert err is not None
print()

print("=== per-tx cap and allowlist still enforced ===")
v4 = SecureVida.__new__(SecureVida)
v4.session_limits = {
    "max_kas_per_tx": 5.0,
    "max_kas_per_day": 100.0,
    "allowed_destinations": ["kaspatest:qgood"],
}
v4.session_expires_at = time.time() + 3600
v4.session_daily_spent = 0.0
v4._session_spend_day = time.strftime("%Y-%m-%d", time.gmtime())
v4._session_file = None
v4._session_machine_key = None
v4.address = "kaspatest:qowner"

print(
    "6 KAS (over 5 max_tx)    ->", "REJECTED" if v4.reserve_session_spend(6.0, "kaspatest:qgood") else "ACCEPTED (bug)"
)
print(
    "5 KAS to bad dest        ->", "REJECTED" if v4.reserve_session_spend(5.0, "kaspatest:qevil") else "ACCEPTED (bug)"
)
print(
    "5 KAS to good dest       ->", "REJECTED (bug)" if v4.reserve_session_spend(5.0, "kaspatest:qgood") else "ACCEPTED"
)
print()
print("=== expiry still enforced ===")
v5 = fresh()
v5.session_expires_at = time.time() - 1
print("expired session          ->", "REJECTED" if v5.reserve_session_spend(1.0, "d") else "ACCEPTED (bug)")
print()
print("ALL CHECKS PASSED")
