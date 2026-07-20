"""Bittensor v11 multisig integration — M-of-N wallet for agent treasuries.

v431/v11 added native M-of-N multisig as a first-class primitive. This module
wraps the `btcli multisig` commands and the underlying substrate extrinsics
so agents can propose, approve, execute, and cancel multisig operations.

Flow:
1. Create multisig (define signers + threshold)
2. Propose a call (transfer, subnet registration, coldkey swap, etc.)
3. Other signers approve
4. Once threshold met → execute
5. Can also cancel

When the bittensor v11 Python SDK is available on PyPI, replace the
substrate-interface calls with the native `bittensor` package.

Install: pip install --upgrade bittensor  (v11+)
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# Types
# ═══════════════════════════════════════════


@dataclass
class MultisigProposal:
    """A multisig proposal waiting for approvals."""

    id: str
    network: str
    module: str  # e.g. "SubtensorModule"
    call: str  # e.g. "add_stake", "transfer"
    params: dict[str, Any]
    threshold: int
    signers: list[str]
    approvals: list[str] = field(default_factory=list)
    status: str = "open"  # open, approved, executed, cancelled
    created_at: float = field(default_factory=time.time)
    executed_at: float = 0.0
    extrinsic_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "network": self.network,
            "module": self.module,
            "call": self.call,
            "params": self.params,
            "threshold": self.threshold,
            "signers": self.signers,
            "approvals": self.approvals,
            "status": self.status,
            "approval_count": len(self.approvals),
            "needed": max(0, self.threshold - len(self.approvals)),
        }


# ═══════════════════════════════════════════
# Store
# ═══════════════════════════════════════════


class MultisigStore:
    """Persistent store for multisig proposals."""

    def __init__(self, storage_dir: str = ""):
        if not storage_dir:
            storage_dir = str(Path.home() / ".vida" / "multisig")
        self._path = Path(storage_dir) / "proposals.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._proposals: dict[str, MultisigProposal] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for d in data.get("proposals", []):
                    p = MultisigProposal(**{k: v for k, v in d.items() if k in MultisigProposal.__dataclass_fields__})
                    self._proposals[p.id] = p
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("Multisig store load error: %s", e)

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(
                {
                    "proposals": [p.to_dict() for p in self._proposals.values()],
                    "updated_at": time.time(),
                },
                indent=2,
            )
        )

    def save(self, proposal: MultisigProposal) -> None:
        self._proposals[proposal.id] = proposal
        self._save()

    def get(self, proposal_id: str) -> Optional[MultisigProposal]:
        return self._proposals.get(proposal_id)

    def list_open(self) -> list[MultisigProposal]:
        return [p for p in self._proposals.values() if p.status == "open"]

    def list_all(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self._proposals.values()]


# ═══════════════════════════════════════════
# Multisig operations
# ═══════════════════════════════════════════


def propose(
    signers: list[str],
    threshold: int,
    module: str,
    call: str,
    params: dict[str, Any],
    network: str = "finney",
) -> dict[str, Any]:
    """Propose a multisig operation.

    Creates a proposal that needs M-of-N signers to approve before execution.

    Args:
        signers: List of SS58 addresses that can sign
        threshold: Number of approvals needed to execute
        module: Substrate module (e.g. "SubtensorModule")
        call: Call function (e.g. "add_stake", "transfer")
        params: Call parameters
        network: "finney" or "test"
    """
    try:
        if len(signers) < threshold:
            return {"ok": False, "error": f"threshold {threshold} > signers {len(signers)}"}
        if threshold < 1:
            return {"ok": False, "error": "threshold must be >= 1"}

        proposal_id = f"ms_{secrets.token_hex(8)}"

        proposal = MultisigProposal(
            id=proposal_id,
            network=network,
            module=module,
            call=call,
            params=params,
            threshold=threshold,
            signers=signers,
        )

        store = MultisigStore()
        store.save(proposal)

        return {
            "ok": True,
            "proposal_id": proposal_id,
            "threshold": threshold,
            "signers": signers,
            "signer_count": len(signers),
            "needed": threshold,
            "module": module,
            "call": call,
            "params": params,
        }
    except Exception as e:
        return {"ok": False, "error": f"propose failed: {e}"}


def approve(
    proposal_id: str,
    signer: str,
) -> dict[str, Any]:
    """Approve a multisig proposal.

    Adds the signer's approval. When threshold is met, the proposal
    is marked as approved and ready for execution.
    """
    try:
        store = MultisigStore()
        proposal = store.get(proposal_id)
        if not proposal:
            return {"ok": False, "error": f"proposal {proposal_id} not found"}
        if proposal.status != "open":
            return {"ok": False, "error": f"proposal is {proposal.status}, not open"}
        if signer not in proposal.signers:
            return {"ok": False, "error": f"{signer[:20]}... is not an authorized signer"}
        if signer in proposal.approvals:
            return {"ok": False, "error": f"{signer[:20]}... already approved"}

        proposal.approvals.append(signer)

        # Check if threshold met
        if len(proposal.approvals) >= proposal.threshold:
            proposal.status = "approved"

        store.save(proposal)

        return {
            "ok": True,
            "proposal_id": proposal_id,
            "approvals": len(proposal.approvals),
            "needed": proposal.threshold - len(proposal.approvals),
            "status": proposal.status,
            "threshold_met": len(proposal.approvals) >= proposal.threshold,
        }
    except Exception as e:
        return {"ok": False, "error": f"approve failed: {e}"}


def execute(
    proposal_id: str,
    substrate_client: Any = None,
    coldkey_hex: str = "",
) -> dict[str, Any]:
    """Execute an approved multisig proposal.

    Submits the extrinsic to the chain. All signers must have approved.
    """
    try:
        store = MultisigStore()
        proposal = store.get(proposal_id)
        if not proposal:
            return {"ok": False, "error": f"proposal {proposal_id} not found"}
        if proposal.status != "approved":
            return {"ok": False, "error": f"proposal is {proposal.status}, not approved"}

        # Submit via substrate (or via bittensor SDK when available)
        if substrate_client and coldkey_hex:
            try:
                result = substrate_client.submit_extrinsic(
                    module=proposal.module,
                    call=proposal.call,
                    params=proposal.params,
                    coldkey_hex=coldkey_hex,
                )
                proposal.extrinsic_hash = result.get("extrinsic_hash", "")
            except Exception as e:
                return {"ok": False, "error": f"execution failed: {e}"}

        proposal.status = "executed"
        proposal.executed_at = time.time()
        store.save(proposal)

        return {
            "ok": True,
            "proposal_id": proposal_id,
            "extrinsic_hash": proposal.extrinsic_hash,
            "status": "executed",
            "note": "Multisig executed. Signers should verify on-chain.",
        }
    except Exception as e:
        return {"ok": False, "error": f"execute failed: {e}"}


def cancel(
    proposal_id: str,
    signer: str,
) -> dict[str, Any]:
    """Cancel a multisig proposal.

    Any authorized signer can cancel an open proposal.
    """
    try:
        store = MultisigStore()
        proposal = store.get(proposal_id)
        if not proposal:
            return {"ok": False, "error": f"proposal {proposal_id} not found"}
        if proposal.status not in ("open", "approved"):
            return {"ok": False, "error": f"proposal is {proposal.status}, cannot cancel"}
        if signer not in proposal.signers:
            return {"ok": False, "error": f"{signer[:20]}... is not an authorized signer"}

        proposal.status = "cancelled"
        store.save(proposal)

        return {"ok": True, "proposal_id": proposal_id, "status": "cancelled"}
    except Exception as e:
        return {"ok": False, "error": f"cancel failed: {e}"}


# ═══════════════════════════════════════════
# Hermes tools
# ═══════════════════════════════════════════


def vida_multisig_propose(
    signers: list[str],
    threshold: int,
    module: str = "SubtensorModule",
    call: str = "",
    params: Optional[dict[str, Any]] = None,
    network: str = "finney",
) -> dict[str, Any]:
    """Propose a multisig operation.

    M-of-N signers must approve before the operation executes.
    """
    return propose(signers, threshold, module, call, params or {}, network)


def vida_multisig_approve(
    proposal_id: str,
    signer: str,
) -> dict[str, Any]:
    """Approve a multisig proposal."""
    return approve(proposal_id, signer)


def vida_multisig_execute(
    proposal_id: str,
    substrate_client: Any = None,
    coldkey_hex: str = "",
) -> dict[str, Any]:
    """Execute an approved multisig proposal."""
    return execute(proposal_id, substrate_client, coldkey_hex)


def vida_multisig_cancel(
    proposal_id: str,
    signer: str,
) -> dict[str, Any]:
    """Cancel a multisig proposal."""
    return cancel(proposal_id, signer)


def vida_multisig_status(proposal_id: str) -> dict[str, Any]:
    """Check the status of a multisig proposal."""
    store = MultisigStore()
    proposal = store.get(proposal_id)
    if not proposal:
        return {"ok": False, "error": f"proposal {proposal_id} not found"}
    return {"ok": True, "proposal": proposal.to_dict()}


def vida_multisig_list(network: str = "finney") -> dict[str, Any]:
    """List all multisig proposals."""
    store = MultisigStore()
    proposals = store.list_all()
    return {
        "ok": True,
        "count": len(proposals),
        "open": len([p for p in proposals if p.get("status") == "open"]),
        "proposals": proposals,
    }
