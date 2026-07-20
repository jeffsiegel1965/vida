"""
Covenant pot simulator — offline lifecycle simulation.

Simulates the full lifecycle of a covenant agent pot:
  plan → fund → spend → settlement

No real KAS, no live network. Useful for testing, demonstration,
and verification before live deployment.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .agent_pot import SOMPI_PER_KAS, plan_agent_pot
from .agent_pot_script import build_agent_pot_script_template
from .fees import calc_fund_fee, calc_spend_fee, get_fee_address
from .pot_spend import check_spend_kas


@dataclass
class SimulatedPot:
    """State of a simulated covenant pot."""

    wallet_id: str
    policy: dict[str, Any]
    policy_hash: str
    balance_sompi: int = 0
    total_funded_sompi: int = 0
    total_spent_sompi: int = 0
    total_fees_sompi: int = 0
    events: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "planned"  # planned | funded | active | spent | depleted

    @property
    def balance_kas(self) -> float:
        return self.balance_sompi / SOMPI_PER_KAS

    def summary(self) -> dict:
        return {
            "wallet_id": self.wallet_id,
            "status": self.status,
            "balance_kas": round(self.balance_kas, 6),
            "balance_sompi": self.balance_sompi,
            "total_funded_kas": round(self.total_funded_sompi / SOMPI_PER_KAS, 6),
            "total_spent_kas": round(self.total_spent_sompi / SOMPI_PER_KAS, 6),
            "total_fees_kas": round(self.total_fees_sompi / SOMPI_PER_KAS, 6),
            "events": len(self.events),
            "policy_hash": self.policy_hash[:16],
            "max_tx_sompi": self.policy.get("max_tx_sompi", 0),
            "dest_count": len(self.policy.get("allowed_destinations", [])),
        }


class CovenantSimulator:
    """Simulate the full covenant pot lifecycle offline."""

    def __init__(self):
        self._pots: dict[str, SimulatedPot] = {}

    def plan(self, wallet_id: str, max_kas_per_tx: float, max_kas_per_day: float,
             allowed_destinations: Optional[list[str]] = None,
             network: str = "mainnet") -> dict[str, Any]:
        """Plan a new covenant pot. Returns pot plan + fee breakdown."""
        if wallet_id in self._pots:
            return {"ok": False, "error": f"pot already exists for {wallet_id}"}

        plan = plan_agent_pot(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations or [],
        )
        if not plan.get("ok"):
            return plan

        template = build_agent_pot_script_template(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations or [],
        )
        if not template.get("ok"):
            return {"ok": False, "error": template.get("error")}

        fee = calc_fund_fee(float(plan["fund_pot_kas"]))
        policy = template["policy"]

        pot = SimulatedPot(
            wallet_id=wallet_id,
            policy=policy,
            policy_hash=template["policy_hash"],
        )
        self._pots[wallet_id] = pot

        return {
            "ok": True,
            "wallet_id": wallet_id,
            "status": "planned",
            "fund_plan": plan,
            "policy_template": template,
            "fee": {
                "dev_fee_kas": fee,
                "dev_address": get_fee_address(network),
            },
            "pot": pot.summary(),
        }

    def fund(self, wallet_id: str, amount_kas: float) -> dict[str, Any]:
        """Simulate funding a covenant pot."""
        pot = self._pots.get(wallet_id)
        if not pot:
            return {"ok": False, "error": f"no pot for {wallet_id}"}
        if pot.status != "planned":
            return {"ok": False, "error": f"pot already {pot.status}"}

        amount_sompi = int(round(amount_kas * SOMPI_PER_KAS))
        if amount_sompi <= 0:
            return {"ok": False, "error": "amount must be positive"}

        fee = calc_fund_fee(amount_kas)
        fee_sompi = int(round(fee * SOMPI_PER_KAS))
        net_sompi = amount_sompi - fee_sompi

        if net_sompi <= 0:
            return {"ok": False, "error": "amount too small after fee"}

        pot.balance_sompi = net_sompi
        pot.total_funded_sompi = net_sompi
        pot.total_fees_sompi = fee_sompi
        pot.status = "funded"
        pot.events.append({
            "type": "fund",
            "amount_sompi": amount_sompi,
            "fee_sompi": fee_sompi,
            "net_sompi": net_sompi,
            "timestamp": time.time(),
        })

        return {
            "ok": True,
            "wallet_id": wallet_id,
            "status": "funded",
            "amount_kas": amount_kas,
            "fee_kas": fee,
            "net_kas": round(net_sompi / SOMPI_PER_KAS, 6),
            "pot": pot.summary(),
        }

    def spend(self, wallet_id: str, amount_kas: float, destination: str,
              owner_address: Optional[str] = None) -> dict[str, Any]:
        """Simulate spending from a covenant pot."""
        pot = self._pots.get(wallet_id)
        if not pot:
            return {"ok": False, "error": f"no pot for {wallet_id}"}
        if pot.status not in ("funded", "active"):
            return {"ok": False, "error": f"pot not funded (status={pot.status})"}

        amount_sompi = int(round(amount_kas * SOMPI_PER_KAS))

        # Check policy
        check = check_spend_kas(
            policy=pot.policy,
            amount_kas=amount_kas,
            destination=destination,
            owner_address=owner_address,
        )
        if not check.get("ok"):
            return {"ok": False, "error": check.get("error", "policy rejected")}

        # Check balance
        fee = calc_spend_fee(amount_kas)
        fee_sompi = int(round(fee * SOMPI_PER_KAS))
        total_sompi = amount_sompi + fee_sompi

        if total_sompi > pot.balance_sompi:
            return {
                "ok": False,
                "error": f"insufficient balance: need {total_sompi}, have {pot.balance_sompi}",
            }

        pot.balance_sompi -= total_sompi
        pot.total_spent_sompi += amount_sompi
        pot.total_fees_sompi += fee_sompi
        pot.status = "active" if pot.balance_sompi > 0 else "depleted"
        pot.events.append({
            "type": "spend",
            "amount_sompi": amount_sompi,
            "fee_sompi": fee_sompi,
            "destination": destination,
            "rule": check.get("rule", "allowed"),
            "remaining_sompi": pot.balance_sompi,
            "timestamp": time.time(),
        })

        covenant_continues = pot.balance_sompi > 0

        return {
            "ok": True,
            "wallet_id": wallet_id,
            "amount_kas": amount_kas,
            "fee_kas": fee,
            "destination": destination,
            "remaining_kas": round(pot.balance_sompi / SOMPI_PER_KAS, 6),
            "covenant_continues": covenant_continues,
            "status": pot.status,
            "pot": pot.summary(),
        }

    def reclaim(self, wallet_id: str, owner_address: str) -> dict[str, Any]:
        """Simulate owner reclaiming remaining pot balance."""
        pot = self._pots.get(wallet_id)
        if not pot:
            return {"ok": False, "error": f"no pot for {wallet_id}"}
        if pot.balance_sompi <= 0:
            return {"ok": False, "error": "pot already depleted"}

        remaining = pot.balance_sompi
        remaining_kas = remaining / SOMPI_PER_KAS

        pot.events.append({
            "type": "reclaim",
            "amount_sompi": remaining,
            "owner": owner_address,
            "timestamp": time.time(),
        })
        pot.balance_sompi = 0
        pot.status = "depleted"

        return {
            "ok": True,
            "wallet_id": wallet_id,
            "reclaimed_kas": round(remaining_kas, 6),
            "status": "depleted",
            "pot": pot.summary(),
        }

    def status(self, wallet_id: str) -> dict[str, Any]:
        """Get current pot status."""
        pot = self._pots.get(wallet_id)
        if not pot:
            return {"ok": False, "error": f"no pot for {wallet_id}"}
        return {"ok": True, "pot": pot.summary(), "events": pot.events[-5:]}

    def list_pots(self) -> list[dict]:
        """List all simulated pots."""
        return [p.summary() for p in self._pots.values()]


# Singleton
_DEFAULT_SIMULATOR: CovenantSimulator | None = None


def get_simulator() -> CovenantSimulator:
    global _DEFAULT_SIMULATOR
    if _DEFAULT_SIMULATOR is None:
        _DEFAULT_SIMULATOR = CovenantSimulator()
    return _DEFAULT_SIMULATOR
