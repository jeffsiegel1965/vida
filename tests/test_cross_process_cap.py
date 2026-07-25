"""Regression tests: cross-process session daily-cap enforcement.

Found and fixed 2026-07-24, proven by execution with real subprocesses.

The in-process RLock (see test_session_cap_race.py) only serialises threads
inside ONE process. Two agent processes sharing a session file each held their
own lock and their own in-memory counter, so both passed the daily cap.

Measured before the fix: 4 concurrent processes each spending 60 KAS against a
100 KAS/day cap -> 2 approvals, 120 KAS committed.

Fix: an exclusive fcntl.flock on "<session>.lock" is held across the entire
read-modify-write, and the ON-DISK counter is authoritative -- re-read under
the lock rather than trusted from memory.

Two follow-on bugs were found while verifying the fix, both included here:

* Lost writes. _sync_spend_from_disk() originally only adopted the disk value
  when it was HIGHER than memory. A freshly started process begins at 0.0,
  adds its own reservation, and then persisted a total LOWER than what
  siblings had committed. Measured: 11 approvals against a 10-approval cap,
  disk ending at 20.0 instead of 100.0.

* Temp-file collision. _persist_session_spend() wrote to a shared
  "<session>.tmp"; two concurrent writers raced and the loser's replace()
  failed with ENOENT. Now uses a per-PID temp name.
"""

import json
import os
import subprocess
import sys
import time

import pytest

REPO = "/home/jeff-siegel/vida"

WORKER = r"""
import json, sys, time
sys.path.insert(0, "{repo}")
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
time.sleep(0.05)
if mode == "commit":
    v.record_session_spend(amount)
    print("APPROVED")
else:
    v.release_session_spend(amount)
    print("RELEASED")
""".format(repo=REPO)


@pytest.fixture
def worker_script(tmp_path):
    p = tmp_path / "worker.py"
    p.write_text(WORKER)
    return str(p)


def make_session(tmp_path, cap, name="session.json"):
    p = tmp_path / name
    p.write_text(
        json.dumps(
            {
                "limits": {
                    "max_kas_per_tx": 0,
                    "max_kas_per_day": cap,
                    "allowed_destinations": None,
                },
                "expires_at": time.time() + 3600,
            }
        )
    )
    return str(p)


