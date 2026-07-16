"""Vida covenant plugin — offline rails + gated live lab/WASM."""

from .agent_pot import plan_agent_pot, validate_agent_pot_plan
from .agent_pot_script import build_agent_pot_script_template, verify_policy_hash
from .config import CovenantConfig, load_covenant_config
from .lab_client import live_gates_ok, run_lab_demo
from .plugin import CovenantPlugin, register_covenant_plugin
from .pot_spend import check_spend_allowed, check_spend_kas, load_pot_record, save_pot_record, check_subscription_status
from .proofs import tn10_microproof
from .scripts import (
    compile_placeholder_timelock_meta,
    describe_compute_budget_rules,
    offline_validate_budget,
)

__all__ = [
    "CovenantConfig",
    "load_covenant_config",
    "CovenantPlugin",
    "register_covenant_plugin",
    "compile_placeholder_timelock_meta",
    "describe_compute_budget_rules",
    "offline_validate_budget",
    "plan_agent_pot",
    "validate_agent_pot_plan",
    "build_agent_pot_script_template",
    "verify_policy_hash",
    "tn10_microproof",
    "live_gates_ok",
    "run_lab_demo",
    "check_spend_allowed",
    "check_spend_kas",
]
