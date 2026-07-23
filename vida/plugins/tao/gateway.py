"""
Agentic subnet gateway — automated discovery, quality scoring, consumption.

The layer that makes Vida genuinely differentiated:
  1. Agent asks "I need LLM inference" → discovers best subnet
  2. Pays via x402 within session budget
  3. Consumes service → returns result to agent
  4. Tracks quality → future queries route to best performers

All under session-gated policy. Master keys never enter agent context.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from .subnet_client import (
    _apply_subnet_query_fee,
    _call_subnet_api,
    _increment_query_count,
)
from .subnet_marketplace import (
    ServiceType,
    SubnetRegistry,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Subnet Quality Scoring
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SubnetPerformance:
    """Tracked performance metrics for a subnet."""

    netuid: int
    total_queries: int = 0
    successful_queries: int = 0
    total_latency_ms: float = 0.0
    total_cost_tao: float = 0.0
    last_query_time: str = ""
    last_error: str = ""
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_queries == 0:
            return 1.0
        return self.successful_queries / self.total_queries

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_queries == 0:
            return float("inf")
        return self.total_latency_ms / self.successful_queries

    @property
    def avg_cost_tao(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.total_cost_tao / self.total_queries

    @property
    def quality_score(self) -> float:
        """Composite quality score (0.0–1.0). Weighted: success_rate × (1 / (1 + latency_seconds))."""
        if self.total_queries < 3:
            return 0.5  # Not enough data — neutral
        latency_seconds = self.avg_latency_ms / 1000
        latency_factor = 1.0 / (1.0 + latency_seconds)
        penalty = 0.5**self.consecutive_failures
        return self.success_rate * latency_factor * penalty


# ═══════════════════════════════════════════════════════════════════
# Session Budget Policy for TAO Subnet Operations
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SubnetBudget:
    """Session-scoped budget for subnet service consumption."""

    max_spend_tao: float = 0.0
    spent_tao: float = 0.0
    max_queries: int = 0
    query_count: int = 0
    allowed_service_types: List[str] = field(default_factory=list)  # Empty = all allowed
    allowed_netuids: List[int] = field(default_factory=list)  # Empty = all allowed
    created: str = ""
    expires: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat()

    @property
    def remaining_tao(self) -> float:
        return max(0.0, self.max_spend_tao - self.spent_tao)

    @property
    def remaining_queries(self) -> int:
        if self.max_queries == 0:
            return 999  # Unlimited
        return max(0, self.max_queries - self.query_count)

    @property
    def is_exhausted(self) -> bool:
        if self.max_spend_tao > 0 and self.remaining_tao <= 0:
            return True
        if self.max_queries > 0 and self.remaining_queries <= 0:
            return True
        return False

    def can_afford(self, amount_tao: float) -> bool:
        return amount_tao <= self.remaining_tao

    def can_query(self) -> bool:
        return not self.is_exhausted

    def check_service_allowed(self, service_type: str, netuid: int) -> bool:
        if self.allowed_service_types and service_type not in self.allowed_service_types:
            return False
        if self.allowed_netuids and netuid not in self.allowed_netuids:
            return False
        return True

    def record_spend(self, amount_tao: float):
        self.spent_tao += amount_tao
        self.query_count += 1

    def to_session_policy(self) -> Dict[str, Any]:
        """Export as session policy field for secure_wallet integration."""
        return {
            "subnet_max_spend_tao": self.max_spend_tao,
            "subnet_max_queries": self.max_queries,
            "subnet_allowed_service_types": self.allowed_service_types,
            "subnet_allowed_netuids": self.allowed_netuids,
        }

    @classmethod
    def from_session_policy(cls, policy: Dict[str, Any]) -> "SubnetBudget":
        return cls(
            max_spend_tao=float(policy.get("subnet_max_spend_tao", 0)),
            max_queries=int(policy.get("subnet_max_queries", 0)),
            allowed_service_types=policy.get("subnet_allowed_service_types", []),
            allowed_netuids=policy.get("subnet_allowed_netuids", []),
        )


# ═══════════════════════════════════════════════════════════════════
# Autonomous Subnet Gateway
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AutonomousGateway:
    """One-call subnet service consumption with quality routing.

    Agent says "I need LLM inference on this prompt" → gateway:
      1. Discovers subnets offering LLM inference
      2. Ranks by quality score + cost
      3. Pays via x402 within session budget
      4. Queries the best subnet
      5. Returns result + updates quality metrics
    """

    budget: SubnetBudget = field(default_factory=SubnetBudget)
    performance: Dict[int, SubnetPerformance] = field(default_factory=dict)
    substrate_client: Any = None
    coldkey_hex: str = ""
    wallet_id: str = ""

    def discover(
        self,
        service_type: str = "",
        capability: str = "",
        min_quality: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Discover subnets matching criteria, ranked by quality."""
        results = []

        if service_type:
            try:
                st = ServiceType(service_type)
                matches = SubnetRegistry.search(service_type=st)
            except ValueError:
                matches = SubnetRegistry.find_by_capability(service_type)
        elif capability:
            matches = SubnetRegistry.find_by_capability(capability)
        else:
            matches = SubnetRegistry.list_all()

        # Enrich with quality scores
        for match in matches:
            netuid = int(match["netuid"]) if isinstance(match, dict) else match.netuid
            perf = self.performance.get(netuid, SubnetPerformance(netuid=netuid))
            score = perf.quality_score
            if score >= min_quality:
                entry = match if isinstance(match, dict) else match.to_dict()
                entry["quality_score"] = round(score, 3)
                entry["success_rate"] = round(perf.success_rate, 3)
                entry["avg_latency_ms"] = round(perf.avg_latency_ms, 1)
                results.append(entry)
        # Sort by quality descending
        results.sort(key=lambda r: r.get("quality_score", 0), reverse=True)
        return results

    def consume(
        self,
        capability: str,
        prompt: Any = None,
        endpoint_path: str = "",
        max_cost_tao: float = 0.01,
        prefer_quality: bool = True,
    ) -> Dict[str, Any]:
        """Discover → pay → consume in one call.

        Args:
            capability: What the agent needs (e.g., "llm", "image", "compute")
            prompt: The input to send to the subnet
            endpoint_path: Specific API path on the subnet
            max_cost_tao: Maximum to spend (checked against budget)
            prefer_quality: True = pick best quality, False = pick cheapest

        Returns:
            Result with the subnet response + metadata (which subnet, cost, latency)
        """
        # 1. Discover
        candidates = self.discover(capability=capability, min_quality=0.3)
        if not candidates:
            return {"ok": False, "error": f"no subnets found for '{capability}'"}

        # 2. Filter by budget
        affordable = [
            c
            for c in candidates
            if self.budget.can_afford(max_cost_tao)
            and self.budget.check_service_allowed(
                c.get("service_type", ""),
                c.get("netuid", 0),
            )
        ]
        if not affordable:
            return {
                "ok": False,
                "error": f"no affordable subnets. budget remaining: {self.budget.remaining_tao} TAO",
                "budget_remaining": self.budget.remaining_tao,
            }

        # 3. Pick best or cheapest
        if prefer_quality:
            best = affordable[0]  # Already sorted by quality
        else:
            best = min(affordable, key=lambda c: c.get("pricing_tao", float("inf")))

        netuid = best["netuid"]
        info = SubnetRegistry.get_by_netuid(netuid)
        if not info:
            return {"ok": False, "error": f"subnet {netuid} info not found"}

        # 4. Query
        start = time.monotonic()
        result = _call_subnet_api(
            f"{info.api_endpoint.rstrip('/')}/{endpoint_path.lstrip('/')}" if endpoint_path else info.api_endpoint,
            method="POST",
            body=prompt if isinstance(prompt, dict) else {"prompt": str(prompt)} if prompt else None,
            timeout=30,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        # 5. Track quality
        self._record_performance(netuid, result.get("ok", False), elapsed_ms, max_cost_tao)

        # 6. Record spend
        self.budget.record_spend(max_cost_tao)

        # 7. Track query count
        if self.wallet_id:
            _increment_query_count(self.wallet_id)
        fee_info = _apply_subnet_query_fee(max_cost_tao, wallet_id=self.wallet_id)

        return {
            "ok": result.get("ok", False),
            "subnet": best["name"],
            "netuid": netuid,
            "data": result.get("data", result),
            "latency_ms": round(elapsed_ms, 1),
            "cost_tao": max_cost_tao,
            "vida_fee": fee_info,
            "quality_score": round(best.get("quality_score", 0), 3),
            "budget_remaining": round(self.budget.remaining_tao, 6),
        }

    def _record_performance(self, netuid: int, success: bool, latency_ms: float, cost_tao: float):
        """Update quality metrics for a subnet."""
        if netuid not in self.performance:
            self.performance[netuid] = SubnetPerformance(netuid=netuid)

        perf = self.performance[netuid]
        perf.total_queries += 1
        perf.total_cost_tao += cost_tao
        perf.last_query_time = datetime.now(timezone.utc).isoformat()

        if success:
            perf.successful_queries += 1
            perf.total_latency_ms += latency_ms
            perf.consecutive_failures = 0
            perf.last_error = ""
        else:
            perf.consecutive_failures += 1

    def get_performance_report(self) -> Dict[str, Any]:
        """Human-readable quality report for all tracked subnets."""
        report = {}
        for netuid, perf in sorted(self.performance.items()):
            info = SubnetRegistry.get_by_netuid(netuid)
            report[str(netuid)] = {
                "name": info.name if info else f"subnet-{netuid}",
                "quality_score": round(perf.quality_score, 3),
                "success_rate": round(perf.success_rate, 3),
                "avg_latency_ms": round(perf.avg_latency_ms, 1),
                "avg_cost_tao": round(perf.avg_cost_tao, 6),
                "total_queries": perf.total_queries,
                "consecutive_failures": perf.consecutive_failures,
            }
        return {
            "subnets_tracked": len(report),
            "subnets": report,
            "budget_spent": round(self.budget.spent_tao, 6),
            "budget_remaining": round(self.budget.remaining_tao, 6),
        }


# ═══════════════════════════════════════════════════════════════════
# High-Level Agent Tool
# ═══════════════════════════════════════════════════════════════════


def agent_consume_subnet_service(
    capability: str,
    prompt: str = "",
    max_cost_tao: float = 0.01,
    budget_tao: float = 0.1,
    wallet_id: str = "",
    substrate_client: Any = None,
    coldkey_hex: str = "",
) -> Dict[str, Any]:
    """One-call subnet service consumption for agents.

    The agent says what it needs, Vida handles the rest:
      discovery → quality routing → payment → consumption → result.

    Args:
        capability: What service the agent needs (e.g., "llm", "image", "compute")
        prompt: The input to send
        max_cost_tao: Max to spend on this query
        budget_tao: Total session budget for subnet operations
        wallet_id: Agent wallet ID for tracking
    """
    budget = SubnetBudget(
        max_spend_tao=budget_tao,
        max_queries=0,  # Unlimited until budget exhausted
    )

    gateway = AutonomousGateway(
        budget=budget,
        substrate_client=substrate_client,
        coldkey_hex=coldkey_hex,
        wallet_id=wallet_id,
    )

    return gateway.consume(
        capability=capability,
        prompt=prompt,
        max_cost_tao=max_cost_tao,
        prefer_quality=True,
    )
