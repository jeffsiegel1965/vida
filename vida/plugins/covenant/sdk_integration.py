"""Covenant deploy and spend using the Kaspa SDK (kaspa>=2.0).

No kascov-lab dependency. Uses the official Kaspa Python SDK for:
- Transaction building (TransactionInput with compute_budget)
- Covenant binding (CovenantBinding, GenesisCovenantGroup)
- Signing (sign_transaction)
- Submission (RpcClient.submit_transaction)

Usage:
    from vida.plugins.covenant.sdk_integration import deploy_covenant, spend_from_covenant, covenant_balance
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any

from kaspa import (
    Address,
    CovenantBinding,
    GenesisCovenantGroup,
    Hash,
    NetworkType,
    PrivateKey,
    Resolver,
    RpcClient,
    ScriptBuilder,
    ScriptPublicKey,
    Transaction,
    TransactionInput,
    TransactionOutpoint,
    TransactionOutput,
    UtxoEntryReference,
    calculate_transaction_mass,
    sign_transaction,
)

# Default: use Resolver for auto-discovery (no hardcoded URLs)
USE_RESOLVER = True

# Covenant transaction constants (from official SDK examples)
TX_VERSION = 1                          # v1 for covenant transactions
COMPUTE_BUDGET = 10                     # compute budget for covenant introspection
SUBNETWORK_ID = bytes(20)              # zero subnetwork (main/payment network)
FEE_MARGIN = 1.1                        # 10% headroom on fee estimates


@dataclass
class CovenantDeployResult:
    ok: bool
    covenant_id: str = ""
    txid: str = ""
    address: str = ""
    value_sompi: int = 0
    error: str = ""


@dataclass
class CovenantSpendResult:
    ok: bool
    txid: str = ""
    change_covenant_id: str = ""
    payment_amount: int = 0
    fee_sompi: int = 0
    error: str = ""


def program_to_covenant_id(program_hex: str) -> str:
    """Derive the covenant ID from a SilverScript program hex.

    Covenant ID = blake2b-256(program_bytes)
    This is what kascov uses as the covenant identifier.
    """
    program = bytes.fromhex(program_hex)
    return hashlib.blake2b(program, digest_size=32).hexdigest()


def _build_covenant_spk(program_hex: str) -> ScriptPublicKey:
    """Build a P2SH script public key for a covenant program.

    Uses ScriptBuilder with covenants_enabled=True, then creates
    a P2SH (pay-to-script-hash) locking script.
    """
    program = bytes.fromhex(program_hex)
    return (
        ScriptBuilder.from_script(program, covenants_enabled=True)
        .create_pay_to_script_hash_script()
    )


def _make_utxo_entry(entry: dict) -> UtxoEntryReference:
    """Convert a raw UTXO dict from the RPC into a UtxoEntryReference."""
    return UtxoEntryReference.from_dict(entry)


async def _estimate_fee(
    client: RpcClient,
    inputs: list[TransactionInput],
    outputs: list[TransactionOutput],
    network_id: str,
) -> int:
    """Calculate the fee for a transaction draft.

    Builds a draft tx, measures mass, fetches fee rate, returns fee.
    """
    draft = Transaction(
        TX_VERSION,
        inputs,
        outputs,
        lock_time=0,
        subnetwork_id=SUBNETWORK_ID,
        gas=0,
        payload=b"",
        mass=0,
    )
    mass = calculate_transaction_mass(network_id, draft)
    estimate = await client.get_fee_estimate()
    feerate = int(estimate["estimate"]["priorityBucket"]["feerate"])
    fee = int(mass * feerate * FEE_MARGIN)
    return max(fee, 10_000)  # minimum 0.0001 KAS


async def deploy_covenant(
    program_hex: str,
    private_key_hex: str,
    value_sompi: int = 100_000_000,  # 1 KAS
    network: str = "testnet-10",
    wrpc_url: str = "",
    key_address: str = "",
) -> CovenantDeployResult:
    """Deploy a SilverScript covenant to the Kaspa network.

    Uses the official SDK pattern from examples/silverscript/counter.py:
    - TransactionInput with compute_budget=10
    - GenesisCovenantGroup for covenant genesis
    - TX_VERSION = 1 for covenant transactions

    Args:
        program_hex: Compiled SilverScript program as hex string.
        private_key_hex: Deployer's private key (hex).
        value_sompi: Amount to fund the covenant with (in sompi).
        network: 'testnet-10' or 'mainnet'.
        wrpc_url: Optional — override Resolver with specific URL.
        key_address: Optional — derived from private key if not provided.
    """
    priv_key = PrivateKey(private_key_hex)
    net = NetworkType.Testnet if "testnet" in network else NetworkType.Mainnet

    if not key_address:
        key_address = str(priv_key.to_address(net))

    rpc = RpcClient(resolver=Resolver()) if not wrpc_url else RpcClient()
    rpc.set_network_id(network)

    try:
        await rpc.connect()

        # Get UTXOs for funding address
        utxos = await rpc.get_utxos_by_addresses(request={"addresses": [key_address]})
        entries = utxos.get("entries", utxos.get("utxos", [])) if isinstance(utxos, dict) else utxos
        if not entries:
            return CovenantDeployResult(ok=False, error="no UTXOs available")

        # Use the largest UTXO as funding source
        fund = max(entries, key=lambda e: e["utxoEntry"]["amount"] if isinstance(e, dict) else e.amount)
        fund["utxoEntry"]["amount"] if isinstance(fund, dict) else fund.amount
        fund_outpoint_dict = fund["outpoint"] if isinstance(fund, dict) else {"transactionId": fund.outpoint.transaction_id, "index": fund.outpoint.index}

        # Build covenant P2SH locking script
        covenant_spk = _build_covenant_spk(program_hex)

        # Build the funding input
        fund_input = TransactionInput(
            TransactionOutpoint(
                Hash(fund_outpoint_dict["transactionId"]),
                fund_outpoint_dict["index"],
            ),
            b"",  # empty sig script (will be signed)
            sequence=0,
            sig_op_count=0,
            compute_budget=COMPUTE_BUDGET,
            utxo=_make_utxo_entry(fund),
        )

        # Build covenant output (unbound — genesis will set covenant id)
        covenant_output = TransactionOutput(value_sompi, covenant_spk)

        # Estimate fee
        fee = await _estimate_fee(rpc, [fund_input], [covenant_output], network)
        covenant_output = TransactionOutput(value_sompi - fee, covenant_spk)

        # Build transaction
        tx = Transaction(
            TX_VERSION,
            [fund_input],
            [covenant_output],
            lock_time=0,
            subnetwork_id=SUBNETWORK_ID,
            gas=0,
            payload=b"",
            mass=0,
        )

        # Populate genesis covenant binding
        tx.populate_genesis_covenants(
            [GenesisCovenantGroup(authorizing_input=0, outputs=[0])]
        )

        # Set mass after covenant binding
        tx.mass = calculate_transaction_mass(network, tx)

        # Sign the funding input (P2PK)
        signed = sign_transaction(tx, [priv_key], True)

        # Submit
        result = await rpc.submit_transaction(request=signed)
        txid = result.get("transactionId", "") if isinstance(result, dict) else str(result)

        covenant_id = program_to_covenant_id(program_hex)

        return CovenantDeployResult(
            ok=True,
            covenant_id=covenant_id,
            txid=str(txid),
            address=key_address,
            value_sompi=value_sompi - fee,
        )

    except Exception as e:
        return CovenantDeployResult(ok=False, error=str(e))
    finally:
        await rpc.disconnect()


async def spend_from_covenant(
    program_hex: str,
    covenant_id: str,
    private_key_hex: str,
    entrypoint: str = "withdraw",
    to_address: str = "",
    amount_sompi: int = 10_000_000,  # 0.1 KAS
    network: str = "testnet-10",
    wrpc_url: str = "",
) -> CovenantSpendResult:
    """Spend from a deployed covenant.

    Uses the official SDK pattern from examples/silverscript/counter.py:
    - TransactionInput with compute_budget=10
    - CovenantBinding with covenant_id for output binding
    - TX_VERSION = 1 for covenant transactions

    Args:
        program_hex: The covenant's compiled program hex.
        covenant_id: The covenant ID to spend from.
        private_key_hex: Owner's private key for authorization.
        entrypoint: Which entrypoint to call ('withdraw' or 'burn').
        to_address: Where to send the payment.
        amount_sompi: Amount to pay out.
        network: 'testnet-10' or 'mainnet'.
    """
    if not to_address:
        return CovenantSpendResult(ok=False, error="to_address required for spend")

    priv_key = PrivateKey(private_key_hex)
    net = NetworkType.Testnet if "testnet" in network else NetworkType.Mainnet
    owner_address = str(priv_key.to_address(net))

    rpc = RpcClient(resolver=Resolver()) if not wrpc_url else RpcClient()
    rpc.set_network_id(network)

    try:
        await rpc.connect()

        # Get UTXOs for the owner address
        utxos = await rpc.get_utxos_by_addresses(request={"addresses": [owner_address]})
        entries = utxos.get("entries", utxos.get("utxos", [])) if isinstance(utxos, dict) else utxos

        if not entries:
            return CovenantSpendResult(ok=False, error="no covenant UTXO found")

        # Find the covenant UTXO (the one with our covenant P2SH script)
        covenant_spk = _build_covenant_spk(program_hex)
        covenant_spk_bytes = bytes(covenant_spk)

        cov_entry = None
        for e in entries:
            spk = e.get("utxoEntry", e).get("scriptPublicKey", {})
            spk_bytes = spk.get("script", b"") if isinstance(spk, dict) else getattr(spk, "script", b"")
            if spk_bytes == covenant_spk_bytes:
                cov_entry = e
                break

        if not cov_entry:
            # Fallback: use the first UTXO with a covenant id
            for e in entries:
                utxo = e.get("utxoEntry", e)
                cov_id = utxo.get("covenantId") if isinstance(utxo, dict) else getattr(utxo, "covenant_id", None)
                if cov_id:
                    cov_entry = e
                    break

        if not cov_entry:
            return CovenantSpendResult(ok=False, error="no covenant UTXO found")

        cov_amount = cov_entry["utxoEntry"]["amount"] if isinstance(cov_entry, dict) else cov_entry.amount
        cov_outpoint_dict = cov_entry["outpoint"] if isinstance(cov_entry, dict) else {
            "transactionId": cov_entry.outpoint.transaction_id,
            "index": cov_entry.outpoint.index,
        }

        # Build covenant spend input
        spend_input = TransactionInput(
            TransactionOutpoint(
                Hash(cov_outpoint_dict["transactionId"]),
                cov_outpoint_dict["index"],
            ),
            b"",  # sig script — filled by covenant entrypoint
            sequence=0,
            sig_op_count=0,
            compute_budget=COMPUTE_BUDGET,
            utxo=_make_utxo_entry(cov_entry),
        )

        # Build outputs:
        # Output 0: covenant continuation (self-replication with remaining funds)
        # Output 1: payment to recipient
        remaining = cov_amount - amount_sompi

        covenant_binding = CovenantBinding(
            authorizing_input=0,
            covenant_id=Hash(covenant_id),
        )

        change_output = TransactionOutput(
            remaining,
            covenant_spk,
            covenant_binding,
        )
        payment_output = TransactionOutput(
            amount_sompi,
            ScriptBuilder.from_address(Address(to_address)).create_pay_to_script_hash_script(),
        )

        # Estimate fee
        fee = await _estimate_fee(rpc, [spend_input], [change_output, payment_output], network)

        # Rebuild outputs with fee deducted from change
        change_output = TransactionOutput(
            remaining - fee,
            covenant_spk,
            covenant_binding,
        )

        # Build transaction
        tx = Transaction(
            TX_VERSION,
            [spend_input],
            [change_output, payment_output],
            lock_time=0,
            subnetwork_id=SUBNETWORK_ID,
            gas=0,
            payload=b"",
            mass=0,
        )

        # Set mass
        tx.mass = calculate_transaction_mass(network, tx)

        # Sign
        signed = sign_transaction(tx, [priv_key], True)

        # Submit
        result = await rpc.submit_transaction(request=signed)
        txid = result.get("transactionId", "") if isinstance(result, dict) else str(result)

        return CovenantSpendResult(
            ok=True,
            txid=str(txid),
            change_covenant_id=covenant_id,
            payment_amount=amount_sompi,
            fee_sompi=fee,
        )

    except Exception as e:
        return CovenantSpendResult(ok=False, error=str(e))
    finally:
        await rpc.disconnect()


async def covenant_balance(
    covenant_id: str,
    network: str = "testnet-10",
    wrpc_url: str = "",
) -> dict[str, Any]:
    """Check the balance of a covenant via kascov explorer.

    Falls back to kaspa_rpc.py for REST API queries.
    """
    try:
        import json
        import urllib.request

        base = f"https://kascov.io/data/{network}/c/{covenant_id}.json"
        req = urllib.request.Request(base, headers={"accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.load(res)

        balance = data.get("balance", data.get("amount", 0))
        return {"ok": True, "covenant_id": covenant_id, "balance_sompi": int(balance)}
    except Exception as e:
        return {"ok": False, "covenant_id": covenant_id, "error": str(e)}


# ── Sync convenience wrappers ──


def deploy(
    program_hex: str,
    private_key_hex: str,
    value_sompi: int = 100_000_000,
    network: str = "testnet-10",
    wrpc_url: str = "",
) -> CovenantDeployResult:
    """Sync wrapper for deploy_covenant."""
    return asyncio.run(
        deploy_covenant(
            program_hex=program_hex,
            private_key_hex=private_key_hex,
            value_sompi=value_sompi,
            network=network,
            wrpc_url=wrpc_url,
        )
    )


def spend(
    program_hex: str,
    covenant_id: str,
    private_key_hex: str,
    entrypoint: str = "withdraw",
    to_address: str = "",
    amount_sompi: int = 10_000_000,
    network: str = "testnet-10",
    wrpc_url: str = "",
) -> CovenantSpendResult:
    """Sync wrapper for spend_from_covenant."""
    return asyncio.run(
        spend_from_covenant(
            program_hex=program_hex,
            covenant_id=covenant_id,
            private_key_hex=private_key_hex,
            entrypoint=entrypoint,
            to_address=to_address,
            amount_sompi=amount_sompi,
            network=network,
            wrpc_url=wrpc_url,
        )
    )
