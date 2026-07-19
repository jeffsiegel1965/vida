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
import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

from kaspa import (
    Address,
    NetworkType,
    PrivateKey,
    Resolver,
    RpcClient,
    sompi_to_kaspa,
)

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
            # Quick health check
            await _client.get_block_dag_info()
            return _client
        except Exception:
            await _disconnect()
    
    # Create new connection
    _resolver = Resolver()
    _client = RpcClient(resolver=_resolver)
    
    # Set network
    _client.set_network_id(_network_id)
    
    await _client.connect()
    return _client


async def _disconnect() -> None:
    """Clean up the shared connection."""
    global _client, _resolver
    if _client is not None:
        try:
            await _client.disconnect()
        except Exception:
            pass
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
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
        # Convert hex to bytes and submit
        tx_bytes = bytes.fromhex(tx_hex)
        # SDK expects a dict or Transaction object
        # Use the raw submission endpoint
        result = await client.submit_transaction(transaction=tx_bytes)
        txid = result.get("txid", "") if isinstance(result, dict) else str(result)
        return {"ok": True, "txid": txid}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
