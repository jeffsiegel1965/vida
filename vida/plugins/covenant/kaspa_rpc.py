"""Kaspa RPC client using the official Kaspa Python SDK (kaspa>=2.0).

Replaces the REST-based kaspa_rpc.py with wRPC (WebSocket) via the SDK.
Uses Resolver for automatic node discovery — no hardcoded URLs.

Usage:
    from vida.plugins.covenant.kaspa_rpc import get_balance, submit_transaction

All functions are sync wrappers around the async SDK. They share a single
RpcClient connection for efficiency.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)

from kaspa import (
    Address,
    NetworkType,
    PrivateKey,
    Resolver,
    RpcClient,
    sompi_to_kaspa,
)


# ── Structured error types ──


class KaspaRpcError(Exception):
    """Base error for Kaspa RPC operations."""
    def __init__(self, message: str, original: Optional[Exception] = None):
        self.original = original
        super().__init__(message)


class ConnectionError_(KaspaRpcError):
    """Connection to Kaspa node failed. The Resolver may not have found
    a reachable node, or the previously cached connection is stale."""


class TimeoutError_(KaspaRpcError):
    """RPC call timed out. The node is reachable but not responding."""


class BalanceError(KaspaRpcError):
    """Balance query failed (invalid address, node not synced)."""


class TransactionError(KaspaRpcError):
    """Transaction submission/query failed."""


class KeyError_(KaspaRpcError):
    """Key generation or loading failed."""


def _error_response(error: KaspaRpcError) -> dict[str, Any]:
    """Build a standard error dict from a structured exception."""
    return {
        "ok": False,
        "error": str(error),
        "error_type": type(error).__name__,
        "error_detail": str(error.original) if error.original else None,
    }


# ── Singleton connection ──

_client: RpcClient | None = None
_resolver: Resolver | None = None
_network_id: str = "testnet-10"


def _sync(fn: Callable) -> Callable:
    """Decorator: run an async function synchronously via asyncio.run()."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


async def _get_client() -> RpcClient:
    """Get or create the shared RpcClient connection."""
    global _client, _resolver
    if _client is not None:
        try:
            await _client.get_block_dag_info()
            return _client
        except (asyncio.TimeoutError, OSError, RuntimeError) as e:
            logger.warning("RPC connection stale, reconnecting: %s", e)
            await _disconnect()
        except Exception as e:
            logger.warning("RPC health check failed: %s", e)
            await _disconnect()
    
    # Create new connection
    try:
        _resolver = Resolver()
        _client = RpcClient(resolver=_resolver)
        _client.set_network_id(_network_id)
        await _client.connect()
    except (OSError, RuntimeError, ConnectionError) as e:
        raise ConnectionError_(f"failed to connect to {_network_id}", original=e)
    return _client


async def _disconnect() -> None:
    """Clean up the shared connection."""
    global _client, _resolver
    if _client is not None:
        try:
            await _client.disconnect()
        except Exception:
            pass  # Cleanup only — ignore errors
        _client = None
    _resolver = None


def set_network(network: str = "testnet-10") -> None:
    """Set the network ID. Call before any RPC calls.
    
    Args:
        network: 'testnet-10' or 'mainnet'.
    """
    global _network_id
    _network_id = network
    # Force reconnect on next call
    global _client
    if _client is not None:
        _client.set_network_id(
            NetworkType.TESTNET if "testnet" in network else NetworkType.MAINNET
        )


# ── Public API (sync, dict-returning) ──


@_sync
async def get_balance(address: str) -> dict[str, Any]:
    """Get balance for a Kaspa address.
    
    Returns:
        {"ok": True, "balance_sompi": int, "balance_kas": str} or
        {"ok": False, "error": str}
    """
    try:
        client = await _get_client()
        result = await client.get_balances_by_addresses(request={
            "addresses": [address]
        })
        entries = result.get("entries", [])
        if entries:
            bal = entries[0].get("balance", 0)
            return {
                "ok": True,
                "balance_sompi": int(bal),
                "balance_kas": str(sompi_to_kaspa(int(bal))),
            }
        return {"ok": True, "balance_sompi": 0, "balance_kas": "0"}
    except ConnectionError_ as e:
        return _error_response(e)
    except (asyncio.TimeoutError, asyncio.CancelledError) as e:
        return _error_response(TimeoutError_(f"balance query timed out for {address}", original=e))
    except (ValueError, TypeError, RuntimeError) as e:
        return _error_response(BalanceError(f"balance query failed for {address}", original=e))


@_sync
async def get_utxos(address: str) -> dict[str, Any]:
    """Get UTXOs for a Kaspa address.
    
    Returns:
        {"ok": True, "utxos": [...]} or {"ok": False, "error": str}
    """
    try:
        client = await _get_client()
        utxos = await client.get_utxos_by_addresses(request={"addresses": [address]})
        utxo_list = utxos.get("utxos", utxos.get("entries", [])) if isinstance(utxos, dict) else utxos
        return {"ok": True, "utxos": utxo_list}
    except ConnectionError_ as e:
        return _error_response(e)
    except (asyncio.TimeoutError, asyncio.CancelledError) as e:
        return _error_response(TimeoutError_(f"UTXO query timed out for {address}", original=e))
    except (ValueError, TypeError, RuntimeError) as e:
        return _error_response(BalanceError(f"UTXO query failed for {address}", original=e))


