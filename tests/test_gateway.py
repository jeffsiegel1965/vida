"""Real-world tests for the autonomous subnet gateway.

Tests subnet discovery, quality scoring, budget enforcement,
and error handling with live registry data.
"""

import socket

import pytest

from vida.plugins.tao.gateway import (
    AutonomousGateway,
    SubnetBudget,
    SubnetPerformance,
    agent_consume_subnet_service,
)
from vida.plugins.tao.subnet_marketplace import ServiceType, SubnetRegistry


def _has_network() -> bool:
    """Check if the CI/test environment can reach subnet endpoints."""
    try:
        s = socket.create_connection(("api.subnet1.ai", 443), timeout=3)
        s.close()
        return True
    except OSError:
        return False


requires_network = pytest.mark.skipif(
    not _has_network(),
    reason="Subnet API endpoints not reachable in this environment",
)


class TestSubnetBudget:
    def test_initial_state(self):
        b = SubnetBudget(max_spend_tao=1.0, max_queries=100)
        assert b.remaining_tao == 1.0
        assert b.remaining_queries == 100
        assert not b.is_exhausted

    def test_spend_tracking(self):
        b = SubnetBudget(max_spend_tao=1.0, max_queries=10)
        b.record_spend(0.3)
        assert b.remaining_tao == 0.7
        assert b.remaining_queries == 9
        assert b.spent_tao == 0.3

    def test_exhausted_by_tao(self):
        b = SubnetBudget(max_spend_tao=0.1, max_queries=100)
        b.record_spend(0.1)
        assert b.is_exhausted
        assert not b.can_afford(0.01)
        assert not b.can_query()

    def test_exhausted_by_queries(self):
        b = SubnetBudget(max_spend_tao=10.0, max_queries=1)
        b.record_spend(0.01)
        assert b.is_exhausted

    def test_unlimited_queries(self):
        b = SubnetBudget(max_spend_tao=1.0, max_queries=0)
        assert b.remaining_queries == 999
        b.record_spend(0.01)
        assert not b.is_exhausted

    def test_service_filtering(self):
        b = SubnetBudget(
            max_spend_tao=1.0,
            allowed_service_types=["llm_inference"],
            allowed_netuids=[19],
        )
        assert b.check_service_allowed("llm_inference", 19)
        assert not b.check_service_allowed("compute", 14)
        assert not b.check_service_allowed("llm_inference", 9)

    def test_session_policy_roundtrip(self):
        original = SubnetBudget(
            max_spend_tao=5.0,
            max_queries=200,
            allowed_service_types=["llm_inference", "image_gen"],
            allowed_netuids=[19, 34],
        )
        policy = original.to_session_policy()
        restored = SubnetBudget.from_session_policy(policy)
        assert restored.max_spend_tao == 5.0
        assert restored.max_queries == 200
        assert restored.allowed_service_types == ["llm_inference", "image_gen"]
        assert restored.allowed_netuids == [19, 34]


class TestSubnetPerformance:
    def test_no_data_neutral(self):
        p = SubnetPerformance(netuid=1)
        assert p.quality_score == 0.5

    def test_perfect_performance(self):
        p = SubnetPerformance(
            netuid=1,
            total_queries=100,
            successful_queries=100,
            total_latency_ms=10000,  # 10ms avg
        )
        assert p.success_rate == 1.0
        assert p.quality_score > 0.9

    def test_poor_performance(self):
        p = SubnetPerformance(
            netuid=2,
            total_queries=100,
            successful_queries=30,
            total_latency_ms=300000,  # 3s avg
        )
        assert p.success_rate == 0.3
        assert p.quality_score < 0.3

    def test_consecutive_failures_penalty(self):
        p = SubnetPerformance(
            netuid=3,
            total_queries=10,
            successful_queries=8,
            total_latency_ms=1000,
            consecutive_failures=5,
        )
        score_with_fails = p.quality_score
        p.consecutive_failures = 0
        score_without_fails = p.quality_score
        assert score_with_fails < score_without_fails


