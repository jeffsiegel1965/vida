"""
Live Bittensor/Substrate client for Vida TAO plugin.

Dependency: substrate-interface (installed via requirements.txt).

Scope for T1.1:
- connect with endpoint fallback
- health() — chain name + block number
- get_balance() — System.Account free/reserved in TAO

No key derivation. No extrinsics.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from .client import BalanceInfo, HealthInfo
from .config import TaoConfig, TaoNetwork, load_tao_config

logger = logging.getLogger(__name__)

# 1 TAO = 1e9 rao on Bittensor
RAO_PER_TAO = Decimal("1000000000")




def _scale_rao(value: Any) -> Decimal:
    """Convert chain balance units (rao) to TAO."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(int(value)) / RAO_PER_TAO
    except Exception:
        try:
            return Decimal(str(value)) / RAO_PER_TAO
        except Exception:
            return Decimal("0")


class SubstrateTaoClient:
    """
    Real WebSocket client for Bittensor (Finney / test).

    Implements TaoNetworkClient protocol.
    """

    def __init__(self, config: Optional[TaoConfig] = None) -> None:
        self.config = config or load_tao_config()
        if self.config.network == TaoNetwork.MOCK:
            raise ValueError("SubstrateTaoClient cannot use network=mock — use MockTaoClient")
        self._substrate: Any = None
        self._endpoint_used: str = ""
        self._SubstrateInterface = _import_substrate()

    def connect(self) -> None:
        if self._substrate is not None:
            return
        endpoints = self.config.resolved_endpoints()
        if not endpoints:
            raise RuntimeError(
                f"no endpoints configured for network={self.config.network.value}"
            )
        errors: list[str] = []
        for url in endpoints:
            try:
                # ss58_format: Bittensor uses 42
                self._substrate = self._SubstrateInterface(
                    url=url,
                    ss58_format=self.config.ss58_prefix,
                    use_remote_preset=True,
                )
                self._endpoint_used = url
                logger.info("TAO substrate connected: %s", url)
                return
            except Exception as e:
                errors.append(f"{url}: {type(e).__name__}: {e}")
                logger.warning("TAO endpoint failed %s: %s", url, e)
                self._substrate = None
        raise RuntimeError(
            "failed to connect to any TAO endpoint: " + " | ".join(errors)
        )

    def close(self) -> None:
        if self._substrate is not None:
            try:
                self._substrate.close()
            except Exception:
                pass
            self._substrate = None
            self._endpoint_used = ""

    def _require(self) -> Any:
        if self._substrate is None:
            raise RuntimeError("not connected — call connect() first")
        return self._substrate

    def health(self) -> HealthInfo:
        try:
            sub = self._require()
            chain = ""
            block_number: Optional[int] = None
            try:
                chain = str(sub.chain or "")
            except Exception:
                try:
                    chain = str(sub.rpc_request("system_chain", []).get("result", ""))
                except Exception:
                    chain = ""
            try:
                hdr = sub.get_block_header()
                # substrate-interface variants
                if isinstance(hdr, dict):
                    header = hdr.get("header") or hdr.get("block", {}).get("header") or hdr
                    num = header.get("number") if isinstance(header, dict) else None
                else:
                    num = getattr(hdr, "number", None)
                if num is not None:
                    if isinstance(num, str) and num.startswith("0x"):
                        block_number = int(num, 16)
                    else:
                        block_number = int(num)
            except Exception as e:
                logger.warning("block header query failed: %s", e)
            return HealthInfo(
                ok=True,
                network=self.config.network.value,
                endpoint=self._endpoint_used,
                block_number=block_number,
                chain_name=chain or "bittensor",
                meta={"ss58_prefix": self.config.ss58_prefix},
            )
        except Exception as e:
            return HealthInfo(
                ok=False,
                network=self.config.network.value,
                endpoint=self._endpoint_used,
                error=f"{type(e).__name__}: {e}",
            )

    def get_balance(self, ss58_address: str) -> BalanceInfo:
        if not ss58_address or not isinstance(ss58_address, str):
            return BalanceInfo(ok=False, address=str(ss58_address), error="invalid address")
        try:
            sub = self._require()
            result = sub.query(
                module="System",
                storage_function="Account",
                params=[ss58_address],
            )
            free = Decimal("0")
            reserved = Decimal("0")
            if result is not None and getattr(result, "value", None) is not None:
                val = result.value
                # Typical shape: {'nonce': N, 'consumers':.., 'data': {'free': .., 'reserved': ..}}
                data = val.get("data", val) if isinstance(val, dict) else None
                if isinstance(data, dict):
                    free = _scale_rao(data.get("free", 0))
                    reserved = _scale_rao(data.get("reserved", 0))
                elif isinstance(val, dict) and "free" in val:
                    free = _scale_rao(val.get("free", 0))
                    reserved = _scale_rao(val.get("reserved", 0))
            return BalanceInfo(
                ok=True,
                address=ss58_address,
                free_tao=free,
                reserved_tao=reserved,
                meta={"endpoint": self._endpoint_used, "unit": "TAO", "rao_per_tao": str(RAO_PER_TAO)},
            )
        except Exception as e:
            return BalanceInfo(
                ok=False,
                address=ss58_address,
                error=f"{type(e).__name__}: {e}",
            )

    def get_stake_positions(self, ss58_address: str) -> dict[str, Any]:
        return {
            "ok": True,
            "address": ss58_address,
            "positions": [],
            "note": "stake position enumeration still partial",
            "endpoint": self._endpoint_used,
        }

    def _keypair_from_cold_hex(self, coldkey_private_hex: str):
        from substrateinterface import Keypair

        raw = coldkey_private_hex[2:] if coldkey_private_hex.startswith("0x") else coldkey_private_hex
        return Keypair.create_from_private_key(
            bytes.fromhex(raw),
            ss58_format=self.config.ss58_prefix,
            crypto_type=1,
        )

    def submit_delegate(
        self,
        *,
        coldkey_private_hex: str,
        hotkey_ss58: str,
        netuid: int,
        amount_tao: Decimal | float | str,
    ) -> dict:
        """Submit stake extrinsic. Tries common SubtensorModule.add_stake param shapes."""
        try:
            sub = self._require()
            amount_rao = int(Decimal(str(amount_tao)) * RAO_PER_TAO)
            if amount_rao <= 0:
                return {"ok": False, "error": "amount must be positive"}
            kp = self._keypair_from_cold_hex(coldkey_private_hex)
            last_err = None
            candidates = [
                # Finney spec 424: hotkey + netuid + amount_staked
                ("SubtensorModule", "add_stake", {"hotkey": hotkey_ss58, "netuid": int(netuid), "amount_staked": amount_rao}),
                ("SubtensorModule", "add_stake", {"hotkey": hotkey_ss58, "amount_staked": amount_rao}),
                ("SubtensorModule", "add_stake", {"netuid": int(netuid), "hotkey": hotkey_ss58, "amount_staked": amount_rao}),
            ]
            for module, call, params in candidates:
                try:
                    call_obj = sub.compose_call(call_module=module, call_function=call, call_params=params)
                    ext = sub.create_signed_extrinsic(call=call_obj, keypair=kp)
                    receipt = sub.submit_extrinsic(ext, wait_for_inclusion=True)
                    h = getattr(receipt, "extrinsic_hash", None)
                    if hasattr(receipt, "is_success") and receipt.is_success is False:
                        return {
                            "ok": False,
                            "error": str(getattr(receipt, "error_message", "extrinsic failed")),
                            "extrinsic_hash": str(h) if h else None,
                        }
                    if not h:
                        return {
                            "ok": False,
                            "error": "submitted but no extrinsic_hash (fail-closed)",
                        }
                    return {
                        "ok": True,
                        "extrinsic_hash": str(h),
                        "action": "delegate",
                        "netuid": int(netuid),
                        "amount_tao": str(amount_tao),
                        "hotkey": hotkey_ss58,
                        "endpoint": self._endpoint_used,
                        "call": f"{module}.{call}",
                    }
                except Exception as e:
                    last_err = e
                    continue
            return {"ok": False, "error": f"add_stake failed: {type(last_err).__name__}: {last_err}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def submit_undelegate(
        self,
        *,
        coldkey_private_hex: str,
        hotkey_ss58: str,
        netuid: int,
        amount_tao: Decimal | float | str,
    ) -> dict:
        try:
            sub = self._require()
            amount_rao = int(Decimal(str(amount_tao)) * RAO_PER_TAO)
            if amount_rao <= 0:
                return {"ok": False, "error": "amount must be positive"}
            kp = self._keypair_from_cold_hex(coldkey_private_hex)
            last_err = None
            candidates = [
                ("SubtensorModule", "remove_stake", {"hotkey": hotkey_ss58, "netuid": int(netuid), "amount_unstaked": amount_rao}),
                ("SubtensorModule", "remove_stake", {"hotkey": hotkey_ss58, "amount_unstaked": amount_rao}),
                ("SubtensorModule", "remove_stake", {"netuid": int(netuid), "hotkey": hotkey_ss58, "amount_unstaked": amount_rao}),
            ]
            for module, call, params in candidates:
                try:
                    call_obj = sub.compose_call(call_module=module, call_function=call, call_params=params)
                    ext = sub.create_signed_extrinsic(call=call_obj, keypair=kp)
                    receipt = sub.submit_extrinsic(ext, wait_for_inclusion=True)
                    h = getattr(receipt, "extrinsic_hash", None)
                    if hasattr(receipt, "is_success") and receipt.is_success is False:
                        return {
                            "ok": False,
                            "error": str(getattr(receipt, "error_message", "extrinsic failed")),
                            "extrinsic_hash": str(h) if h else None,
                        }
                    if not h:
                        return {
                            "ok": False,
                            "error": "submitted but no extrinsic_hash (fail-closed)",
                        }
                    return {
                        "ok": True,
                        "extrinsic_hash": str(h),
                        "action": "undelegate",
                        "netuid": int(netuid),
                        "amount_tao": str(amount_tao),
                        "hotkey": hotkey_ss58,
                        "endpoint": self._endpoint_used,
                        "call": f"{module}.{call}",
                    }
                except Exception as e:
                    last_err = e
                    continue
            return {"ok": False, "error": f"remove_stake failed: {type(last_err).__name__}: {last_err}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}


    def submit_transfer(
        self,
        *,
        coldkey_private_hex: str,
        dest_ss58: str,
        amount_tao: Decimal | float | str,
        keep_alive: bool = True,
    ) -> dict:
        """P2P TAO payment: Balances.transfer_keep_alive or transfer_allow_death."""
        try:
            sub = self._require()
            amount_rao = int(Decimal(str(amount_tao)) * RAO_PER_TAO)
            if amount_rao <= 0:
                return {"ok": False, "error": "amount must be positive"}
            if not dest_ss58:
                return {"ok": False, "error": "dest_ss58 required"}
            kp = self._keypair_from_cold_hex(coldkey_private_hex)
            call_name = "transfer_keep_alive" if keep_alive else "transfer_allow_death"
            call_obj = sub.compose_call(
                call_module="Balances",
                call_function=call_name,
                call_params={"dest": dest_ss58, "value": amount_rao},
            )
            ext = sub.create_signed_extrinsic(call=call_obj, keypair=kp)
            receipt = sub.submit_extrinsic(ext, wait_for_inclusion=True)
            h = getattr(receipt, "extrinsic_hash", None)
            if hasattr(receipt, "is_success") and receipt.is_success is False:
                return {
                    "ok": False,
                    "error": str(getattr(receipt, "error_message", "extrinsic failed")),
                    "extrinsic_hash": str(h) if h else None,
                }
            if not h:
                return {
                    "ok": False,
                    "error": "submitted but no extrinsic_hash (fail-closed)",
                }
            return {
                "ok": True,
                "extrinsic_hash": str(h),
                "action": "transfer",
                "dest": dest_ss58,
                "amount_tao": str(amount_tao),
                "keep_alive": keep_alive,
                "endpoint": self._endpoint_used,
                "call": f"Balances.{call_name}",
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def make_tao_client(config: Optional[TaoConfig] = None) -> Any:
    """
    Factory: Mock for mock network; Substrate for finney/test.
    """
    from .client import MockTaoClient

    cfg = config or load_tao_config()
    if cfg.network == TaoNetwork.MOCK:
        return MockTaoClient(network=cfg.network.value)
    return SubstrateTaoClient(config=cfg)
