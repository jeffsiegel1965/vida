"""
TAO yield optimizer (MVP).

Honest scope:
- Scores validators on a subnet using on-chain emission (+ permit) as a proxy
- Produces a rebalance plan (keep reserve free TAO, stake the rest to top scorer)
- Can execute via plugin.delegate under session policy

This is NOT a guaranteed APY product. Emission is a heuristic for "active/valuable"
validators, not future yield.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


class OptimizerClient(Protocol):
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def get_balance(self, ss58_address: str) -> Any: ...
    def health(self) -> Any: ...


@dataclass
class ValidatorScore:
    netuid: int
    uid: int
    hotkey: str
    emission: int
    validator_permit: bool
    score: float
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class YieldPlan:
    ok: bool
    netuid: int
    free_tao: Decimal
    reserve_tao: Decimal
    stake_amount: Decimal
    target_hotkey: str = ""
    target_uid: int = -1
    candidates: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    action: str = "none"  # none | stake


def _as_list(val: Any) -> list:
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return list(val)
    return []


def score_subnet_validators(substrate: Any, netuid: int, top_n: int = 5) -> list[ValidatorScore]:
    """
    Query chain for emission + permit + keys on one netuid.
    Score = emission if permit else emission * 0.25 (miners can emit too; prefer permits).
    """
    n = substrate.query("SubtensorModule", "SubnetworkN", [netuid])
    n_val = int(n.value) if n is not None and n.value is not None else 0
    if n_val <= 0:
        return []

    emission = _as_list(
        getattr(substrate.query("SubtensorModule", "Emission", [netuid]), "value", None)
    )
    permit = _as_list(
        getattr(substrate.query("SubtensorModule", "ValidatorPermit", [netuid]), "value", None)
    )
    incentive = _as_list(
        getattr(substrate.query("SubtensorModule", "Incentive", [netuid]), "value", None)
    )

    scores: list[ValidatorScore] = []
    # Cap scan for speed on large subnets
    limit = min(n_val, max(top_n * 20, 64))
    for uid in range(limit):
        try:
            key_q = substrate.query("SubtensorModule", "Keys", [netuid, uid])
            hotkey = key_q.value if key_q is not None else None
            if not hotkey:
                continue
            em = int(emission[uid]) if uid < len(emission) else 0
            perm = bool(permit[uid]) if uid < len(permit) else False
            inc = int(incentive[uid]) if uid < len(incentive) else 0
            if em <= 0 and not perm:
                continue
            score = float(em) * (1.0 if perm else 0.25) + float(inc) * 0.01
            scores.append(
                ValidatorScore(
                    netuid=netuid,
                    uid=uid,
                    hotkey=str(hotkey),
                    emission=em,
                    validator_permit=perm,
                    score=score,
                    meta={"incentive": inc},
                )
            )
        except Exception:
            continue

    scores.sort(key=lambda s: s.score, reverse=True)
    return scores[:top_n]


def build_yield_plan(
    *,
    free_tao: Decimal | float | str,
    netuid: int,
    candidates: list[ValidatorScore],
    reserve_tao: Decimal | float | str = Decimal("0.01"),
    min_stake: Decimal | float | str = Decimal("0.01"),
    prefer_permit: bool = True,
) -> YieldPlan:
    free = Decimal(str(free_tao))
    reserve = Decimal(str(reserve_tao))
    min_s = Decimal(str(min_stake))
    stake_amt = free - reserve

    cand_dicts = [
        {
            "uid": c.uid,
            "hotkey": c.hotkey,
            "emission": c.emission,
            "validator_permit": c.validator_permit,
            "score": c.score,
        }
        for c in candidates
    ]

    if not candidates:
        return YieldPlan(
            ok=False,
            netuid=netuid,
            free_tao=free,
            reserve_tao=reserve,
            stake_amount=Decimal("0"),
            candidates=cand_dicts,
            reason="no scored validators",
            action="none",
        )

    # Prefer permit holders among top scores
    ordered = list(candidates)
    if prefer_permit:
        ordered = sorted(
            candidates,
            key=lambda c: (c.validator_permit, c.score),
            reverse=True,
        )
    top = ordered[0]

    if stake_amt < min_s:
        return YieldPlan(
            ok=True,
            netuid=netuid,
            free_tao=free,
            reserve_tao=reserve,
            stake_amount=Decimal("0"),
            target_hotkey=top.hotkey,
            target_uid=top.uid,
            candidates=cand_dicts,
            reason=f"free-reserve {stake_amt} below min_stake {min_s}; hold",
            action="none",
        )

    return YieldPlan(
        ok=True,
        netuid=netuid,
        free_tao=free,
        reserve_tao=reserve,
        stake_amount=stake_amt,
        target_hotkey=top.hotkey,
        target_uid=top.uid,
        candidates=cand_dicts,
        reason=f"stake {stake_amt} TAO to uid {top.uid} (score {top.score:.0f})",
        action="stake",
    )


def plan_to_dict(plan: YieldPlan) -> dict[str, Any]:
    return {
        "ok": plan.ok,
        "netuid": plan.netuid,
        "free_tao": str(plan.free_tao),
        "reserve_tao": str(plan.reserve_tao),
        "stake_amount": str(plan.stake_amount),
        "target_hotkey": plan.target_hotkey,
        "target_uid": plan.target_uid,
        "action": plan.action,
        "reason": plan.reason,
        "candidates": plan.candidates,
        "disclaimer": (
            "Heuristic optimizer using emission/permit — not guaranteed yield or APY"
        ),
    }
