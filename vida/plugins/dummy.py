"""Dummy plugin for Phase 0 — proves registry + policy without a chain."""

from __future__ import annotations

from typing import Any

from .base import VidaPluginContext
from .policy import PolicyRequest


class DummyPlugin:
    """Dev/test plugin. capabilities: status only (plus policy checks for fake spend)."""

    name = "dummy"
    chain = "none"
    capabilities = ["status"]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "chain": self.chain,
            "capabilities": list(self.capabilities),
            "purpose": "Phase 0 test plugin — no chain",
        }

    def status(self, ctx: VidaPluginContext) -> dict[str, Any]:
        return {
            "ok": True,
            "plugin": self.name,
            "wallet_id": ctx.wallet_id,
            "network": ctx.network,
            "mode": ctx.mode,
            "message": "dummy status — no chain",
        }

    def fake_spend(self, ctx: VidaPluginContext, amount: float) -> dict[str, Any]:
        """
        Example gated action (not a real transfer).
        Used only to exercise evaluate_policy in tests.
        """
        decision = ctx.decide(PolicyRequest(chain=self.chain, action="transfer", amount=amount))
        if not decision.allowed:
            return {
                "ok": False,
                "error": decision.reason,
                "needs_approval": decision.needs_approval,
            }
        return {
            "ok": True,
            "spent": amount,
            "reason": decision.reason,
        }
