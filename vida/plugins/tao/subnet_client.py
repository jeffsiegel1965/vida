"""Agent subnet client — purchase and consume Bittensor subnet services.

Current chain: Finney (pre-dTAO). Agents pay for subnet access by staking
TAO to subnet hotkeys via `add_stake(hotkey, netuid, amount_staked)`.

When dTAO is deployed, the payment model will change to subnet token swaps.
The `AgentSubnetPurchase` class is designed to abstract this — update the
`pay()` method when dTAO goes live.

Agents can:
1. Discover subnets offering specific services
2. Check pricing and requirements
3. Pay for access (stake TAO to subnet hotkey — current Finney model)
4. Query the subnet's API to consume the service
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from .subnet_marketplace import (
    SUBNET_REGISTRY,
    ServiceType,
    SubnetInfo,
    SubnetRegistry,
)

logger = logging.getLogger(__name__)

# ── Subnet gateway fee tracking ──

_QUERY_COUNTS: dict[str, int] = {}  # wallet_id → daily query count


def _get_daily_query_count(wallet_id: str) -> int:
    """Get the number of queries made by this wallet today."""
    return _QUERY_COUNTS.get(wallet_id, 0)


def _increment_query_count(wallet_id: str) -> int:
    """Increment and return the query count for this wallet."""
    count = _QUERY_COUNTS.get(wallet_id, 0) + 1
    _QUERY_COUNTS[wallet_id] = count
    return count


def _apply_subnet_query_fee(
    amount_tao: float,
    wallet_id: str = "",
) -> dict[str, Any]:
    """Calculate and return subnet gateway fee info.
    
    Returns fee info including whether the query is free (first N per day).
    """
    from vida.plugins.covenant.fees import (
        SUBNET_FEE_SCHEDULE,
        calc_subnet_query_fee,
        get_tao_fee_address,
    )
    
    daily_count = _get_daily_query_count(wallet_id) if wallet_id else 999
    is_free = daily_count < SUBNET_FEE_SCHEDULE.free_queries_per_day
    
    if is_free:
        return {
            "fee_tao": 0.0,
            "fee_pct": 0.0,
            "is_free": True,
            "free_queries_remaining": SUBNET_FEE_SCHEDULE.free_queries_per_day - daily_count - 1,
            "tao_fee_address": "",
            "note": "Free query — within daily free tier",
        }
    
    fee = calc_subnet_query_fee(amount_tao)
    return {
        "fee_tao": fee,
        "fee_pct": SUBNET_FEE_SCHEDULE.query_fee_pct * 100,
        "is_free": False,
        "free_queries_remaining": 0,
        "tao_fee_address": get_tao_fee_address(),
        "note": f"Vida subnet gateway fee: {fee} TAO ({SUBNET_FEE_SCHEDULE.query_fee_pct * 100}%)",
    }

# ── Payment ──


def _stake_for_subnet_access(
    substrate_client: Any,
    coldkey_hex: str,
    hotkey_ss58: str,
    netuid: int,
    amount_tao: float,
) -> dict[str, Any]:
    """Stake TAO to a subnet's hotkey to gain access.

    Delegates the subagent to use the substrate_client's staking extrinsic.
    """
    try:
        return substrate_client.submit_delegate(
            coldkey_private_hex=coldkey_hex,
            hotkey_ss58=hotkey_ss58,
            netuid=netuid,
            amount_tao=amount_tao,
        )
    except Exception as e:
        return {"ok": False, "error": f"stake failed: {e}"}


def _pay_per_request(
    substrate_client: Any,
    coldkey_hex: str,
    dest_ss58: str,
    amount_tao: float,
) -> dict[str, Any]:
    """Direct TAO transfer for per-request payment."""
    try:
        return substrate_client.submit_transfer(
            coldkey_private_hex=coldkey_hex,
            dest_ss58=dest_ss58,
            amount_tao=amount_tao,
        )
    except Exception as e:
        return {"ok": False, "error": f"payment failed: {e}"}


# ── Subnet API Client ──


def _call_subnet_api(
    endpoint: str,
    method: str = "POST",
    headers: Optional[dict[str, str]] = None,
    body: Optional[dict[str, Any]] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Call a subnet's REST API endpoint."""
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)

    data = json.dumps(body).encode() if body else None
    req = Request(endpoint, data=data, headers=hdrs, method=method)

    try:
        with urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return {"ok": True, "data": result, "status": resp.status}
    except URLError as e:
        return {"ok": False, "error": f"API call failed: {e.reason}"}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"invalid JSON response: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ── Agent Purchase Workflow ──