def run_workers(script, session, n, amount, mode="commit"):
    procs = [
        subprocess.Popen(
            [sys.executable, script, session, str(amount), mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(n)
    ]
    tags = []
    for p in procs:
        out, err = p.communicate(timeout=60)
        lines = (out or "").strip().splitlines()
        tags.append(lines[-1] if lines else f"ERR:{(err or '').strip()[:80]}")
    return tags


def disk_spent(session):
    with open(session) as f:
        return json.load(f).get("spend", {}).get("daily_spent", 0.0)


class TestCrossProcessCap:
    def test_four_processes_cannot_double_spend(self, tmp_path, worker_script):
        """The original exploit: 4 x 60 KAS against a 100 KAS cap."""
        session = make_session(tmp_path, 100.0)
        tags = run_workers(worker_script, session, 4, 60)
        approved = tags.count("APPROVED")
        assert not [t for t in tags if t.startswith("ERR")], tags
        assert approved == 1, f"expected 1 approval, got {approved}: {tags}"
        assert disk_spent(session) <= 100.0

    def test_twenty_processes_exact_cap(self, tmp_path, worker_script):
        """20 x 10 KAS against 100 KAS must approve exactly 10."""
        session = make_session(tmp_path, 100.0)
        tags = run_workers(worker_script, session, 20, 10)
        approved = tags.count("APPROVED")
        assert not [t for t in tags if t.startswith("ERR")], tags
        assert approved == 10, f"expected 10 approvals, got {approved}"
        assert disk_spent(session) == pytest.approx(100.0)

    def test_no_lost_writes(self, tmp_path, worker_script):
        """Disk total must equal the number of approvals x amount."""
        session = make_session(tmp_path, 100.0)
        tags = run_workers(worker_script, session, 20, 10)
        approved = tags.count("APPROVED")
        assert disk_spent(session) == pytest.approx(approved * 10.0)

    def test_released_reservations_do_not_consume_budget(self, tmp_path, worker_script):
        session = make_session(tmp_path, 100.0)
        tags = run_workers(worker_script, session, 5, 20, mode="release")
        assert tags.count("RELEASED") >= 1, tags
        assert disk_spent(session) == pytest.approx(0.0, abs=1e-6)
        # Budget is available again afterwards.
        tags = run_workers(worker_script, session, 5, 20, mode="commit")
        assert tags.count("APPROVED") == 5
        assert disk_spent(session) == pytest.approx(100.0)

    def test_mixed_commit_and_release_never_exceeds_cap(self, tmp_path, worker_script):
        session = make_session(tmp_path, 50.0)
        procs = []
        for i in range(10):
            mode = "commit" if i % 2 == 0 else "release"
            procs.append(
                subprocess.Popen(
                    [sys.executable, worker_script, session, "10", mode],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        for p in procs:
            p.communicate(timeout=60)
        assert disk_spent(session) <= 50.0

    def test_no_leftover_temp_files(self, tmp_path, worker_script):
        """Per-PID temp names must still be cleaned up by replace()."""
        session = make_session(tmp_path, 100.0)
        run_workers(worker_script, session, 10, 10)
        leftovers = [f for f in os.listdir(tmp_path) if ".tmp" in f]
        assert not leftovers, f"leaked temp files: {leftovers}"

    def test_lock_file_is_owner_only(self, tmp_path, worker_script):
        session = make_session(tmp_path, 100.0)
        run_workers(worker_script, session, 2, 10)
        lock = session + ".lock"
        if os.path.exists(lock):
            mode = os.stat(lock).st_mode & 0o777
            assert mode == 0o600, f"lock file mode {oct(mode)}, expected 0600"


class TestDiskIsAuthoritative:
    def test_fresh_process_adopts_persisted_total(self, tmp_path):
        """A new process must see what a previous one already spent."""
        from vida.secure_wallet import SecureVida

        session = make_session(tmp_path, 100.0)

        def wallet():
            v = SecureVida.__new__(SecureVida)
            v.session_limits = {
                "max_kas_per_tx": 0,
                "max_kas_per_day": 100.0,
                "allowed_destinations": None,
            }
            v.session_expires_at = time.time() + 3600
            v.session_daily_spent = 0.0
            v._session_spend_day = time.strftime("%Y-%m-%d", time.gmtime())
            v._session_file = session
            v._session_machine_key = None
            v.address = "kaspatest:qowner"
            return v

        a = wallet()
        assert a.reserve_session_spend(60.0, "kaspatest:qd") is None
        a.record_session_spend(60.0)

        b = wallet()  # fresh process, starts at 0.0 in memory
        assert b.reserve_session_spend(60.0, "kaspatest:qd") is not None, "fresh process ignored the persisted counter"
        assert b.reserve_session_spend(40.0, "kaspatest:qd") is None

    def test_sequential_fresh_processes_hit_cap_exactly(self, tmp_path):
        from vida.secure_wallet import SecureVida

        session = make_session(tmp_path, 100.0)
        approved = 0
        for _ in range(20):
            v = SecureVida.__new__(SecureVida)
            v.session_limits = {
                "max_kas_per_tx": 0,
                "max_kas_per_day": 100.0,
                "allowed_destinations": None,
            }
            v.session_expires_at = time.time() + 3600
            v.session_daily_spent = 0.0
            v._session_spend_day = time.strftime("%Y-%m-%d", time.gmtime())
            v._session_file = session
            v._session_machine_key = None
            v.address = "kaspatest:qowner"
            if v.reserve_session_spend(10.0, "kaspatest:qd") is None:
                v.record_session_spend(10.0)
                approved += 1
        assert approved == 10
        assert disk_spent(session) == pytest.approx(100.0)
