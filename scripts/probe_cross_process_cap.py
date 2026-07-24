"""Does the in-process RLock protect against TWO processes sharing a session file?

The RLock fix closed the single-process race. This proves the multi-process
gap: two agent processes reading the same session file each hold their own
lock and their own in-memory counter.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

WORKER = r'''
import json, sys, time
sys.path.insert(0, "/home/jeff-siegel/vida")
from vida.secure_wallet import SecureVida

session_file = sys.argv[1]
amount = float(sys.argv[2])

with open(session_file) as f:
    sess = json.load(f)

v = SecureVida.__new__(SecureVida)
v.session_limits = sess["limits"]
v.session_expires_at = sess["expires_at"]
v.session_daily_spent = sess.get("spend", {}).get("daily_spent", 0.0)
v._session_spend_day = sess.get("spend", {}).get("day", time.strftime("%Y-%m-%d", time.gmtime()))
v._session_file = session_file
v._session_machine_key = None
v.address = "kaspatest:qowner"

err = v.reserve_session_spend(amount, dest_address="kaspatest:qdest")
if err is None:
    time.sleep(0.15)          # overlap window with the sibling process
    v.record_session_spend(amount)
    print(f"APPROVED {amount}")
else:
    print(f"DENIED {err[:40]}")
'''

tmp = tempfile.mkdtemp()
worker_path = os.path.join(tmp, "worker.py")
with open(worker_path, "w") as f:
    f.write(WORKER)

session_path = os.path.join(tmp, "session.json")
with open(session_path, "w") as f:
    json.dump(
        {
            "limits": {
                "max_kas_per_tx": 0,
                "max_kas_per_day": 100.0,
                "allowed_destinations": None,
            },
            "expires_at": time.time() + 3600,
            "spend": {"day": time.strftime("%Y-%m-%d", time.gmtime()), "daily_spent": 0.0},
        },
        f,
    )

print("=== CROSS-PROCESS DAILY CAP TEST ===")
print("Cap: 100 KAS/day. Launching 4 concurrent processes, each spending 60 KAS.")
print("Correct behaviour: at most 1 approval (60 <= 100, second would exceed).")
print()

procs = [
    subprocess.Popen(
        [sys.executable, worker_path, session_path, "60"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    for _ in range(4)
]
results = [p.communicate() for p in procs]

approved = 0
for i, (out, err) in enumerate(results):
    line = (out or err or "").strip().splitlines()
    tag = line[-1] if line else "(no output)"
    print(f"  process {i}: {tag}")
    if "APPROVED" in tag:
        approved += 1

with open(session_path) as f:
    final = json.load(f)
recorded = final.get("spend", {}).get("daily_spent", 0.0)

print()
print("approvals            :", approved)
print("daily_spent on disk  :", recorded)
print("cap                  : 100.0")
print()
total_attempted = approved * 60
if total_attempted > 100:
    print(f">>> CAP EXCEEDED: {total_attempted} KAS approved against a 100 KAS cap")
    print(">>> CROSS-PROCESS GAP CONFIRMED: the in-process RLock does not span processes")
else:
    print(">>> cap held across processes")