class AgentSubnetPurchase:
    """A complete purchase+consume workflow for a Bittensor subnet service.

    Steps:
    1. resolve_subnet() — find the right subnet
    2. check_requirements() — validate balance and access
    3. pay() — stake TAO or send per-request payment
    4. query() — call the subnet's API to consume the service
    """

    def __init__(self, substrate_client: Any, coldkey_hex: str):
        self._substrate = substrate_client
        self._coldkey_hex = coldkey_hex
        self._netuid: Optional[int] = None
        self._subnet_info: Optional[SubnetInfo] = None
        self._payment_result: Optional[dict[str, Any]] = None
        self._query_result: Optional[dict[str, Any]] = None

    def resolve_subnet(self, netuid: int) -> dict[str, Any]:
        """Find a subnet by netuid and cache its info."""
        info = SubnetRegistry.get_by_netuid(netuid)
        if not info:
            return {"ok": False, "error": f"subnet {netuid} not found in registry"}
        self._netuid = netuid
        self._subnet_info = info
        return {
            "ok": True,
            "subnet": info.to_dict(),
            "message": f"Found subnet {netuid}: {info.name}",
        }

    def resolve_by_capability(self, capability: str) -> dict[str, Any]:
        """Find subnets offering a specific capability."""
        results = SubnetRegistry.find_by_capability(capability)
        if not results:
            return {
                "ok": False,
                "error": f"no subnets found for '{capability}'",
                "suggestions": ["llm", "compute", "gpu", "image", "audio", "storage"],
            }
        # Pick the first match
        info = SUBNET_REGISTRY.get(results[0]["netuid"])
        if info:
            self._netuid = info.netuid
            self._subnet_info = info
        return {
            "ok": True,
            "results": results,
            "count": len(results),
            "message": f"Found {len(results)} subnet(s) for '{capability}'",
            "selected": results[0] if results else None,
        }

    def check_balance(self, ss58_address: str) -> dict[str, Any]:
        """Check if the agent has enough TAO to use a subnet."""
        try:
            bal = self._substrate.get_balance(ss58_address)
            return (
                {
                    "ok": bal.ok,
                    "free_tao": float(bal.free_tao),
                    "reserved_tao": float(bal.reserved_tao),
                    "address": ss58_address,
                }
                if bal.ok
                else {
                    "ok": False,
                    "error": bal.error,
                }
            )
        except Exception as e:
            return {"ok": False, "error": f"balance check failed: {e}"}

    def pay(
        self,
        amount_tao: float,
        hotkey_ss58: str = "",
        payment_type: str = "stake",
    ) -> dict[str, Any]:
        """Pay for subnet access.

        Current Finney chain: stake TAO to a subnet hotkey via
        `SubtensorModule.add_stake(hotkey, netuid, amount_staked)`.

        dTAO readiness: when dTAO is deployed, this method will be updated
        to use subnet token swaps instead of direct staking. The AgentMemory
        system will track the transition.

        payment_type options:
        - "stake": Stake TAO to a subnet hotkey (current Finney model)
        - "transfer": Direct TAO transfer (pay-as-you-go)
        """
        if not self._subnet_info:
            return {"ok": False, "error": "no subnet resolved — call resolve_subnet() first"}

        if payment_type == "stake":
            if not hotkey_ss58:
                return {"ok": False, "error": "hotkey_ss58 required for staking"}
            result = _stake_for_subnet_access(
                self._substrate,
                self._coldkey_hex,
                hotkey_ss58,
                self._subnet_info.netuid,
                amount_tao,
            )
        elif payment_type == "transfer":
            if not hotkey_ss58:
                return {"ok": False, "error": "destination address required for transfer"}
            result = _pay_per_request(
                self._substrate,
                self._coldkey_hex,
                hotkey_ss58,
                amount_tao,
            )
        else:
            return {"ok": False, "error": f"unknown payment type: {payment_type}"}

        self._payment_result = result
        return result

    def query(
        self,
        endpoint_path: str = "",
        method: str = "POST",
        body: Optional[dict[str, Any]] = None,
        wallet_id: str = "",
        amount_tao: float = 0.0,
    ) -> dict[str, Any]:
        """Query a subnet's API to consume the service.
        
        If no endpoint_path is given, uses the subnet's default API endpoint.
        
        Args:
            wallet_id: Agent wallet ID for fee tracking (query count)
            amount_tao: Amount being paid for this query (for fee calculation)
        """
        if not self._subnet_info:
            return {"ok": False, "error": "no subnet resolved"}

        base = self._subnet_info.api_endpoint
        if not base and not endpoint_path:
            return {"ok": False, "error": "no API endpoint configured for this subnet"}

        url = f"{base.rstrip('/')}/{endpoint_path.lstrip('/')}" if base else endpoint_path

        result = _call_subnet_api(url, method=method, body=body)
        self._query_result = result
        
        # Track query count and calculate fee
        if wallet_id:
            _increment_query_count(wallet_id)
        fee_info = _apply_subnet_query_fee(amount_tao, wallet_id=wallet_id)
        
        if result.get("ok"):
            result["vida_fee"] = fee_info
            result["vida_gateway"] = "powered by Vida Wallet"
            result["note"] = fee_info.get("note", "")
        
        return result

    def status(self) -> dict[str, Any]:
        """Get the current status of this purchase workflow."""
        return {
            "netuid": self._netuid,
            "subnet_name": self._subnet_info.name if self._subnet_info else None,
            "has_payment": self._payment_result is not None,
            "payment_ok": self._payment_result.get("ok") if self._payment_result else None,
            "has_query_result": self._query_result is not None,
            "query_ok": self._query_result.get("ok") if self._query_result else None,
        }


