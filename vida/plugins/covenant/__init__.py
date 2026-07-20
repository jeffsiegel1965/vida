"""Vida covenant plugin — offline rails + gated live lab/WASM."""

from .agent_pot import plan_agent_pot, validate_agent_pot_plan
from .agent_pot_script import build_agent_pot_script_template, verify_policy_hash
from .config import CovenantConfig, load_covenant_config
from .escrow import vida_escrow_create, vida_escrow_status, vida_escrow_list, EscrowRecord, EscrowStore
from .lab_client import live_gates_ok, run_lab_demo
from .plugin import CovenantPlugin, register_covenant_plugin
from .pot_spend import check_spend_allowed, check_spend_kas, load_pot_record, save_pot_record, check_subscription_status
from .proofs import tn10_microproof
from .scripts import (
    compile_placeholder_timelock_meta,
    describe_compute_budget_rules,
    offline_validate_budget,
)
from .tools import (
    covenant_describe,
    covenant_live_gates,
    covenant_plan_pot,
    covenant_quine_info,
    covenant_spend_policy_check,
    covenant_status,
    covenant_plan_with_fees,
    covenant_estimate_fee,
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
    "load_pot_record",
    "save_pot_record",
    "check_subscription_status",
    "covenant_describe",
    "covenant_live_gates",
    "covenant_plan_pot",
    "covenant_quine_info",
    "covenant_spend_policy_check",
    "covenant_status",
    "covenant_plan_with_fees",
    "covenant_estimate_fee",
    "vida_escrow_create",
    "vida_escrow_status",
    "vida_escrow_list",
    "EscrowRecord",
    "EscrowStore",
]