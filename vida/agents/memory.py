"""Vida Agent Memory — persistent cross-session intelligence for agents.

An agent that remembers nothing is useless. This module gives Vida agents:
- Deal history across sessions
- Counterparty reputation tracking  
- Subnet usage history and preferences
- Current context/session state
- Volume discount tracking
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Data models ──


@dataclass
class DealRecord:
    """Record of a completed deal (covenant pot, TAO stake, or subnet purchase)."""
    id: str
    deal_type: str                           # "covenant_pot", "tao_stake", "subnet_purchase"
    counterparty_id: str
    amount_kas: float = 0.0
    amount_tao: float = 0.0
    netuid: int = 0
    terms: dict[str, Any] = field(default_factory=dict)
    txid: str = ""
    success: bool = False
    rounds_to_deal: int = 0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DealRecord:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CounterpartyProfile:
    """Learned profile for a counterparty agent."""
    agent_id: str
    total_deals: int = 0
    total_kas_volume: float = 0.0
    total_tao_volume: float = 0.0
    avg_rounds_to_deal: float = 0.0
    success_rate: float = 1.0
    failed_deals: int = 0
    first_seen: float = 0.0
    last_interaction: float = 0.0
    preferred_template: str = "standard"
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CounterpartyProfile:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SubnetUsageRecord:
    """Record of an agent using a Bittensor subnet."""
    netuid: int
    service_type: str
    requests_made: int = 0
    total_tao_spent: float = 0.0
    last_used: float = 0.0
    favorite: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentContext:
    """The agent's current working context — survives interruptions."""
    current_goal: str = ""
    current_session_id: str = ""
    work_in_progress: dict[str, Any] = field(default_factory=dict)
    last_error: str = ""
    last_success: str = ""
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentContext:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── The Memory Store ──