# ── High-level tools for the orchestrator ──


def tao_list_subnets(
    service_type: str = "",
    query: str = "",
) -> dict[str, Any]:
    """List available Bittensor subnets and their services."""
    try:
        if service_type:
            try:
                st = ServiceType(service_type)
                results = SubnetRegistry.search(service_type=st)
            except ValueError:
                # Fall back to by-capability lookup
                results = SubnetRegistry.find_by_capability(service_type)
        elif query:
            results = SubnetRegistry.search(query=query)
        else:
            results = SubnetRegistry.list_all()

        return {
            "ok": True,
            "count": len(results),
            "subnets": results,
            "message": f"{len(results)} subnet(s) found",
        }
    except Exception as e:
        return {"ok": False, "error": f"list subnets failed: {e}"}


def tao_subnet_query(
    netuid: int, endpoint_path: str = "", method: str = "POST", body: Optional[dict[str, Any]] = None,
    wallet_id: str = "", amount_tao: float = 0.0,
) -> dict[str, Any]:
    """Query a subnet's API to consume its service.
    
    Args:
        wallet_id: Agent wallet ID for fee tracking
        amount_tao: Amount being paid for this query (for fee calculation)
    """
    try:
        info = SubnetRegistry.get_by_netuid(netuid)
        if not info:
            return {"ok": False, "error": f"subnet {netuid} not found"}
        base = info.api_endpoint
        if not base and not endpoint_path:
            return {"ok": False, "error": "no API endpoint configured for this subnet"}
        url = f"{base.rstrip('/')}/{endpoint_path.lstrip('/')}" if base else endpoint_path
        
        result = _call_subnet_api(url, method=method, body=body)
        
        # Track query count and calculate fee
        if wallet_id:
            _increment_query_count(wallet_id)
        fee_info = _apply_subnet_query_fee(amount_tao, wallet_id=wallet_id)
        
        if result.get("ok"):
            result["vida_fee"] = fee_info
            result["vida_gateway"] = "powered by Vida Wallet"
            result["note"] = fee_info.get("note", "")
        
        return result
    except Exception as e:
        return {"ok": False, "error": f"subnet query failed: {e}"}


def tao_subnet_info(netuid: int) -> dict[str, Any]:
    """Get detailed info about a specific subnet."""
    try:
        info = SubnetRegistry.get_by_netuid(netuid)
        if not info:
            return {"ok": False, "error": f"subnet {netuid} not found"}
        return {"ok": True, "subnet": info.to_dict()}
    except Exception as e:
        return {"ok": False, "error": f"subnet info failed: {e}"}
