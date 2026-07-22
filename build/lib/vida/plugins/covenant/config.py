"""Covenant plugin config — no secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class CovenantConfig:
    network: str = "testnet-10"  # mainnet only after TN10 proofs
    # Live path is gated until post-Toccata SDK is wired
    live_enabled: bool = False
    # Recommended compute budget per signing input (post-Toccata)
    default_compute_budget: int = 10
    max_compute_budget: int = 20
    notes: str = "soft policy now; on-chain after #1074 tooling"


def load_covenant_config(
    *,
    network: Optional[str] = None,
    live_enabled: Optional[bool] = None,
) -> CovenantConfig:
    net = network or os.environ.get("VIDA_COVENANT_NETWORK") or "testnet-10"
    live_env = os.environ.get("VIDA_COVENANT_LIVE", "").strip().lower()
    live = live_enabled if live_enabled is not None else live_env in ("1", "true", "yes")
    # Hard safety: default False; even env live does not claim chain success
    return CovenantConfig(network=net, live_enabled=bool(live))