class AgentMemory:
    """Persistent memory for a Vida agent.
    
    Stores and retrieves everything an agent needs across sessions:
    • Deal history — every transaction the agent made
    • Counterparty profiles — who to trust, who not to
    • Subnet usage — which subnets deliver, which don't
    • Current context — what was the agent doing before it stopped
    
    Usage:
        mem = AgentMemory("agent_wallet_1")
        mem.record_deal(deal_record)
        mem.remember_context("current_goal", "Stake 50 TAO")
        goal = mem.get_context("current_goal")
    """
    
    def __init__(self, wallet_id: str = "default", storage_dir: str = ""):
        if not storage_dir:
            storage_dir = str(Path.home() / ".vida" / "memory")
        self._base = Path(storage_dir) / wallet_id
        self._base.mkdir(parents=True, exist_ok=True)
        self._file = self._base / "memory.json"
        self._loaded = False
        
        # In-memory cache
        self._deals: list[DealRecord] = []
        self._counterparties: dict[str, CounterpartyProfile] = {}
        self._subnets: dict[int, SubnetUsageRecord] = {}
        self._context: AgentContext = AgentContext()
        self._kv_store: dict[str, Any] = {}
        
        self._load()
    
    def _load(self) -> None:
        if not self._file.exists():
            self._loaded = True
            return
        try:
            data = json.loads(self._file.read_text())
            self._deals = [DealRecord.from_dict(d) for d in data.get("deals", [])]
            for k, v in data.get("counterparties", {}).items():
                self._counterparties[k] = CounterpartyProfile.from_dict(v)
            for k, v in data.get("subnets", {}).items():
                self._subnets[int(k)] = SubnetUsageRecord(**v)
            if "context" in data:
                self._context = AgentContext.from_dict(data["context"])
            if "kv" in data:
                self._kv_store = data["kv"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Memory load error: %s", e)
        self._loaded = True
    
    def _save(self) -> None:
        data = {
            "deals": [d.to_dict() for d in self._deals],
            "counterparties": {k: v.to_dict() for k, v in self._counterparties.items()},
            "subnets": {str(k): v.to_dict() for k, v in self._subnets.items()},
            "context": self._context.to_dict(),
            "kv": self._kv_store,
            "version": 1,
            "updated_at": time.time(),
        }
        self._file.write_text(json.dumps(data, indent=2))
    
    # ── Deal history ──
    
    def record_deal(self, deal: DealRecord) -> None:
        """Record a completed deal."""
        self._deals.append(deal)
        
        # Update counterparty profile
        cp = self._counterparties.get(deal.counterparty_id,
                                        CounterpartyProfile(agent_id=deal.counterparty_id))
        cp.total_deals += 1
        cp.total_kas_volume += deal.amount_kas
        cp.total_tao_volume += deal.amount_tao
        if not cp.first_seen:
            cp.first_seen = deal.timestamp
        cp.last_interaction = deal.timestamp
        
        # Rolling average for rounds
        if deal.rounds_to_deal > 0:
            old_total = cp.avg_rounds_to_deal * (cp.total_deals - 1)
            cp.avg_rounds_to_deal = (old_total + deal.rounds_to_deal) / cp.total_deals
        
        if not deal.success:
            cp.failed_deals += 1
        cp.success_rate = (cp.total_deals - cp.failed_deals) / max(cp.total_deals, 1)
        
        self._counterparties[deal.counterparty_id] = cp
        
        # Update subnet usage if applicable
        if deal.netuid > 0:
            sn = self._subnets.get(deal.netuid, SubnetUsageRecord(
                netuid=deal.netuid, service_type=deal.deal_type))
            sn.requests_made += 1
            sn.total_tao_spent += deal.amount_tao
            sn.last_used = deal.timestamp
            self._subnets[deal.netuid] = sn
        
        self._save()
    
    def get_deals(self, limit: int = 20, deal_type: str = "") -> list[dict[str, Any]]:
        """Get recent deals, optionally filtered by type."""
        deals = self._deals
        if deal_type:
            deals = [d for d in deals if d.deal_type == deal_type]
        deals = sorted(deals, key=lambda d: d.timestamp, reverse=True)
        return [d.to_dict() for d in deals[:limit]]
    
    def get_deal_by_id(self, deal_id: str) -> Optional[dict[str, Any]]:
        for d in self._deals:
            if d.id == deal_id:
                return d.to_dict()
        return None
    
    def get_deal_by_txid(self, txid: str) -> Optional[dict[str, Any]]:
        for d in self._deals:
            if d.txid == txid:
                return d.to_dict()
        return None
    
    # ── Counterparty profiles ──
    
    def get_counterparty(self, agent_id: str) -> Optional[dict[str, Any]]:
        cp = self._counterparties.get(agent_id)
        return cp.to_dict() if cp else None
    
    def list_counterparties(self) -> list[dict[str, Any]]:
        return [cp.to_dict() for cp in self._counterparties.values()]
    
    def update_counterparty_profile(self, agent_id: str, **updates) -> None:
        cp = self._counterparties.get(agent_id, CounterpartyProfile(agent_id=agent_id))
        for k, v in updates.items():
            if hasattr(cp, k):
                setattr(cp, k, v)
        self._counterparties[agent_id] = cp
        self._save()
    
    # ── Subnet usage ──
    
    def get_subnet_record(self, netuid: int) -> Optional[dict[str, Any]]:
        sn = self._subnets.get(netuid)
        return sn.to_dict() if sn else None
    
    def list_favorite_subnets(self) -> list[dict[str, Any]]:
        return [sn.to_dict() for sn in self._subnets.values() if sn.favorite]
    
    def mark_subnet_favorite(self, netuid: int) -> None:
        sn = self._subnets.get(netuid, SubnetUsageRecord(netuid=netuid, service_type=""))
        sn.favorite = True
        self._subnets[netuid] = sn
        self._save()
    
    # ── KV store (simple key-value) ──
    
    def put(self, key: str, value: Any) -> None:
        """Store any value by key. Persisted to disk."""
        self._kv_store[key] = value
        self._save()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored value."""
        return self._kv_store.get(key, default)
    
    def delete(self, key: str) -> None:
        self._kv_store.pop(key, None)
        self._save()
    
    # ── Context (what the agent was doing) ──
    
    def set_context(self, **kwargs) -> None:
        """Set context fields. Survives interruptions."""
        for k, v in kwargs.items():
            if hasattr(self._context, k):
                setattr(self._context, k, v)
        self._save()
    
    def get_context(self) -> dict[str, Any]:
        """Get full context dict."""
        return self._context.to_dict()
    
    def clear_context(self) -> None:
        self._context = AgentContext()
        self._save()
    
    # ── Stats ──
    
    def stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        counterparties = len(self._counterparties)
        return {
            "total_deals": len(self._deals),
            "unique_counterparties": counterparties,
            "favorite_subnets": len([s for s in self._subnets.values() if s.favorite]),
            "total_kas_volume": sum(d.amount_kas for d in self._deals),
            "total_tao_volume": sum(d.amount_tao for d in self._deals),
            "active_context": bool(self._context.current_goal),
            "current_goal": self._context.current_goal,
            "last_error": self._context.last_error,
            "storage_file": str(self._file),
        }
    
    def volume_discount_rate(self, counterparty_id: str) -> float:
        """Get volume discount for a counterparty based on total TAO volume."""
        cp = self._counterparties.get(counterparty_id)
        if not cp:
            return 0.0
        total = cp.total_tao_volume + cp.total_kas_volume
        if total >= 10000: return 0.30
        if total >= 1000: return 0.20
        if total >= 100: return 0.10
        return 0.0
    
    def wipe(self) -> None:
        """Reset all memory. Use with caution."""
        self._deals = []
        self._counterparties = {}
        self._subnets = {}
        self._context = AgentContext()
        self._kv_store = {}
        self._save()