"""TAO network client interface + mock. Live client: substrate_client.SubstrateTaoClient."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class HealthInfo:
    ok: bool
    network: str
    endpoint: str = ""
    block_number: Optional[int] = None
    chain_name: str = ""
    error: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class BalanceInfo:
    ok: bool
    address: str
    free_tao: Decimal = Decimal("0")
    reserved_tao: Decimal = Decimal("0")
    error: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class TaoNetworkClient(Protocol):
    """Minimal chain surface the TAO plugin is allowed to call."""

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def health(self) -> HealthInfo: ...

    def get_balance(self, ss58_address: str) -> BalanceInfo: ...

    def get_stake_positions(self, ss58_address: str) -> dict[str, Any]: ...


class MockTaoClient:
    """
    Offline client for unit tests and infra development.
    No network I/O. Balances come from an in-memory map.
    """

    def __init__(
        self,
        network: str = "mock",
        balances: Optional[dict[str, Decimal]] = None,
        block_number: int = 1,
    ) -> None:
        self.network = network
        self._balances = {k: Decimal(str(v)) for k, v in (balances or {}).items()}
        self._block = block_number
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def close(self) -> None:
        self._connected = False

    def health(self) -> HealthInfo:
        if not self._connected:
            return HealthInfo(
                ok=False,
                network=self.network,
                error="not connected — call connect() first",
            )
        return HealthInfo(
            ok=True,
            network=self.network,
            endpoint="mock://local",
            block_number=self._block,
            chain_name="mock-bittensor",
        )

    def get_balance(self, ss58_address: str) -> BalanceInfo:
        if not self._connected:
            return BalanceInfo(ok=False, address=ss58_address, error="not connected")
        if not ss58_address or not isinstance(ss58_address, str):
            return BalanceInfo(ok=False, address=str(ss58_address), error="invalid address")
        free = self._balances.get(ss58_address, Decimal("0"))
        return BalanceInfo(ok=True, address=ss58_address, free_tao=free)

    def get_stake_positions(self, ss58_address: str) -> dict[str, Any]:
        # Phase 1B
        return {
            "ok": True,
            "address": ss58_address,
            "positions": [],
            "note": "stake positions not implemented in infra slice",
        }

    def set_balance(self, ss58_address: str, free_tao: Decimal | float | str) -> None:
        self._balances[ss58_address] = Decimal(str(free_tao))

    def submit_delegate(
        self,
        *,
        coldkey_private_hex: str,
        hotkey_ss58: str,
        netuid: int,
        amount_tao: Decimal | float | str,
    ) -> dict:
        if not self._connected:
            return {"ok": False, "error": "not connected"}
        amt = Decimal(str(amount_tao))
        if amt <= 0:
            return {"ok": False, "error": "amount must be positive"}
        # Mock extrinsic hash
        h = f"mock_delegate_{netuid}_{amt}_{hotkey_ss58[:8]}"
        return {
            "ok": True,
            "extrinsic_hash": h,
            "action": "delegate",
            "netuid": netuid,
            "amount_tao": str(amt),
            "hotkey": hotkey_ss58,
            "mock": True,
        }

    def submit_undelegate(
        self,
        *,
        coldkey_private_hex: str,
        hotkey_ss58: str,
        netuid: int,
        amount_tao: Decimal | float | str,
    ) -> dict:
        if not self._connected:
            return {"ok": False, "error": "not connected"}
        amt = Decimal(str(amount_tao))
        if amt <= 0:
            return {"ok": False, "error": "amount must be positive"}
        h = f"mock_undelegate_{netuid}_{amt}_{hotkey_ss58[:8]}"
        return {
            "ok": True,
            "extrinsic_hash": h,
            "action": "undelegate",
            "netuid": netuid,
            "amount_tao": str(amt),
            "hotkey": hotkey_ss58,
            "mock": True,
        }

    def submit_transfer(
        self,
        *,
        coldkey_private_hex: str,
        dest_ss58: str,
        amount_tao: Decimal | float | str,
        keep_alive: bool = True,
    ) -> dict:
        if not self._connected:
            return {"ok": False, "error": "not connected"}
        amt = Decimal(str(amount_tao))
        if amt <= 0:
            return {"ok": False, "error": "amount must be positive"}
        # debit mock balance if tracked
        # (caller address unknown from private hex — skip balance move for mock)
        h = f"mock_transfer_{amt}_{dest_ss58[:8]}"
        return {
            "ok": True,
            "extrinsic_hash": h,
            "action": "transfer",
            "dest": dest_ss58,
            "amount_tao": str(amt),
            "keep_alive": keep_alive,
            "mock": True,
        }


class UnimplementedLiveTaoClient:
    """
    Legacy placeholder kept for tests.

    Prefer SubstrateTaoClient from .substrate_client for real RPC.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs

    def connect(self) -> None:
        raise NotImplementedError(
            "Use SubstrateTaoClient (vida.plugins.tao.substrate_client) for live RPC; MockTaoClient for offline tests."
        )

    def close(self) -> None:
        return None

    def health(self) -> HealthInfo:
        raise NotImplementedError("Use SubstrateTaoClient for live RPC")

    def get_balance(self, ss58_address: str) -> BalanceInfo:
        raise NotImplementedError("Use SubstrateTaoClient for live RPC")

    def get_stake_positions(self, ss58_address: str) -> dict[str, Any]:
        raise NotImplementedError("Use SubstrateTaoClient for live RPC")
