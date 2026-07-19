"""Subscription manager — recurring agent pot subscriptions.

Agents can set up recurring covenant pots that auto-renew on a schedule.
Subscriptions get a 15% fee discount.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from .models import CovenantTerms


@dataclass
class Subscription:
    """A recurring covenant pot subscription."""
    id: str
    counterparty_id: str
    terms: CovenantTerms
    amount_kas_per_cycle: float
    interval_hours: int          # 168 = weekly, 720 = monthly
    auto_renew: bool = True
    created_at: float = field(default_factory=time.time)
    last_renewed_at: float = 0.0
    next_renewal_at: float = 0.0
    total_cycles: int = 0
    active: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["terms"] = self.terms.to_dict()
        return d
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Subscription:
        return cls(
            id=d["id"],
            counterparty_id=d["counterparty_id"],
            terms=CovenantTerms.from_dict(d.get("terms", {})),
            amount_kas_per_cycle=d.get("amount_kas_per_cycle", 0),
            interval_hours=d.get("interval_hours", 720),
            auto_renew=d.get("auto_renew", True),
            created_at=d.get("created_at", time.time()),
            last_renewed_at=d.get("last_renewed_at", 0.0),
            next_renewal_at=d.get("next_renewal_at", 0.0),
            total_cycles=d.get("total_cycles", 0),
            active=d.get("active", True),
        )


SUBSCRIPTION_DISCOUNT = 0.15  # 15% off fees for subscriptions


class SubscriptionManager:
    """Manages recurring covenant pot subscriptions."""
    
    def __init__(self, storage_path: str = ""):
        if not storage_path:
            storage_path = str(Path.home() / ".vida" / "subscriptions.json")
        self._path = Path(storage_path)
        self._subscriptions: dict[str, Subscription] = {}
        self._load()
    
    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for s in data.get("subscriptions", []):
                    sub = Subscription.from_dict(s)
                    self._subscriptions[sub.id] = sub
            except (json.JSONDecodeError, KeyError):
                pass
    
    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "subscriptions": [s.to_dict() for s in self._subscriptions.values()],
        }
        self._path.write_text(json.dumps(data, indent=2))
    
    def create(self, sub: Subscription) -> Subscription:
        """Create a new subscription."""
        # Set up renewal schedule
        now = time.time()
        sub.last_renewed_at = now
        sub.next_renewal_at = now + (sub.interval_hours * 3600)
        sub.total_cycles = 0
        sub.active = True
        self._subscriptions[sub.id] = sub
        self._save()
        return sub
    
    def renew(self, sub_id: str) -> Optional[Subscription]:
        """Renew a subscription for another cycle."""
        sub = self._subscriptions.get(sub_id)
        if not sub or not sub.active:
            return None
        
        now = time.time()
        sub.last_renewed_at = now
        sub.next_renewal_at = now + (sub.interval_hours * 3600)
        sub.total_cycles += 1
        self._save()
        return sub
    
    def cancel(self, sub_id: str) -> bool:
        """Cancel a subscription."""
        sub = self._subscriptions.get(sub_id)
        if not sub:
            return False
        sub.active = False
        sub.auto_renew = False
        self._save()
        return True
    
    def get(self, sub_id: str) -> Optional[Subscription]:
        return self._subscriptions.get(sub_id)
    
    def list_active(self) -> list[Subscription]:
        return [s for s in self._subscriptions.values() if s.active]
    
    def due_for_renewal(self) -> list[Subscription]:
        """Get active subscriptions that are due for renewal."""
        now = time.time()
        return [
            s for s in self._subscriptions.values()
            if s.active and s.next_renewal_at <= now
        ]
    
    def discount_for(self, sub_id: str) -> float:
        """Get the subscription discount rate for a subscription."""
        if sub_id in self._subscriptions:
            return SUBSCRIPTION_DISCOUNT
        return 0.0
    
    def stats(self) -> dict[str, Any]:
        active = self.list_active()
        return {
            "total": len(self._subscriptions),
            "active": len(active),
            "total_cycles": sum(s.total_cycles for s in self._subscriptions.values()),
        }