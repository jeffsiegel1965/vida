"""Covenant pattern library — deploy and interact with SilverScript covenant patterns.

Wraps the SDK integration for common covenant patterns used by Vida agents:

- DeadMansSwitch: Agent inactivity timeout → fallback recipient
- StreamingPayment: Continuous payment streaming per period
- Vesting: Scheduled token release with cliff and admin revocation
- QuineAgentPot: Self-replicating agent spending pot

Each pattern has deploy, status, and action functions.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Paths to compiled SilverScript JSON artifacts ──
CONTRACTS_DIR = Path(__file__).resolve().parent / "silverscript" / "contracts"

# Known compiled contract artifacts (produced by silverc compiler)
# Each maps pattern name -> {json_path, contract_name}
COMPILED_ARTIFACTS: dict[str, dict[str, Any]] = {
    "quine_agent_pot": {
        "json_path": Path(__file__).resolve().parent / "silverscript" / "quine_agent_pot.json",
        "contract_name": "QuineAgentPot",
    },
    "dead_mans_switch": {
        "json_path": CONTRACTS_DIR / "DeadMansSwitch.json",
        "contract_name": "DeadMansSwitch",
    },
    "streaming_payment": {
        "json_path": CONTRACTS_DIR / "StreamingPayment.json",
        "contract_name": "StreamingPayment",
    },
    "vesting": {
        "json_path": CONTRACTS_DIR / "Vesting.json",
        "contract_name": "Vesting",
    },
    "ownable": {
        "json_path": CONTRACTS_DIR / "Ownable.json",
        "contract_name": "Ownable",
    },
    "timelock": {
        "json_path": CONTRACTS_DIR / "TimeLock.json",
        "contract_name": "TimeLock",
    },
    "atomic_swap_htlc": {
        "json_path": CONTRACTS_DIR / "AtomicSwapHTLC.json",
        "contract_name": "AtomicSwapHTLC",
    },
    "social_recovery": {
        "json_path": CONTRACTS_DIR / "SocialRecovery.json",
        "contract_name": "SocialRecovery",
    },
}


@dataclass
class PatternResult:
    """Standard result from any covenant pattern operation."""
    ok: bool
    txid: str = ""
    pattern: str = ""
    action: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def load_compiled_program(pattern_name: str) -> tuple[str, str]:
    """Load a compiled SilverScript program from its JSON artifact.

    Returns:
        (program_hex, contract_name) tuple.

    Raises:
        FileNotFoundError: If the compiled artifact doesn't exist.
    """
    artifact = COMPILED_ARTIFACTS.get(pattern_name)
    if not artifact:
        raise FileNotFoundError(f"Unknown pattern: {pattern_name}")

    path = artifact["json_path"]
    if not path.exists():
        # Try to find the .sil source and compile it
        raise FileNotFoundError(
            f"No compiled artifact for {pattern_name}. "
            f"Expected at {path}. "
            f"Compile the source at {path.with_suffix('.sil')} with silverc first."
        )

    with open(path) as f:
        data = json.load(f)

    script_bytes = bytes(data["script"])
    return script_bytes.hex(), artifact["contract_name"]


# ── Dead Man's Switch ──


def create_dms_config(
    *,
    owner_pubkey: str,
    fallback_pubkey: str,
    timeout_blocks: int = 100_000,  # ~7 days at 1 block/sec
    initial_age: int = 0,
) -> dict[str, Any]:
    """Create constructor args for DeadMansSwitch deployment.

    Args:
        owner_pubkey: 32-byte hex x-only public key of the agent.
        fallback_pubkey: 32-byte hex x-only public key of the fallback recipient.
        timeout_blocks: Number of blocks after which fallback can claim.
        initial_age: Starting age (0 for fresh deploy).

    Returns:
        Constructor args dict matching the SilverScript contract parameters.
    """
    return {
        "init_owner": owner_pubkey,
        "init_fallback": fallback_pubkey,
        "init_timeout_age": timeout_blocks,
        "init_last_ping_age": initial_age,
    }


async def deploy_dead_mans_switch(
    private_key_hex: str,
    config: dict[str, Any],
    value_sompi: int = 100_000_000,
    network: str = "testnet-10",
) -> PatternResult:
    """Deploy a DeadMansSwitch covenant.

    Args:
        private_key_hex: Deployer's private key.
        config: Constructor args from create_dms_config().
        value_sompi: Amount to lock in the covenant.
        network: Network to deploy to.
    """
    from .sdk_integration import deploy_covenant

    try:
        program_hex, _ = load_compiled_program("dead_mans_switch")
        result = await deploy_covenant(
            program_hex=program_hex,
            private_key_hex=private_key_hex,
            value_sompi=value_sompi,
            network=network,
        )
        if result.ok:
            return PatternResult(
                ok=True,
                txid=result.txid,
                pattern="dead_mans_switch",
                action="deploy",
                data={
                    "covenant_id": result.covenant_id,
                    "address": result.address,
                    "value_sompi": result.value_sompi,
                    "config": config,
                },
            )
        return PatternResult(ok=False, pattern="dead_mans_switch", action="deploy", error=result.error)
    except Exception as e:
        return PatternResult(ok=False, pattern="dead_mans_switch", action="deploy", error=str(e))


# ── Streaming Payment ──


def create_stream_config(
    *,
    sender_pubkey: str,
    recipient_pubkey: str,
    rate_per_claim_sompi: int,
    total_allowance_sompi: int,
    period_blocks: int = 86400,  # ~1 day
    start_time: int | None = None,
) -> dict[str, Any]:
    """Create constructor args for StreamingPayment deployment.

    Args:
        sender_pubkey: 32-byte hex x-only public key of the sender.
        recipient_pubkey: 32-byte hex x-only public key of the recipient.
        rate_per_claim_sompi: Amount released per claim.
        total_allowance_sompi: Total KAS to stream.
        period_blocks: Blocks between releases.
        start_time: First release time (default: now).

    Returns:
        Constructor args dict.
    """
    now = start_time or int(time.time())
    return {
        "init_sender": sender_pubkey,
        "init_recipient": recipient_pubkey,
        "init_rate_per_claim": rate_per_claim_sompi,
        "init_total_allowance": total_allowance_sompi,
        "init_remaining_allowance": total_allowance_sompi,
        "init_period": period_blocks,
        "init_next_release_time": now + period_blocks,
    }


async def deploy_streaming_payment(
    private_key_hex: str,
    config: dict[str, Any],
    value_sompi: int = 100_000_000,
    network: str = "testnet-10",
) -> PatternResult:
    """Deploy a StreamingPayment covenant."""
    from .sdk_integration import deploy_covenant

    try:
        program_hex, _ = load_compiled_program("streaming_payment")
        result = await deploy_covenant(
            program_hex=program_hex,
            private_key_hex=private_key_hex,
            value_sompi=value_sompi,
            network=network,
        )
        if result.ok:
            return PatternResult(
                ok=True,
                txid=result.txid,
                pattern="streaming_payment",
                action="deploy",
                data={
                    "covenant_id": result.covenant_id,
                    "address": result.address,
                    "value_sompi": result.value_sompi,
                    "config": config,
                },
            )
        return PatternResult(ok=False, pattern="streaming_payment", action="deploy", error=result.error)
    except Exception as e:
        return PatternResult(ok=False, pattern="streaming_payment", action="deploy", error=str(e))


# ── Vesting ──


def create_vesting_config(
    *,
    beneficiary_pubkey: str,
    admin_pubkey: str,
    total_allocation_sompi: int,
    cliff_time: int | None = None,
    period_blocks: int = 86400,  # ~1 day
    release_per_period_sompi: int,
    revocable: bool = True,
) -> dict[str, Any]:
    """Create constructor args for Vesting deployment.

    Args:
        beneficiary_pubkey: 32-byte hex x-only public key of the beneficiary.
        admin_pubkey: 32-byte hex x-only public key of the admin.
        total_allocation_sompi: Total KAS to vest.
        cliff_time: First release time (default: now + 1 period).
        period_blocks: Blocks between releases.
        release_per_period_sompi: Amount per period.
        revocable: Whether admin can revoke unvested funds.

    Returns:
        Constructor args dict.
    """
    now = cliff_time or int(time.time()) + period_blocks
    return {
        "init_beneficiary": beneficiary_pubkey,
        "init_admin": admin_pubkey,
        "init_total_allocation": total_allocation_sompi,
        "init_claimed_amount": 0,
        "init_cliff_time": now,
        "init_period": period_blocks,
        "init_release_per_period": release_per_period_sompi,
        "init_revocable": revocable,
    }


async def deploy_vesting(
    private_key_hex: str,
    config: dict[str, Any],
    value_sompi: int = 100_000_000,
    network: str = "testnet-10",
) -> PatternResult:
    """Deploy a Vesting covenant."""
    from .sdk_integration import deploy_covenant

    try:
        program_hex, _ = load_compiled_program("vesting")
        result = await deploy_covenant(
            program_hex=program_hex,
            private_key_hex=private_key_hex,
            value_sompi=value_sompi,
            network=network,
        )
        if result.ok:
            return PatternResult(
                ok=True,
                txid=result.txid,
                pattern="vesting",
                action="deploy",
                data={
                    "covenant_id": result.covenant_id,
                    "address": result.address,
                    "value_sompi": result.value_sompi,
                    "config": config,
                },
            )
        return PatternResult(ok=False, pattern="vesting", action="deploy", error=result.error)
    except Exception as e:
        return PatternResult(ok=False, pattern="vesting", action="deploy", error=str(e))


# ── Status helper ──


async def covenant_status(
    covenant_id: str,
    network: str = "testnet-10",
) -> dict[str, Any]:
    """Check covenant balance and status via kascov explorer."""
    from .sdk_integration import covenant_balance

    return await covenant_balance(covenant_id=covenant_id, network=network)


# ── Sync wrappers ──


def deploy_dms(
    private_key_hex: str,
    config: dict[str, Any],
    value_sompi: int = 100_000_000,
    network: str = "testnet-10",
) -> PatternResult:
    """Sync wrapper for deploy_dead_mans_switch."""
    return asyncio.run(deploy_dead_mans_switch(
        private_key_hex=private_key_hex, config=config,
        value_sompi=value_sompi, network=network,
    ))


def deploy_stream(
    private_key_hex: str,
    config: dict[str, Any],
    value_sompi: int = 100_000_000,
    network: str = "testnet-10",
) -> PatternResult:
    """Sync wrapper for deploy_streaming_payment."""
    return asyncio.run(deploy_streaming_payment(
        private_key_hex=private_key_hex, config=config,
        value_sompi=value_sompi, network=network,
    ))


def deploy_vest(
    private_key_hex: str,
    config: dict[str, Any],
    value_sompi: int = 100_000_000,
    network: str = "testnet-10",
) -> PatternResult:
    """Sync wrapper for deploy_vesting."""
    return asyncio.run(deploy_vesting(
        private_key_hex=private_key_hex, config=config,
        value_sompi=value_sompi, network=network,
    ))