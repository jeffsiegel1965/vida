"""Regression tests: session daily-cap race condition.

Found 2026-07-24 during Opus 5 audit, proven by execution.

Root cause: transactions.send() called check_session_spend() at ~line 227 and
record_session_spend() at ~line 342, with the whole UTXO-gather / build / sign
/ broadcast sequence in between and no lock or reservation. Concurrent agent
calls each read the same stale session_daily_spent, so every one of them
passed the daily cap.

Measured before the fix: 20 concurrent 10 KAS spends against a 100 KAS/day
cap -- all 20 approved, 200 KAS committed. A 2x overspend of the owner's
stated daily limit on real funds.

Fix: reserve_session_spend() performs check-and-reserve atomically under an
RLock and counts in-flight reservations against the cap;
record_session_spend() commits and consumes the reservation;
release_session_spend() returns the budget when a send fails before broadcast.
"""

import threading
import time

import pytest

from vida.secure_wallet import SecureVida


def _session_wallet(
    max_tx: float = 0.0,
    max_day: float = 100.0,
    allowed=None,
    expires_in: float = 3600.0,
):
    """Build a SecureVida with session limits, no chain or keyfile needed."""
    v = SecureVida.__new__(SecureVida)
    v.session_limits = {
        "max_kas_per_tx": max_tx,
        "max_kas_per_day": max_day,
        "allowed_destinations": allowed,
    }
    v.session_expires_at = time.time() + expires_in
    v.session_daily_spent = 0.0
    v._session_spend_day = time.strftime("%Y-%m-%d", time.gmtime())
    v._session_file = None
    v._session_machine_key = None
    v.address = "kaspatest:qowner"
    return v


class TestConcurrentDailyCap:
    def test_concurrent_spends_cannot_exceed_daily_cap(self):
        """The exploit: 20 threads x 10 KAS must not exceed a 100 KAS cap."""
        v = _session_wallet(max_day=100.0)
        approved = []
        guard = threading.Lock()

        def attempt(i):
            if v.reserve_session_spend(10.0, dest_address="kaspatest:qdest") is None:
                time.sleep(0.001)  # widen the check->record window
                v.record_session_spend(10.0)
                with guard:
                    approved.append(i)

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert v.session_daily_spent <= 100.0
        assert len(approved) == 10
        assert v._reserved == 0.0

    def test_high_contention_many_small_spends(self):
        """50 threads x 1 KAS against a 10 KAS cap."""
        v = _session_wallet(max_day=10.0)
        approved = []
        guard = threading.Lock()

        def attempt():
            if v.reserve_session_spend(1.0, dest_address="d") is None:
                v.record_session_spend(1.0)
                with guard:
                    approved.append(1)

        threads = [threading.Thread(target=attempt) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(approved) == 10
        assert v.session_daily_spent == pytest.approx(10.0)

    def test_reservation_counted_against_cap(self):
        """An in-flight reservation must block a second spend."""
        v = _session_wallet(max_day=100.0)
        assert v.reserve_session_spend(60.0, dest_address="d") is None
        assert v.reserve_session_spend(60.0, dest_address="d") is not None


class TestReservationLifecycle:
    def test_release_returns_budget(self):
        v = _session_wallet(max_day=100.0)
        assert v.reserve_session_spend(60.0, dest_address="d") is None
        v.release_session_spend(60.0)
        assert v._reserved == 0.0
        assert v.reserve_session_spend(60.0, dest_address="d") is None

    def test_record_consumes_reservation_no_double_count(self):
        v = _session_wallet(max_day=100.0)
        v.reserve_session_spend(40.0, dest_address="d")
        v.record_session_spend(40.0)
        assert v.session_daily_spent == pytest.approx(40.0)
        assert v._reserved == 0.0

    def test_release_never_goes_negative(self):
        v = _session_wallet(max_day=100.0)
        v.release_session_spend(10.0)
        assert v._reserved >= 0.0

    def test_full_cap_then_rejected(self):
        v = _session_wallet(max_day=100.0)
        assert v.reserve_session_spend(100.0, dest_address="d") is None
        v.record_session_spend(100.0)
        assert v.reserve_session_spend(0.1, dest_address="d") is not None


class TestOtherCapsStillEnforced:
    """The reserve path must not weaken any existing gate."""

    def test_per_tx_cap(self):
        v = _session_wallet(max_tx=5.0, max_day=100.0)
        assert v.reserve_session_spend(6.0, dest_address="d") is not None
        assert v.reserve_session_spend(5.0, dest_address="d") is None

    def test_destination_allowlist(self):
        v = _session_wallet(allowed=["kaspatest:qgood"])
        assert v.reserve_session_spend(1.0, dest_address="kaspatest:qevil") is not None
        assert v.reserve_session_spend(1.0, dest_address="kaspatest:qgood") is None

    def test_empty_allowlist_denies_all(self):
        v = _session_wallet(allowed=[])
        assert v.reserve_session_spend(1.0, dest_address="kaspatest:qany") is not None

    def test_expired_session(self):
        v = _session_wallet(expires_in=-1)
        assert v.reserve_session_spend(1.0, dest_address="d") is not None

    def test_non_finite_amount_rejected(self):
        v = _session_wallet()
        for bad in (float("nan"), float("inf"), float("-inf")):
            assert v.reserve_session_spend(bad, dest_address="d") is not None

    def test_owner_unlock_has_no_caps(self):
        """session_limits None means an owner password unlock: no session cap."""
        v = _session_wallet()
        v.session_limits = None
        assert v.reserve_session_spend(10_000_000.0, dest_address="d") is None
