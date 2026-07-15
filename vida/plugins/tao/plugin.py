"""
TaoPlugin — Bittensor (TAO) plugin for Vida.

Capabilities: status, balance, owner provision, agent sessions,
policy-gated delegate/undelegate/transfer, yield optimizer MVP,
ML-DSA-65 PQ identity at rest (not on-chain).

Honesty: Finney uses sr25519 for spends; session caps are software policy.
"""

from __future__ import annotations

from typing import Any, Optional

from ..base import VidaPluginContext
from ..policy import PolicyRequest
from .accounts import TaoAccountStore
from .client import MockTaoClient, TaoNetworkClient
from .config import TaoConfig, TaoNetwork, load_tao_config


class TaoPlugin:
    name = "tao"
    chain = "bittensor"
    capabilities = ["status", "balance", "delegate", "undelegate", "transfer", "optimize", "session"]

    def __init__(
        self,
        config: Optional[TaoConfig] = None,
        client: Optional[TaoNetworkClient] = None,
        account_store: Optional[TaoAccountStore] = None,
    ) -> None:
        self.config = config or load_tao_config()
        if client is not None:
            self.client = client
        elif self.config.network == TaoNetwork.MOCK:
            self.client = MockTaoClient(network=self.config.network.value)
        else:
            from .substrate_client import SubstrateTaoClient

            self.client = SubstrateTaoClient(config=self.config)
        self.account_store = account_store
        from .staking import SpendTracker
        self._spend = SpendTracker()

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "chain": self.chain,
            "capabilities": list(self.capabilities),
            "network": self.config.network.value,
            "ss58_prefix": self.config.ss58_prefix,
            "endpoints": self.config.resolved_endpoints(),
            "phase": "stake_policy",
            "derivation": "owner_provision_only",
            "docs": "docs/plugins/tao.md",
        }

    def status(self, ctx: VidaPluginContext) -> dict[str, Any]:
        """
        Read-only status. Safe for agents.

        Includes free/reserved TAO when account is provisioned and client works.
        Never returns private keys or seed material.
        """
        out: dict[str, Any] = {
            "ok": True,
            "plugin": self.name,
            "wallet_id": ctx.wallet_id,
            "network": self.config.network.value,
            "mode": ctx.mode,
            "provisioned": False,
            "ss58_address": None,
            "hotkey_ss58": None,
            "client": None,
            "balance": None,
            "phase": "stake_policy",
            "capabilities": list(self.capabilities),
        }

        if self.account_store is not None:
            rec = self.account_store.load(ctx.wallet_id)
            if rec is not None:
                out["provisioned"] = bool(rec.provisioned and rec.ss58_address)
                out["account"] = rec.to_public_dict()
                out["pq"] = {
                    "pq_ready": bool(rec.pq_public_key and rec.enc_pq_sk),
                    "pq_scheme": "ML-DSA-65" if rec.pq_public_key else None,
                    "pq_public_key": rec.pq_public_key,
                    "pq_on_chain": False,
                    "note": "Forward identity — Finney still uses sr25519 on-chain",
                }
                out["ss58_address"] = rec.ss58_address or None
                hot = (rec.meta or {}).get("hotkey_ss58")
                if hot:
                    out["hotkey_ss58"] = hot
            else:
                out["account"] = None
        else:
            out["account_store"] = "not_configured"

        if self.client is None:
            out["client"] = {
                "ok": False,
                "error": "no client configured",
            }
            out["ok"] = False
            return out

        try:
            self.client.connect()
            health = self.client.health()
            out["client"] = {
                "ok": health.ok,
                "endpoint": health.endpoint,
                "block_number": health.block_number,
                "chain_name": health.chain_name,
                "error": health.error,
            }
            if not health.ok:
                out["ok"] = False

            addr = out.get("ss58_address")
            if isinstance(addr, str) and addr:
                bal = self.client.get_balance(addr)
                out["balance"] = {
                    "ok": bal.ok,
                    "free_tao": str(bal.free_tao),
                    "reserved_tao": str(bal.reserved_tao),
                    "unit": "TAO",
                    "error": bal.error,
                    "meta": dict(bal.meta or {}),
                }
                if not bal.ok:
                    out["ok"] = False
            else:
                out["balance"] = {
                    "ok": False,
                    "error": "not_provisioned",
                    "free_tao": None,
                    "reserved_tao": None,
                }
        except NotImplementedError as e:
            out["client"] = {"ok": False, "error": str(e)}
            out["ok"] = False
        except Exception as e:  # pragma: no cover
            out["client"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            out["ok"] = False
        finally:
            try:
                self.client.close()
            except Exception:
                pass

        return out

    def balance(self, ctx: VidaPluginContext) -> dict[str, Any]:
        """Explicit balance helper (same data as status['balance'] when provisioned)."""
        st = self.status(ctx)
        bal = st.get("balance") or {}
        return {
            "ok": bool(bal.get("ok")),
            "wallet_id": ctx.wallet_id,
            "ss58_address": st.get("ss58_address"),
            "network": st.get("network"),
            "balance": bal,
            "client": st.get("client"),
            "provisioned": st.get("provisioned"),
        }

    def check_action(
        self, ctx: VidaPluginContext, action: str, amount: float = 0.0
    ) -> dict[str, Any]:
        """Policy preflight — used by future transfer/stake; available now for tests."""
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
        }

    def provision_from_seed(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Blocked on agent path. Owner scripts call owner_provision() instead."""
        return {
            "ok": False,
            "error": (
                "agent path blocked — owner must run scripts/provision_tao_account.py "
                "or TaoPlugin.owner_provision(...)"
            ),
        }

    def owner_provision(
        self,
        *,
        wallet_id: str,
        mnemonic: str,
        password: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        Owner-only provisioning. Requires account_store.
        Do not expose as a Hermes tool that accepts mnemonics from chat.
        """
        if self.account_store is None:
            return {"ok": False, "error": "account_store not configured"}
        from .provision import provision_tao_account

        return provision_tao_account(
            wallet_id=wallet_id,
            mnemonic=mnemonic,
            password=password,
            network=self.config.network.value,
            store=self.account_store,
            ss58_prefix=self.config.ss58_prefix,
            overwrite=overwrite,
        )

    def _stake_action(
        self,
        ctx: VidaPluginContext,
        *,
        action: str,
        amount_tao: float,
        netuid: int,
        hotkey: str = "",
        confirm: bool = False,
        password: str | None = None,
        session_path: str | None = None,
    ) -> dict[str, Any]:
        """Shared path for delegate/undelegate.

        Unlock order:
        1) session_path (agent — no owner password)
        2) password (owner path)
        """
        from .staking import evaluate_stake

        if not confirm:
            return {
                "ok": False,
                "error": "confirm=True required for stake actions",
                "needs_confirm": True,
            }
        if self.account_store is None:
            return {"ok": False, "error": "account_store not configured"}
        rec = self.account_store.load(ctx.wallet_id)
        if rec is None or not rec.provisioned or not rec.ss58_address:
            return {"ok": False, "error": "wallet not provisioned for TAO"}

        # Resolve signing secrets
        secrets: dict = {}
        mode = ctx.mode
        max_per_tx = ctx.max_per_tx
        daily_limit = ctx.daily_limit
        threshold = ctx.threshold
        allowed_actions = ctx.allowed_actions
        allowed_subnets = ctx.allowed_subnets
        session_revoked = ctx.session_revoked
        unlock_via = None

        if session_path:
            from .session import load_tao_session_secrets

            sess = load_tao_session_secrets(session_path)
            if not sess.get("ok"):
                return {
                    "ok": False,
                    "error": sess.get("error", "session unlock failed"),
                    "session_revoked": bool(sess.get("session_revoked")),
                }
            if sess.get("wallet_id") and sess["wallet_id"] != ctx.wallet_id:
                return {"ok": False, "error": "session wallet_id mismatch"}
            limits = sess.get("limits") or {}
            mode = limits.get("mode") or mode
            max_per_tx = float(limits.get("max_tao_per_tx") or max_per_tx)
            daily_limit = float(limits.get("max_tao_per_day") or daily_limit)
            threshold = float(limits.get("threshold") or threshold)
            if limits.get("allowed_actions") is not None:
                allowed_actions = list(limits["allowed_actions"])
            if limits.get("allowed_subnets") is not None:
                allowed_subnets = list(limits["allowed_subnets"])
            secrets = dict(sess.get("secrets") or {})
            unlock_via = "session"
            _session_daily = float(sess.get("daily_spent") or 0)
        elif password:
            from .provision import unlock_tao_secrets

            unlocked = unlock_tao_secrets(rec, password)
            if not unlocked.get("ok"):
                return {"ok": False, "error": unlocked.get("error", "unlock failed")}
            secrets = unlocked["secrets"]
            unlock_via = "password"
        else:
            return {
                "ok": False,
                "error": "session_path or password required to unlock coldkey for signing",
            }

        hot = hotkey or secrets.get("hotkey_ss58") or (rec.meta or {}).get("hotkey_ss58") or ""
        if not hot:
            secrets.clear()
            return {"ok": False, "error": "hotkey ss58 required"}

        self._spend._roll()
        if unlock_via == "session":
            daily_spent = float(locals().get("_session_daily", 0) or 0)
            if ctx.daily_spent:
                daily_spent = max(daily_spent, float(ctx.daily_spent))
        else:
            daily_spent = self._spend.daily_spent if ctx.daily_spent == 0 else ctx.daily_spent
        decision = evaluate_stake(
            mode=mode,
            amount=float(amount_tao),
            action=action,
            netuid=int(netuid),
            threshold=threshold,
            max_per_tx=max_per_tx,
            daily_limit=daily_limit,
            daily_spent=daily_spent,
            allowed_actions=allowed_actions,
            allowed_subnets=allowed_subnets,
            session_revoked=session_revoked,
            confirm=confirm,
        )
        if not decision.allowed:
            secrets.clear()
            return {
                "ok": False,
                "error": decision.reason,
                "needs_approval": decision.needs_approval,
                "policy": decision.reason,
                "unlock_via": unlock_via,
            }

        if self.client is None:
            secrets.clear()
            return {"ok": False, "error": "no client configured"}

        cold_hex = secrets.get("cold_private_hex") or ""
        if not cold_hex:
            secrets.clear()
            return {"ok": False, "error": "no cold private key available"}

        try:
            self.client.connect()
            if action == "delegate":
                result = self.client.submit_delegate(
                    coldkey_private_hex=cold_hex,
                    hotkey_ss58=hot,
                    netuid=int(netuid),
                    amount_tao=amount_tao,
                )
            else:
                result = self.client.submit_undelegate(
                    coldkey_private_hex=cold_hex,
                    hotkey_ss58=hot,
                    netuid=int(netuid),
                    amount_tao=amount_tao,
                )
        except Exception as e:
            result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            try:
                self.client.close()
            except Exception:
                pass
            secrets.clear()
            cold_hex = ""

        if result.get("ok"):
            self._spend.add(float(amount_tao), {"action": action, "netuid": netuid})
            result = dict(result)
            result["unlock_via"] = unlock_via
            if unlock_via == "session" and session_path:
                from .session import record_tao_session_spend
                rec_s = record_tao_session_spend(session_path, float(amount_tao))
                result["session_spend"] = rec_s
        return result

    def delegate(
        self,
        ctx: VidaPluginContext,
        *,
        amount_tao: float,
        netuid: int,
        hotkey: str = "",
        confirm: bool = False,
        password: str | None = None,
        session_path: str | None = None,
    ) -> dict[str, Any]:
        return self._stake_action(
            ctx,
            action="delegate",
            amount_tao=amount_tao,
            netuid=netuid,
            hotkey=hotkey,
            confirm=confirm,
            password=password,
            session_path=session_path,
        )

    def undelegate(
        self,
        ctx: VidaPluginContext,
        *,
        amount_tao: float,
        netuid: int,
        hotkey: str = "",
        confirm: bool = False,
        password: str | None = None,
        session_path: str | None = None,
    ) -> dict[str, Any]:
        return self._stake_action(
            ctx,
            action="undelegate",
            amount_tao=amount_tao,
            netuid=netuid,
            hotkey=hotkey,
            confirm=confirm,
            password=password,
            session_path=session_path,
        )

    def transfer(
        self,
        ctx: VidaPluginContext,
        *,
        dest_ss58: str,
        amount_tao: float,
        confirm: bool = False,
        password: str | None = None,
        session_path: str | None = None,
        keep_alive: bool = True,
    ) -> dict[str, Any]:
        """P2P TAO payment under policy + session/password unlock."""
        from .staking import evaluate_stake

        if not confirm:
            return {"ok": False, "error": "confirm=True required for transfer", "needs_confirm": True}
        if self.account_store is None:
            return {"ok": False, "error": "account_store not configured"}
        rec = self.account_store.load(ctx.wallet_id)
        if rec is None or not rec.provisioned:
            return {"ok": False, "error": "wallet not provisioned for TAO"}
        if not dest_ss58:
            return {"ok": False, "error": "dest_ss58 required"}

        secrets: dict = {}
        mode = ctx.mode
        max_per_tx = ctx.max_per_tx
        daily_limit = ctx.daily_limit
        threshold = ctx.threshold
        allowed_actions = ctx.allowed_actions or ["transfer", "delegate", "undelegate"]
        allowed_subnets = ctx.allowed_subnets
        session_revoked = ctx.session_revoked
        unlock_via = None
        allowed_destinations = None
        allow_any_dest_flag = False
        _session_daily = 0.0

        if session_path:
            from .session import load_tao_session_secrets
            sess = load_tao_session_secrets(session_path)
            if not sess.get("ok"):
                return {"ok": False, "error": sess.get("error", "session unlock failed"),
                        "session_revoked": bool(sess.get("session_revoked"))}
            if sess.get("wallet_id") and sess["wallet_id"] != ctx.wallet_id:
                return {"ok": False, "error": "session wallet_id mismatch"}
            limits = sess.get("limits") or {}
            mode = limits.get("mode") or mode
            max_per_tx = float(limits.get("max_tao_per_tx") or max_per_tx)
            daily_limit = float(limits.get("max_tao_per_day") or daily_limit)
            threshold = float(limits.get("threshold") or threshold)
            if limits.get("allowed_actions") is not None:
                allowed_actions = list(limits["allowed_actions"])
            if limits.get("allowed_destinations") is not None:
                allowed_destinations = list(limits["allowed_destinations"])
            allow_any_dest_flag = bool(limits.get("allow_any_dest"))
            secrets = dict(sess.get("secrets") or {})
            unlock_via = "session"
            _session_daily = float(sess.get("daily_spent") or 0)
        elif password:
            from .provision import unlock_tao_secrets
            unlocked = unlock_tao_secrets(rec, password)
            if not unlocked.get("ok"):
                return {"ok": False, "error": unlocked.get("error", "unlock failed")}
            secrets = unlocked["secrets"]
            unlock_via = "password"
        else:
            return {"ok": False, "error": "session_path or password required"}

        if unlock_via == "session":
            if allowed_destinations is None and not allow_any_dest_flag:
                secrets.clear()
                return {
                    "ok": False,
                    "error": (
                        "session transfer denied: no allowed_destinations "
                        "(re-grant with --dest or allow_any_dest)"
                    ),
                }
        if allowed_destinations is not None:
            allow = set(allowed_destinations)
            if not allow:
                secrets.clear()
                return {"ok": False, "error": "allowed_destinations empty — deny all transfers"}
            if dest_ss58 not in allow:
                secrets.clear()
                return {"ok": False, "error": "destination not in session allowed_destinations"}

        self._spend._roll()
        if unlock_via == "session":
            daily_spent = float(locals().get("_session_daily", 0) or 0)
            if ctx.daily_spent:
                daily_spent = max(daily_spent, float(ctx.daily_spent))
        else:
            daily_spent = self._spend.daily_spent if ctx.daily_spent == 0 else ctx.daily_spent
        # reuse stake policy with action=transfer (netuid ignored if no allowlist subnets for transfer)
        decision = evaluate_stake(
            mode=mode,
            amount=float(amount_tao),
            action="transfer",
            netuid=0,
            threshold=threshold,
            max_per_tx=max_per_tx,
            daily_limit=daily_limit,
            daily_spent=daily_spent,
            allowed_actions=allowed_actions,
            allowed_subnets=None,  # transfers are not subnet-scoped
            session_revoked=session_revoked,
            confirm=confirm,
        )
        if not decision.allowed:
            secrets.clear()
            return {
                "ok": False,
                "error": decision.reason,
                "needs_approval": decision.needs_approval,
                "unlock_via": unlock_via,
            }

        cold_hex = secrets.get("cold_private_hex") or ""
        if not cold_hex or self.client is None:
            secrets.clear()
            return {"ok": False, "error": "missing coldkey or client"}

        try:
            self.client.connect()
            result = self.client.submit_transfer(
                coldkey_private_hex=cold_hex,
                dest_ss58=dest_ss58,
                amount_tao=amount_tao,
                keep_alive=keep_alive,
            )
        except Exception as e:
            result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            try:
                self.client.close()
            except Exception:
                pass
            secrets.clear()

        if result.get("ok"):
            self._spend.add(float(amount_tao), {"action": "transfer", "dest": dest_ss58})
            result = dict(result)
            result["unlock_via"] = unlock_via
            if unlock_via == "session" and session_path:
                from .session import record_tao_session_spend
                rec_s = record_tao_session_spend(session_path, float(amount_tao))
                result["session_spend"] = rec_s
        return result

    def optimize_yield(
        self,
        ctx: VidaPluginContext,
        *,
        netuid: int = 1,
        reserve_tao: float = 0.01,
        min_stake: float = 0.01,
        top_n: int = 5,
        execute: bool = False,
        confirm: bool = False,
        password: str | None = None,
        session_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Plan (and optionally execute) a simple yield allocation on one subnet.

        execute=True requires confirm=True and session/password; stakes under policy.
        """
        from decimal import Decimal

        from .yield_optimizer import (
            ValidatorScore,
            build_yield_plan,
            plan_to_dict,
            score_subnet_validators,
        )

        if self.account_store is None:
            return {"ok": False, "error": "account_store not configured"}
        rec = self.account_store.load(ctx.wallet_id)
        if rec is None or not rec.provisioned or not rec.ss58_address:
            return {"ok": False, "error": "wallet not provisioned"}
        if self.client is None:
            return {"ok": False, "error": "no client"}

        plan = None
        bal_ok = False
        free = Decimal("0")
        try:
            self.client.connect()
            bal = self.client.get_balance(rec.ss58_address)
            bal_ok = bool(bal.ok)
            free = Decimal(str(bal.free_tao or 0))
            candidates: list = []
            sub = getattr(self.client, "_substrate", None)
            if sub is not None:
                candidates = score_subnet_validators(sub, int(netuid), top_n=top_n)
            else:
                # Mock path: optional preloaded ValidatorScore list
                raw = getattr(self.client, "mock_validators", None) or []
                candidates = list(raw)
            plan = build_yield_plan(
                free_tao=free,
                netuid=int(netuid),
                candidates=candidates,
                reserve_tao=reserve_tao,
                min_stake=min_stake,
            )
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            try:
                self.client.close()
            except Exception:
                pass

        if plan is None:
            return {"ok": False, "error": "plan failed"}

        out = plan_to_dict(plan)
        out["wallet_id"] = ctx.wallet_id
        out["ss58_address"] = rec.ss58_address
        out["balance_ok"] = bal_ok
        out["executed"] = False

        if not execute:
            return out
        if plan.action != "stake" or plan.stake_amount <= 0:
            out["execute_skipped"] = plan.reason
            return out

        stake_res = self.delegate(
            ctx,
            amount_tao=float(plan.stake_amount),
            netuid=int(netuid),
            hotkey=plan.target_hotkey,
            confirm=confirm,
            password=password,
            session_path=session_path,
        )
        out["executed"] = bool(stake_res.get("ok"))
        out["stake_result"] = stake_res
        return out
