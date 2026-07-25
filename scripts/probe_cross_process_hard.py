"""Harder cross-process cases: many small spends, release, and lock contention."""

import json
import os
import subprocess
import sys
import tempfile
import time

WORKER = r"""
import json, sys, time
sys.path.insert(0, "/home/jeff-siegel/vida")
from vida.secure_wallet import SecureVida

session_file, amount, mode = sys.argv[1], float(sys.argv[2]), sys.argv[3]

with open(session_file) as f:
    sess = json.load(f)

v = SecureVida.__new__(SecureVida)
v.session_limits = sess["limits"]
v.session_expires_at = sess["expires_at"]
v.session_daily_spent = 0.0
v._session_spend_day = time.strftime("%Y-%m-%d", time.gmtime())
v._session_file = session_file
v._session_machine_key = None
v.address = "kaspatest:qowner"

err = v.reserve_session_spend(amount, dest_address="kaspatest:qdest")
if err is not None:
    print("DENIED"); raise SystemExit
if mode == "commit":
    time.sleep(0.05)
    v.record_session_spend(amount)
    print("APPROVED")
else:                     # simulate a failed broadcast
    time.sleep(0.05)
    v.release_session_spend(amount)
    print("RELEASED")
"""

tmp = tempfile.mkdtemp()
worker = os.path.join(tmp, "w.py")
with open(worker, "w") as f:
    f.write(WORKER)


def new_session(cap):
    p = os.path.join(tmp, f"s{time.time_ns()}.json")
    with open(p, "w") as f:
        json.dump(
            {
                "limits": {
                    "max_kas_per_tx": 0,
                    "max_kas_per_day": cap,
                    "allowed_destinations": None,
                },
                "expires_at": time.time() + 3600,
            },
            f,
        )
    return p


def run(path, n, amount, mode):
    procs = [
        subprocess.Popen(
            [sys.executable, worker, path, str(amount), mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(n)
    ]
    out = [p.communicate() for p in procs]
    tags = []
    for o, e in out:
        lines = (o or "").strip().splitlines()
        tags.append(lines[-1] if lines else f"ERR:{(e or '').strip()[:60]}")
    return tags


def disk_spent(path):
    with open(path) as f:
        return json.load(f).get("spend", {}).get("daily_spent", 0.0)


print("=== TEST 1: 20 processes x 10 KAS, cap 100 ===")
p1 = new_session(100.0)
tags = run(p1, 20, 10, "commit")
ok = tags.count("APPROVED")
print(f"  approved={ok}  denied={tags.count('DENIED')}  errors={sum(1 for t in tags if t.startswith('ERR'))}")
print(f"  disk daily_spent={disk_spent(p1)}  cap=100.0")
assert ok == 10, f"expected 10 approvals, got {ok}"
assert disk_spent(p1) <= 100.0
print("  >>> PASS")
print()

print("=== TEST 2: released reservations return budget ===")
p2 = new_session(100.0)
tags = run(p2, 5, 20, "release")
print(f"  released={tags.count('RELEASED')}  denied={tags.count('DENIED')}")
print(f"  disk daily_spent after all releases={disk_spent(p2)}")
assert disk_spent(p2) < 1.0, "released budget was not returned"
tags = run(p2, 5, 20, "commit")
print(f"  then committed: approved={tags.count('APPROVED')}  disk={disk_spent(p2)}")
assert disk_spent(p2) <= 100.0
print("  >>> PASS")
print()

print("=== TEST 3: mixed commit/release under contention, cap 50 ===")
p3 = new_session(50.0)
procs = []
for i in range(10):
    mode = "commit" if i % 2 == 0 else "release"
    procs.append(
        subprocess.Popen(
            [sys.executable, worker, p3, "10", mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    )
res = [p.communicate() for p in procs]
tags = []
for o, e in res:
    lines = (o or "").strip().splitlines()
    tags.append(lines[-1] if lines else f"ERR:{(e or '').strip()[:50]}")
print(f"  approved={tags.count('APPROVED')} released={tags.count('RELEASED')} denied={tags.count('DENIED')}")
print(f"  disk daily_spent={disk_spent(p3)}  cap=50.0")
assert disk_spent(p3) <= 50.0, f"CAP EXCEEDED: {disk_spent(p3)}"
print("  >>> PASS")
print()

print("=== TEST 4: no leftover temp files ===")
leftovers = [f for f in os.listdir(tmp) if ".tmp" in f]
print(f"  temp files remaining: {leftovers if leftovers else 'none'}")
assert not leftovers, f"leaked temp files: {leftovers}"
print("  >>> PASS")
print()
print("ALL CROSS-PROCESS TESTS PASSED")
