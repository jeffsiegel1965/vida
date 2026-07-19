"""Agent orchestrator — the missing agent loop.

Implements the Observation → Thought → Action → Observation cycle
using Vida's covenant tools. Agents can decompose goals, select tools,
and execute multi-step plans.

Usage:
    from vida.agents.orchestrator import AgentOrchestrator
    
    async def main():
        orch = AgentOrchestrator()
        result = await orch.run(
            goal="Stake 100 TAO with highest APY, auto-compound weekly",
            context={"session": session},
        )
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from vida.plugins.covenant import (
    covenant_describe,
    covenant_live_gates,
    covenant_plan_pot,
    covenant_quine_info,
    covenant_spend_policy_check,
    covenant_status,
)

logger = logging.getLogger("vida.agents")

# ── Tool helpers ──

def _safe_tool(name: str, **kw: Any) -> dict[str, Any]:
    """Safely call a tool by name from the covenant tools module.
    
    Returns {"ok": False, "error": ...} if the tool doesn't exist or errors.
    """
    from vida.plugins.covenant.tools import HERMES_TOOLS
    tool = HERMES_TOOLS.get(name)
    if not tool:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        fn = tool["fn"]
        return fn(**kw) if kw else fn()
    except Exception as e:
        return {"ok": False, "error": f"{name} failed: {e}"}


# ── Type aliases ──

ToolResult = dict[str, Any]
AgentState = dict[str, Any]


class Step:
    """A single step in the agent's execution plan."""
    def __init__(self, id: str, action: str, params: dict[str, Any] = None,
                 status: str = "pending", description: str = "",
                 result: Optional[ToolResult] = None, error: Optional[str] = None):
        self.id = id
        self.action = action
        self.params = params or {}
        self.status = status
        self.description = description
        self.result = result
        self.error = error
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None