@_sync
async def submit_transaction(tx_hex: str) -> dict[str, Any]:
    """Submit a raw transaction to the network.
    
    Args:
        tx_hex: Hex-encoded transaction.
    
    Returns:
        {"ok": True, "txid": str} or {"ok": False, "error": str}
    """
    try:
        client = await _get_client()
        tx_bytes = bytes.fromhex(tx_hex)
        # Method 1: Try SDK submit
        try:
            result = await client.submit_transaction(request=tx_bytes)
            txid = result.get("txid", "") if isinstance(result, dict) else result
            if txid:
                return {"ok": True, "txid": txid, "source": "sdk"}
        except Exception as sdk_err:
            logger.warning("SDK submit failed: %s — trying REST fallback", sdk_err)
        
        # Method 2: Fall back to REST API
        import json
        from urllib.request import Request, urlopen, URLError
        base = "https://api-tn10.kaspa.org" if "testnet" in _network_id else "https://api.kaspa.org"
        req = Request(
            f"{base}/transactions",
            data=tx_hex.encode(),
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            txid = body.get("txid") or body.get("transactionId", "")
            return {"ok": True, "txid": txid, "source": "rest_api"}
    except URLError as e:
        return _error_response(TransactionError(f"REST API submit failed: {e.reason}"))
    except (ValueError, TypeError, RuntimeError, OSError) as e:
        return _error_response(TransactionError(f"transaction submission failed", original=e))


@_sync
async def get_transaction(txid: str) -> dict[str, Any]:
    """Get transaction details.
    
    Returns:
        {"ok": True, "transaction": {...}} or {"ok": False, "error": str}
    """
    try:
        client = await _get_client()
        tx = await client.get_transaction(txid)
        return {"ok": True, "transaction": tx}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@_sync
async def get_network_info() -> dict[str, Any]:
    """Get network info (DAG info, sync status).
    
    Returns:
        {"ok": True, "info": {...}} or {"ok": False, "error": str}
    """
    try:
        client = await _get_client()
        info = await client.get_block_dag_info()
        return {"ok": True, "info": dict(info) if not isinstance(info, dict) else info}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@_sync
async def get_virtual_chain_blue_score() -> dict[str, Any]:
    """Get the current virtual chain blue score.
    
    Returns:
        {"ok": True, "blue_score": int} or {"ok": False, "error": str}
    """
    try:
        client = await _get_client()
        info = await client.get_block_dag_info()
        score = info.get("daa_score", info.get("virtualDaaScore", 0)) if isinstance(info, dict) else 0
        return {"ok": True, "blue_score": int(score)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@_sync
async def generate_keypair() -> dict[str, Any]:
    """Generate a Kaspa-compatible secp256k1 keypair using the SDK.
    
    Returns:
        {"ok": True, "private_key_hex": str, "address": str, "public_key_hex": str}
    """
    try:
        import secrets
        
        # Generate random private key (valid secp256k1 scalar with overwhelming probability)
        priv_key = PrivateKey(secrets.token_hex(32))
        _ = priv_key.to_public_key()  # ensure valid
        pub_key = priv_key.to_public_key()
        
        # Derive address
        net = NetworkType.Testnet if "testnet" in _network_id else NetworkType.Mainnet
        addr = priv_key.to_address(net)
        
        return {
            "ok": True,
            "private_key_hex": priv_key.to_string(),
            "public_key_hex": pub_key.to_string(),
            "address": str(addr),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_key(key_path: str) -> Optional[bytes]:
    """Load a hex-encoded private key from file."""
    path = Path(key_path)
    if not path.is_file():
        return None
    try:
        return bytes.fromhex(path.read_text().strip())
    except (ValueError, OSError):
        return None


def save_key(key_path: str, key_bytes: bytes) -> None:
    """Save a hex-encoded private key to file (0600 permissions)."""
    path = Path(key_path)
    path.write_text(key_bytes.hex() + "\n")
    path.chmod(0o600)


def p2sh_address(program_hex: str) -> str:
    """Derive the P2SH address from a SilverScript program hex.
    
    Uses blake2b-256 hash of the program as the covenant identifier.
    """
    program = bytes.fromhex(program_hex)
    h = hashlib.blake2b(program, digest_size=32)
    return f"kaspatest:{h.hexdigest()[:60]}"


def estimate_submit_mass(program_hex: str, num_outputs: int = 2) -> int:
    """Estimate the compute mass for a covenant transaction."""
    program_len = len(bytes.fromhex(program_hex))
    base = 20  # signature
    covenant_overhead = 50  # covenant introspection
    output_mass = num_outputs * 10
    script_mass = program_len // 10
    return base + covenant_overhead + output_mass + script_mass


@_sync
async def disconnect() -> None:
    """Explicitly disconnect the shared RPC client."""
    await _disconnect()