class TestGatewayDiscovery:
    def test_discover_by_capability(self):
        gw = AutonomousGateway()
        results = gw.discover(capability="llm")
        assert len(results) >= 1
        assert results[0]["quality_score"] == 0.5  # Neutral — no data yet

    def test_discover_by_type(self):
        gw = AutonomousGateway()
        results = gw.discover(service_type="llm_inference")
        assert len(results) >= 1

    def test_discover_min_quality_filter(self):
        gw = AutonomousGateway()
        all_results = gw.discover(capability="compute")
        filtered = gw.discover(capability="compute", min_quality=0.9)
        assert len(filtered) <= len(all_results)

    def test_discover_nonexistent(self):
        gw = AutonomousGateway()
        results = gw.discover(capability="nonexistent_service")
        assert len(results) == 0

    def test_results_sorted_by_quality(self):
        gw = AutonomousGateway()
        results = gw.discover(capability="compute")
        if len(results) >= 2:
            scores = [r["quality_score"] for r in results]
            assert scores == sorted(scores, reverse=True)


@requires_network
class TestGatewayConsumption:
    def test_consume_no_affordable(self):
        """Attempting to spend more than budget returns error gracefully."""
        budget = SubnetBudget(max_spend_tao=0.001, max_queries=10)
        gw = AutonomousGateway(budget=budget)
        result = gw.consume(capability="llm", max_cost_tao=1.0)
        assert not result["ok"]
        assert "no affordable" in result.get("error", "").lower()

    def test_consume_budget_exhausted(self):
        """When budget is exhausted, consume fails before API call."""
        budget = SubnetBudget(max_spend_tao=0.0, max_queries=10)
        gw = AutonomousGateway(budget=budget)
        result = gw.consume(capability="llm", max_cost_tao=0.001)
        assert not result["ok"]

    def test_consume_tracks_performance_on_failure(self):
        """Even failed API calls get tracked for quality scoring."""
        budget = SubnetBudget(max_spend_tao=1.0, max_queries=100)
        gw = AutonomousGateway(budget=budget)
        result = gw.consume(capability="agents", max_cost_tao=0.001)
        # Should have tracked at least one subnet
        assert len(gw.performance) >= 1
        if gw.performance:
            perf = list(gw.performance.values())[0]
            assert perf.total_queries >= 1

    def test_consume_returns_budget_info(self):
        budget = SubnetBudget(max_spend_tao=1.0, max_queries=100)
        gw = AutonomousGateway(budget=budget)
        result = gw.consume(capability="llm", max_cost_tao=0.001)
        assert "budget_remaining" in result
        assert "quality_score" in result

    def test_performance_report(self):
        budget = SubnetBudget(max_spend_tao=1.0, max_queries=100)
        gw = AutonomousGateway(budget=budget)
        gw.consume(capability="llm", max_cost_tao=0.001)
        report = gw.get_performance_report()
        assert "subnets_tracked" in report
        assert "budget_spent" in report
        assert "subnets" in report


@requires_network
class TestAgentToolIntegration:
    def test_high_level_entry_point(self):
        """agent_consume_subnet_service returns valid structure."""
        result = agent_consume_subnet_service(
            capability="llm",
            prompt="test prompt",
            max_cost_tao=0.001,
            budget_tao=0.1,
        )
        assert "ok" in result
        assert "subnet" in result
        assert "cost_tao" in result

    def test_budget_exhausted_in_high_level(self):
        """High-level API respects budget."""
        result = agent_consume_subnet_service(
            capability="llm",
            prompt="test",
            max_cost_tao=1.0,
            budget_tao=0.0,
        )
        assert not result["ok"]


class TestRegistryCoverage:
    """Verify the subnet registry has expected coverage."""

    def test_registry_has_essential_categories(self):
        subnets = SubnetRegistry.list_all()
        service_types = set()
        for s in subnets:
            st = s.get("service_type", "") if isinstance(s, dict) else s.service_type
            if st:
                service_types.add(st)

        essential = {"llm_inference", "compute", "storage", "image_gen"}
        missing = essential - service_types
        assert not missing, f"Missing essential service types: {missing}"

    def test_most_subnets_have_endpoints(self):
        subnets = SubnetRegistry.list_all()
        with_endpoints = sum(
            1 for s in subnets
            if (s.get("api_endpoint") if isinstance(s, dict) else getattr(s, "api_endpoint", ""))
        )
        assert with_endpoints >= len(subnets) - 2  # At most 2 without endpoints