@dataclass
class ExecutionPlan:
    """A plan decomposed from a goal into executable steps."""
    goal: str
    steps: list[Step] = field(default_factory=list)
    context: AgentState = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class AgentOrchestrator:
    """Orchestrates agent goal execution using Vida tools.
    
    The orchestrator:
    1. Takes a natural language goal
    2. Decomposes it into a plan using available tools
    3. Executes each step, feeding results back
    4. Reports status and final result
    """
    
    # ── Tool dispatch ──
    # Maps tool names to their implementation functions.
    # WARNING: Each tool must return {"ok": bool, ...}. Do NOT alias tools.
    
    _TOOL_IMPL = {
        "covenant_status": lambda ctx: covenant_status(),
        "covenant_describe": lambda ctx: covenant_describe(),
        "covenant_live_gates": lambda ctx: covenant_live_gates(),
        "covenant_plan_pot": lambda ctx, **kw: covenant_plan_pot(**kw),
        "covenant_spend_policy_check": lambda ctx, **kw: covenant_spend_policy_check(**kw),
        "covenant_quine_info": lambda ctx: covenant_quine_info(),
        "covenant_kascov_verify": lambda ctx, **kw: _safe_tool("covenant_kascov_verify", **kw),
        "covenant_kascov_search": lambda ctx, **kw: _safe_tool("covenant_kascov_search", **kw),
        "covenant_kascov_address": lambda ctx, **kw: _safe_tool("covenant_kascov_address", **kw),
        "covenant_kascov_live": lambda ctx: _safe_tool("covenant_kascov_live"),
        "covenant_validate_pot": lambda ctx, **kw: _safe_tool("covenant_validate_pot", **kw),
        "covenant_estimate_fee": lambda ctx, **kw: _safe_tool("covenant_estimate_fee", **kw),
        "covenant_fee_schedule": lambda ctx: _safe_tool("covenant_fee_schedule"),
        "covenant_plan_with_fees": lambda ctx, **kw: _safe_tool("covenant_plan_with_fees", **kw),
        "kaspa_balance": lambda ctx: _kaspa_balance(),
        "kaspa_send": lambda ctx, **kw: _kaspa_send(**kw),
    }
    
    def _kaspa_balance(self) -> dict[str, Any]:
        """Check wallet balance via Kaspa REST API."""
        from vida.plugins.covenant.kaspa_rpc import get_balance
        # Try configured address, fall back to session
        addr = self.session.get("address", "")
        if not addr:
            return {"ok": False, "error": "no wallet address configured"}
        return get_balance(addr)
    
    def _kaspa_send(self, amount: float, destination: str) -> dict[str, Any]:
        """Send KAS via Kaspa REST API. Requires session with caps."""
        # Check session caps
        max_tx = float(self.session.get("max_kas_per_tx", 0))
        if max_tx > 0 and amount > max_tx:
            return {"ok": False, "error": f"amount {amount} exceeds session cap {max_tx}"}
        if not destination:
            return {"ok": False, "error": "destination address required"}
        # Note: actual broadcast needs wallet signing — this validates the policy
        return {"ok": True, "note": "send validated by policy; broadcast requires wallet signing", "amount": amount, "destination": destination}

    def __init__(self, session: Optional[dict] = None):
        self.session = session or {}
        self._plan: Optional[ExecutionPlan] = None
    
    def get_available_tools(self) -> list[dict[str, Any]]:
        """Return the OpenAI-compatible tool schema for LLM consumption."""
        from vida.agents.tool_schema import TOOL_SCHEMA
        return TOOL_SCHEMA
    
    def decompose_goal(self, goal: str, context: Optional[AgentState] = None) -> ExecutionPlan:
        """Decompose a natural language goal into executable steps.
        
        Uses K2.5 (via staking_optimizer.llm_call) to plan the execution.
        Falls back to rule-based decomposition if LLM is unavailable.
        """
        plan = ExecutionPlan(goal=goal, context=context or {})
        
        # Try LLM-powered decomposition
        try:
            from vida.agents.staking_optimizer import llm_call
            context_str = json.dumps(context or {}, indent=2)
            
            tools_list = [
                "vida_status(no params)",
                "vida_describe(no params)",
                "vida_live_gates(no params)",
                "vida_plan_pot(max_per_tx, max_per_day, destinations)",
                "vida_quine_info(no params)",
            ]
            
            system = "You are an agent planner. Produce ONLY valid JSON."
            prompt = f"""GOAL: {goal}

Available tools:
{chr(10).join('- ' + t for t in tools_list)}

Produce a JSON array of steps:
[{{"step":1, "action":"tool_name", "params":{{}}, "reason":"why"}}]

Return ONLY valid JSON. No other text."""

            response = llm_call(system, prompt, max_tokens=2000)
            
            # Parse JSON
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                steps = json.loads(response[start:end])
                plan.steps = [
                    Step(id=str(s["step"]), action=s["action"],
                         params=s.get("params", {}),
                         description=s.get("reason", ""))
                    for s in steps if s.get("action")
                ]
                if plan.steps:
                    return plan
        except Exception as e:
            pass  # Fall through to rule-based
        
        # ── Fallback: rule-based decomposition ──
        
        goal_lower = goal.lower()
        
        # ── Staking optimization ──
        if "stake" in goal_lower and "tao" in goal_lower:
            # Parse amount from goal
            amount = None
            for word in goal_lower.split():
                try:
                    amount = float(word)
                except ValueError:
                    continue
            
            plan.steps = [
                Step(id="1", action="covenant_status", params={},
                     description="Check wallet and covenant readiness"),
                Step(id="2", action="tao_stake_optimize", params={
                    "amount": amount or 100,
                    "risk_tolerance": "medium",
                }, description="Generate staking plan"),
                Step(id="3", action="covenant_plan_pot", params={
                    "max_kas_per_tx": amount / 10 if amount else 10,
                    "max_kas_per_day": amount or 100,
                }, description="Plan agent pot for staking"),
            ]
        
        # ── Covenant inspection ──
        elif "inspect" in goal_lower or "check" in goal_lower or "status" in goal_lower:
            plan.steps = [
                Step(id="1", action="covenant_status", params={},
                     description="Check covenant module status"),
                Step(id="2", action="covenant_describe", params={},
                     description="List available covenants"),
                Step(id="3", action="covenant_live_gates", params={},
                     description="Check deployment gates"),
            ]
        
        # ── Pot planning ──
        elif "pot" in goal_lower or "fund" in goal_lower or "plan" in goal_lower:
            per_tx = float(context.get("max_kas_per_tx", 0)) if context else 0
            per_day = float(context.get("max_kas_per_day", 0)) if context else 0
            plan.steps = [
                Step(id="1", action="covenant_status", params={},
                     description="Check readiness"),
                Step(id="2", action="covenant_plan_pot", params={
                    "max_kas_per_tx": per_tx or 1.0,
                    "max_kas_per_day": per_day or 5.0,
                }, description="Plan agent pot funding"),
            ]
        
        # ── Spend policy ──
        elif "spend" in goal_lower or "send" in goal_lower or "pay" in goal_lower:
            plan.steps = [
                Step(id="1", action="covenant_status", params={},
                     description="Check readiness"),
                Step(id="2", action="covenant_live_gates", params={},
                     description="Check deployment gates"),
                Step(id="3", action="covenant_spend_policy_check", params={
                    "amount": float(context.get("amount", 0)) if context else 0,
                    "destination": context.get("destination", ""),
                    "wallet_id": context.get("wallet_id", "default"),
                }, description="Validate spend policy"),
            ]
        
        # ── Default: inspect everything ──
        else:
            plan.steps = [
                Step(id="1", action="covenant_status", params={},
                     description="Check covenant module"),
                Step(id="2", action="covenant_describe", params={},
                     description="List available capabilities"),
                Step(id="3", action="covenant_quine_info", params={},
                     description="Get quine contract details"),
            ]
        
        return plan
    
    async def execute_step(self, step: Step) -> ToolResult:
        """Execute a single step by dispatching to the right tool."""
        impl = self._TOOL_IMPL.get(step.action)
        if not impl:
            return {"ok": False, "error": f"unknown tool: {step.action}"}
        
        step.started_at = time.time()
        step.status = "running"
        
        try:
            result = impl(self.session, **step.params)
            step.result = result
            step.status = "completed" if result.get("ok") else "failed"
            if not result.get("ok"):
                step.error = result.get("error", "tool returned not ok")
        except Exception as e:
            step.result = {"ok": False, "error": str(e)}
            step.status = "failed"
            step.error = str(e)
        
        step.completed_at = time.time()
        return step.result or {"ok": False, "error": "no result"}
    
    async def run(
        self,
        goal: str,
        context: Optional[AgentState] = None,
    ) -> dict[str, Any]:
        """Execute a goal: decompose → execute each step → return results."""
        self._plan = self.decompose_goal(goal, context)
        
        results = []
        for step in self._plan.steps:
            logger.info(f"Executing step {step.id}: {step.action}")
            result = await self.execute_step(step)
            results.append({
                "step": step.id,
                "action": step.action,
                "status": step.status,
                "result": result,
                "duration": (
                    (step.completed_at or 0) - (step.started_at or 0)
                ) if step.completed_at and step.started_at else None,
            })
            
            # Stop on failure unless step allows recovery
            if step.status == "failed" and not context.get("allow_recovery"):
                break
        
        all_ok = all(r["status"] == "completed" for r in results)
        
        # Build a summary
        summary_lines = []
        for r in results:
            icon = "✅" if r["status"] == "completed" else "❌"
            summary_lines.append(f"{icon} {r['action']}: {r['status']}")
        
        return {
            "ok": all_ok,
            "goal": goal,
            "steps": len(results),
            "completed": sum(1 for r in results if r["status"] == "completed"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "summary": "\n".join(summary_lines),
            "details": results,
        }


# ── Convenience functions ──

def get_tool_schema() -> list[dict[str, Any]]:
    """Get the OpenAI-compatible function calling schema."""
    from vida.agents.tool_schema import TOOL_SCHEMA
    return TOOL_SCHEMA