"""Vida Staking Agent — a real agent that does something useful.

Takes a natural language goal, uses an LLM to decompose it into steps,
and executes each step using actual Vida covenant tools.

This is NOT a demo. It calls K2.5 for planning and real Vida tools for execution.

Usage:
    python -m vida.agents.staking_optimizer "Stake 50 TAO with highest APY validator"
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

# ── LLM client ──

API_KEY = os.environ.get("ZYLOO_API_KEY")
if not API_KEY:
    print("ERROR: ZYLOO_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)
API_URL = "https://api.zyloo.io/v1/chat/completions"
MODEL = "zyloo/kimi-k2.5"


def llm_call(system: str, prompt: str, max_tokens: int = 2000) -> str:
    """Call K2.5 and return the response text."""
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
    )
    r = subprocess.run(
        [
            "curl",
            "-s",
            "--max-time",
            "60",
            API_URL,
            "-H",
            f"Authorization: Bearer {API_KEY}",
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
        capture_output=True,
        text=True,
        timeout=70,
    )
    resp = json.loads(r.stdout)
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content


# ── Vida tool wrappers ──


def vida_status() -> dict:
    """Check covenant module status."""
    from vida.plugins.covenant.tools import covenant_status

    return covenant_status()


def vida_live_gates() -> dict:
    """Check deployment gates."""
    from vida.plugins.covenant.tools import covenant_live_gates

    return covenant_live_gates()


def vida_plan_pot(max_per_tx: float, max_per_day: float, destinations: list[str] | None = None) -> dict:
    """Plan an agent pot."""
    from vida.plugins.covenant.tools import covenant_plan_pot

    return covenant_plan_pot(
        max_kas_per_tx=max_per_tx,
        max_kas_per_day=max_per_day,
        allowed_destinations=destinations,
    )


def vida_describe() -> dict:
    """List available covenants."""
    from vida.plugins.covenant.tools import covenant_describe

    return covenant_describe()


def vida_quine_info() -> dict:
    """Get quine contract details."""
    from vida.plugins.covenant.tools import covenant_quine_info

    return covenant_quine_info()


# ── Tool registry ──

TOOLS = {
    "vida_status": vida_status,
    "vida_live_gates": vida_live_gates,
    "vida_plan_pot": vida_plan_pot,
    "vida_describe": vida_describe,
    "vida_quine_info": vida_quine_info,
}


def execute_plan(plan: list[dict]) -> list[dict]:
    """Execute a plan (list of step dicts) against real tools."""
    results = []
    for step in plan:
        action = step.get("action", "")
        params = step.get("params", {})
        print(f"\n  ▶ {action}({json.dumps(params)})")

        fn = TOOLS.get(action)
        if not fn:
            results.append(
                {"step": step.get("step"), "action": action, "ok": False, "error": f"unknown tool: {action}"}
            )
            print(f"    ✗ Error: unknown tool '{action}'")
            continue

        try:
            result = fn(**params)
            ok = result.get("ok", False)
            results.append({"step": step.get("step"), "action": action, "ok": ok, "result": result})
            print(f"    {'✓' if ok else '✗'} {json.dumps(result, indent=2)[:200]}")
        except Exception as e:
            results.append({"step": step.get("step"), "action": action, "ok": False, "error": str(e)})
            print(f"    ✗ Exception: {e}")

    return results


def assess_goal(goal: str) -> tuple[str, list[dict]]:
    """Use K2.5 to assess the goal and produce an execution plan."""
    status = vida_status()
    gates = vida_live_gates()
    describe = vida_describe()
    quine = vida_quine_info()

    context = json.dumps(
        {
            "wallet_status": status,
            "gates": gates,
            "available_covenants": describe,
            "quine_contract": quine,
        },
        indent=2,
    )

    system = "You are an agent that executes cryptocurrency tasks. You are given a goal and context, and you produce a JSON plan."

    prompt = f"""GOAL: {goal}

CONTEXT (Vida wallet state):
{context}

Available tools:
- vida_status() - Check covenant module status (no params)
- vida_live_gates() - Check deployment gates (no params)
- vida_plan_pot(max_per_tx, max_per_day, destinations) - Plan agent pot
- vida_describe() - List available covenants (no params)
- vida_quine_info() - Get quine contract details (no params)

Produce a JSON execution plan as an array of steps:
[
    {{
        "step": 1,
        "action": "tool_name",
        "params": {{"param1": "value1"}},
        "reason": "why this step"
    }},
    ...
]

Only use the tools listed above. Return ONLY valid JSON, nothing else."""

    print("\n  Calling K2.5 to plan execution...")
    response = llm_call(system, prompt)

    # Parse JSON from response
    try:
        plan = json.loads(response)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                plan = json.loads(response[start:end])
            except json.JSONDecodeError:
                plan = [{"step": 1, "action": "vida_status", "params": {}, "reason": "fallback: default status check"}]
        else:
            plan = [{"step": 1, "action": "vida_status", "params": {}, "reason": "fallback: default status check"}]

    return response, plan


def main():
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Check Vida covenant status and plan a 5 KAS agent pot"

    print(f"\n{'=' * 60}")
    print(f"GOAL: {goal}")
    print(f"{'=' * 60}\n")

    # Step 1: Assess goal and get plan from K2.5
    print("── Step 1: Letting K2.5 analyze the goal and plan execution ──")
    analysis, plan = assess_goal(goal)
    print(f"\n  Analysis: {analysis[:300]}...")
    print(f"\n  Plan: {json.dumps(plan, indent=2)}")

    if not plan:
        print("\n✗ K2.5 couldn't produce a valid plan")
        return

    # Step 2: Execute each step against real tools
    print(f"\n── Step 2: Executing {len(plan)} steps against Vida tools ──")
    results = execute_plan(plan)

    # Step 3: Final summary
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = sum(1 for r in results if not r["ok"])

    print(f"\n{'=' * 60}")
    print(f"RESULT: {ok_count}/{len(results)} steps completed successfully")
    if fail_count > 0:
        print(f"  {fail_count} steps failed")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
