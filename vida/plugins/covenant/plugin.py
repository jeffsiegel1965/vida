"""Covenant plugin — offline rails + gated live lab/WASM paths.

Live deploy/fund require VIDA_COVENANT_LIVE=1 + key + tooling.
In-process never claims success without subprocess/tool result.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ..base import VidaPluginContext
from ..policy import PolicyRequest
from .agent_pot import plan_agent_pot, validate_agent_pot_plan
from .agent_pot_script import (
    STRATEGY_MVP,
    build_agent_pot_script_template,
    verify_policy_hash,
)
from .config import CovenantConfig, load_covenant_config
from .lab_client import (
    can_fund_agent_pot,
    can_run_lab_demo,
    can_spend_agent_pot,
    live_gates_ok,
    run_lab_demo,
)
from .lab_client import (
    fund_agent_pot as lab_fund_agent_pot,
)
from .lab_client import (
    spend_agent_pot as lab_spend_agent_pot,
)
from .pot_spend import (
    check_spend_kas,
    load_pot_record,
    save_pot_record,
)
from .proofs import proof_doc_exists, tn10_microproof
from .scripts import (
    compile_placeholder_timelock_meta,
    describe_compute_budget_rules,
    offline_validate_budget,
)


class CovenantPlugin:
    """Offline helpers + optional gated live TN10 tooling."""

    name = "covenant"
    chain = "kaspa"
    capabilities = [
        "status",
        "describe",
        "offline_budget_validate",
        "offline_timelock_meta",
        "check_action",
        "plan_agent_pot",
        "agent_pot_script_template",
        "tn10_proof_status",
        "live_gates",
        # live methods exist but gated
        "deploy_lab_demo",
        "fund_agent_pot",
        "check_pot_spend",
        "spend_agent_pot",
    ]

    def __init__(self, config: Optional[CovenantConfig] = None) -> None:
        self.config = config or load_covenant_config()

    def describe(self) -> dict[str, Any]:
        proof = tn10_microproof()
        return {
            "name": self.name,
            "chain": self.chain,
            "phase": "tn10_lab_proven_plugin_gated_live",
            "live_enabled": self.config.live_enabled,
            "network": self.config.network,
            "capabilities": list(self.capabilities),
            "docs": "docs/plugins/covenant/README.md",
            "blocker": "docs/plugins/COVENANT_BLOCKER_STATUS.md",
            "design": "docs/plugins/covenant/AGENT_HARD_CAP_DESIGN.md",
            "proof_doc": proof["doc"],
            "tn10_covenant_id": proof["covenant_id"],
            "issue": "https://github.com/kaspanet/rusty-kaspa/issues/1073",
            "fix_pr": "https://github.com/kaspanet/rusty-kaspa/pull/1074",
            "notes": (
                "TN10 lifecycle proven (kascov-lab). "
                "Gated live: deploy()→lab demo; fund_agent_pot()→WASM #1074. "
                "Agent pot max_tx/dest template offline; chain enforces lineage today."
            ),
        }

    def status(self, ctx: VidaPluginContext) -> dict[str, Any]:
        proof = tn10_microproof()
        gates = live_gates_ok()
        return {
            "ok": True,
            "plugin": self.name,
            "chain": self.chain,
            "wallet_id": ctx.wallet_id,
            "network": self.config.network,
            "mode": ctx.mode,
            "live_deploy_available": can_run_lab_demo() and self.config.live_enabled,
            "live_fund_pot_available": can_fund_agent_pot() and self.config.live_enabled,
            "live_spend_available": can_spend_agent_pot() and self.config.live_enabled,
            "live_enabled_flag": self.config.live_enabled,
            "live_gates": gates,
            "soft_policy_available": True,
            "soft_policy_note": "Use Kaspa agent sessions for caps today",
            "tn10_lab_proven": True,
            "tn10_proof_doc_present": proof_doc_exists(),
            "tn10_covenant_id": proof["covenant_id"],
            "tn10_genesis_txid": proof["txs"]["genesis"],
            "budget_rules": describe_compute_budget_rules(),
            "default_compute_budget": self.config.default_compute_budget,
            "phase": "tn10_lab_proven_plugin_gated_live",
            "capabilities": list(self.capabilities),
            "blocker": "docs/plugins/COVENANT_BLOCKER_STATUS.md",
            "lab_wrapper": "scripts/covenant_tn10_lab.sh",
            "fund_helper": "scripts/covenant_fund_agent_pot.js",
        }

    def live_gates(self) -> dict[str, Any]:
        g = live_gates_ok()
        return {
            "ok": True,
            "gates": g,
            "can_lab_demo": can_run_lab_demo(),
            "can_fund_agent_pot": can_fund_agent_pot(),
            "config_live_enabled": self.config.live_enabled,
        }

    def check_action(
        self, ctx: VidaPluginContext, action: str, amount: float = 0.0
    ) -> dict[str, Any]:
        decision = ctx.decide(
            PolicyRequest(chain=self.chain, action=action, amount=amount)
        )
        return {
            "ok": decision.allowed,
            "allowed": decision.allowed,
            "needs_approval": decision.needs_approval,
            "reason": decision.reason,
            "action": action,
            "amount": amount,
            "enforcement": "soft_policy",
            "on_chain_hard_cap": False,
        }

    def validate_budget(self, budget: int, signing_inputs: int = 1) -> dict[str, Any]:
        return offline_validate_budget(budget, signing_inputs=signing_inputs)

    def sketch_timelock(self, lock_blocks: int) -> dict[str, Any]:
        return compile_placeholder_timelock_meta(lock_blocks=lock_blocks)

    def plan_agent_pot(
        self,
        *,
        max_kas_per_tx: float,
        max_kas_per_day: float,
        allowed_destinations: Optional[Sequence[str]] = None,
        session_hours: float = 8.0,
        fee_buffer_kas: float = 0.05,
    ) -> dict[str, Any]:
        plan = plan_agent_pot(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations,
            session_hours=session_hours,
            fee_buffer_kas=fee_buffer_kas,
        )
        if plan.get("ok"):
            plan["validation"] = validate_agent_pot_plan(plan)
            plan["script_template"] = build_agent_pot_script_template(
                max_kas_per_tx=max_kas_per_tx,
                max_kas_per_day=max_kas_per_day,
                allowed_destinations=allowed_destinations or [],
                strategy=STRATEGY_MVP,
            )
        return plan

    def agent_pot_script_template(
        self,
        *,
        max_kas_per_tx: float,
        max_kas_per_day: float,
        allowed_destinations: Optional[Sequence[str]] = None,
        owner_address: Optional[str] = None,
        strategy: str = STRATEGY_MVP,
    ) -> dict[str, Any]:
        t = build_agent_pot_script_template(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations or [],
            owner_address=owner_address,
            strategy=strategy,
        )
        if t.get("ok"):
            t["hash_ok"] = verify_policy_hash(t)
        return t

    def tn10_proof_status(self) -> dict[str, Any]:
        p = tn10_microproof()
        return {
            "ok": True,
            "proven": True,
            "network": p["network"],
            "covenant_id": p["covenant_id"],
            "txs": p["txs"],
            "doc": p["doc"],
            "doc_present": proof_doc_exists(),
            "claim": p["claim"],
            "in_process_live": can_run_lab_demo() or can_fund_agent_pot(),
        }

    def deploy(
        self,
        *args: Any,
        transitions: int = 1,
        force_live: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Gated live path: kascov-lab demo (genesis→transition→burn).

        Requires config.live_enabled or force_live, plus VIDA_COVENANT_LIVE=1.
        """
        if not (self.config.live_enabled or force_live):
            proof = tn10_microproof()
            return {
                "ok": False,
                "error": (
                    "live deploy disabled; set CovenantConfig.live_enabled "
                    "and VIDA_COVENANT_LIVE=1, or pass force_live=True"
                ),
                "live_deploy_available": can_run_lab_demo(),
                "tn10_lab_proven": True,
                "tn10_covenant_id": proof["covenant_id"],
                "proof": proof["doc"],
                "gates": live_gates_ok(),
            }
        result = run_lab_demo(transitions=transitions)
        result["method"] = "kascov_lab_demo"
        return result

    def fund_agent_pot(
        self,
        *,
        max_kas_per_tx: float,
        max_kas_per_day: float,
        allowed_destinations: Optional[Sequence[str]] = None,
        force_live: bool = False,
        single_output: bool = True,
        wallet_id: str = "default",
        save_record: bool = True,
    ) -> dict[str, Any]:
        """
        Plan pot policy template, then optionally fund covenant-bound pot via WASM.
        """
        template = build_agent_pot_script_template(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations or [],
            strategy=STRATEGY_MVP,
        )
        if not template.get("ok"):
            return template

        if not (self.config.live_enabled or force_live):
            return {
                "ok": False,
                "error": "live fund disabled; enable live_enabled + VIDA_COVENANT_LIVE=1",
                "template": template,
                "gates": live_gates_ok(),
            }

        pot_sompi = int(template["pot_fund_sompi"])
        max_tx_sompi = int(template["policy"]["max_tx_sompi"])
        # single_output may fund more than template pot; relax max_tx vs pot for lab call
        lab_pot = pot_sompi
        if single_output and max_tx_sompi > pot_sompi:
            return {"ok": False, "error": "max_tx exceeds planned pot", "template": template}

        funded = lab_fund_agent_pot(
            pot_sompi=max(lab_pot, max_tx_sompi + 1),
            max_tx_sompi=max_tx_sompi,
            allowed_destinations=allowed_destinations or [],
        )
        funded["template"] = template
        funded["single_output"] = single_output
        if funded.get("ok"):
            funded["hard_rules_attached"] = {
                **(funded.get("hard_rules_attached") or {}),
                "policy_hash": template["policy_hash"],
                "max_tx_sompi": max_tx_sompi,
                "allowed_destinations": list(allowed_destinations or []),
            }
            if save_record:
                funded["pot_record"] = save_pot_record(wallet_id, funded)
        return funded

    def check_pot_spend(
        self,
        *,
        amount_kas: float,
        destination: str,
        policy: Optional[dict[str, Any]] = None,
        wallet_id: str = "default",
        owner_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """Software max_tx + dest check (no broadcast)."""
        pol = policy
        if pol is None:
            loaded = load_pot_record(wallet_id)
            if not loaded.get("ok"):
                return {
                    "ok": False,
                    "error": loaded.get("error") or "no policy",
                    "hint": "pass policy= or fund_agent_pot first",
                }
            pol = loaded["record"].get("policy") or {}
        return check_spend_kas(
            policy=pol,
            amount_kas=amount_kas,
            destination=destination,
            owner_address=owner_address,
        )

    def spend(
        self,
        *args: Any,
        amount_kas: Optional[float] = None,
        destination: Optional[str] = None,
        wallet_id: str = "default",
        force_live: bool = False,
        policy: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Gated pot spend: soft policy check then WASM broadcast.

        Requires amount_kas + destination. Loads pot policy from record if needed.
        """
        if amount_kas is None or not destination:
            proof = tn10_microproof()
            return {
                "ok": False,
                "error": "spend requires amount_kas and destination",
                "live_spend_available": can_spend_agent_pot(),
                "tn10_lab_proven": True,
                "tn10_covenant_id": proof["covenant_id"],
                "proof": proof["doc"],
            }

        pol = policy
        covenant_id = None
        if pol is None:
            loaded = load_pot_record(wallet_id)
            if loaded.get("ok"):
                rec = loaded["record"]
                pol = rec.get("policy") or {}
                covenant_id = rec.get("covenant_id")
            else:
                pol = {}

        check = check_spend_kas(
            policy=pol or {"max_tx_sompi": 0, "allowed_destinations": [], "require_dest_allowlist": False},
            amount_kas=float(amount_kas),
            destination=str(destination),
        )
        if not check.get("ok"):
            return {**check, "broadcast": False}

        if not (self.config.live_enabled or force_live):
            return {
                "ok": False,
                "error": "live spend disabled; enable live_enabled + VIDA_COVENANT_LIVE=1",
                "policy_check": check,
                "gates": live_gates_ok(),
                "broadcast": False,
            }

        amount_sompi = int(check["amount_sompi"])
        max_tx = int((pol or {}).get("max_tx_sompi") or 0)
        dests = list((pol or {}).get("allowed_destinations") or [])
        result = lab_spend_agent_pot(
            amount_sompi=amount_sompi,
            destination=str(destination),
            max_tx_sompi=max_tx,
            allowed_destinations=dests,
            covenant_id=covenant_id,
        )
        result["policy_check"] = check
        result["method"] = "wasm_agent_pot_spend"
        return result

    def fund_agent_pot_and_record(
        self,
        *,
        max_kas_per_tx: float,
        max_kas_per_day: float,
        allowed_destinations: Optional[Sequence[str]] = None,
        wallet_id: str = "default",
        force_live: bool = False,
    ) -> dict[str, Any]:
        """fund_agent_pot + save pot record for later spend checks."""
        funded = self.fund_agent_pot(
            max_kas_per_tx=max_kas_per_tx,
            max_kas_per_day=max_kas_per_day,
            allowed_destinations=allowed_destinations,
            force_live=force_live,
        )
        if funded.get("ok"):
            saved = save_pot_record(wallet_id, funded)
            funded["pot_record"] = saved
        return funded


def register_covenant_plugin(
    registry: Any, config: Optional[CovenantConfig] = None
) -> CovenantPlugin:
    plugin = CovenantPlugin(config=config)
    registry.register(plugin)
    return plugin
