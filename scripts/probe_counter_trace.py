"""Trace the exact counter arithmetic across two processes."""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, "/home/jeff-siegel/vida")
from vida.secure_wallet import SecureVida  # noqa: E402

tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "s.json")
with open(path, "w") as f:
    json.dump(
        {
            "limits": {
                "max_kas_per_tx": 0,
                "max_kas_per_day": 100.0,
                "allowed_destinations": None,
            },
            "expires_at": time.time() + 3600,
        },
        f,
    )


def worker(tag, start_spent=0.0):
    v = SecureVida.__new__(SecureVida)
    v.session_limits = {
        "max_kas_per_tx": 0,
        "max_kas_per_day": 100.0,
        "allowed_destinations": None,
    }
    v.session_expires_at = time.time() + 3600
    v.session_daily_spent = start_spent
    v._session_spend_day = time.strftime("%Y-%m-%d", time.gmtime())
    v._session_file = path
    v._session_machine_key = None
    v.address = "kaspatest:qowner"
    v._tag = tag
    return v


def disk():
    with open(path) as f:
        return json.load(f).get("spend", {}).get("daily_spent", 0.0)


print("cap = 100. Two separate 'processes' (fresh objects, spent=0).")
print()

a = worker("A")
b = worker("B")

print("A reserves 60")
print("  err:", a.reserve_session_spend(60.0, "d"))
print(f"  A.mem={a.session_daily_spent} A.reserved={a._reserved} disk={disk()}")
print()

print("B reserves 60 (should be DENIED: 60+60 > 100)")
err = b.reserve_session_spend(60.0, "d")
print("  err:", (err or "NONE")[:50])
print(f"  B.mem={b.session_daily_spent} B.reserved={b._reserved} disk={disk()}")
print()

print("A commits 60")
a.record_session_spend(60.0)
print(f"  A.mem={a.session_daily_spent} A.reserved={a._reserved} disk={disk()}")
print()

print("=== THE BUG: a THIRD process now reserves ===")
c = worker("C")
err = c.reserve_session_spend(60.0, "d")
print("  C reserve 60 ->", (err or "ALLOWED")[:60])
print(f"  C.mem={c.session_daily_spent} disk={disk()}")
if err is None:
    print("  >>> WRONG: disk says 60 spent, 60+60=120 > 100 cap")
print()

print("=== small-spend accumulation ===")
os.remove(path)
with open(path, "w") as f:
    json.dump(
        {
            "limits": {
                "max_kas_per_tx": 0,
                "max_kas_per_day": 100.0,
                "allowed_destinations": None,
            },
            "expires_at": time.time() + 3600,
        },
        f,
    )
approved = 0
for i in range(20):
    w = worker(f"W{i}")  # each a fresh 'process' with spent=0
    if w.reserve_session_spend(10.0, "d") is None:
        w.record_session_spend(10.0)
        approved += 1
print(f"  sequential fresh processes approved: {approved} (expect 10)")
print(f"  disk daily_spent: {disk()} (expect 100.0)")
