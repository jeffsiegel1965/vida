"""
Vida Transactions - Build, sign, and broadcast real Kaspa transactions.

Uses the official kaspa Python SDK (rusty-kaspa bindings):
  - RpcClient + Resolver for node discovery (public nodes, no local node needed)
  - create_transaction / sign_transaction for correct wire format
  - submit_transaction for broadcast
  - Post-broadcast verification: confirms the tx is actually known to the network

Design rules:
  - All amounts validated (> 0, above dust threshold)
  - UTXO selection: smallest-first to avoid Kaspa storage-mass rejections
  - Policy gate: session-key spends go through Vida.sign-policy (can_sign)
    before the cold key ever touches the transaction
  - Never trust "submitted" alone: we re-query the network for the txid
"""

import asyncio
from dataclasses import dataclass
from typing import List, Optional

from kaspa import (
    Resolver,
    RpcClient,
    PrivateKey,
    Address,
    create_transaction,
    sign_transaction,
    calculate_transaction_mass,
    kaspa_to_sompi,
    sompi_to_kaspa,
)

try:
    import aiohttp
except ImportError:
    aiohttp = None

from wallet import Vida, DelegationMode

# Kaspa dust threshold: outputs below ~0.02 KAS incur massive storage-mass
# penalties and get rejected (verified on testnet-10, July 2026).
DUST_THRESHOLD_KAS = 0.02

# Keep total output value conservative to stay under the 500K storage-mass cap
# when spending large UTXOs (see kaspa-transaction-format-requirements skill).
# Kaspa standard-tx relay rule: fee must be >= mass * 100 sompi/gram
# (verified empirically on testnet-10: "10000 fees ... under the required
#  amount of 539000 for compute mass 5390" => 100 sompi per mass unit)
FEE_RATE_SOMPI_PER_MASS = 100
FEE_SAFETY_MARGIN = 1.1  # 10% headroom over the minimum

DEFAULT_PRIORITY_FEE_SOMPI = 10_000  # floor; real fee computed from mass


@dataclass
class SendResult:
    """Result of a send attempt."""
    success: bool
    txid: Optional[str] = None
    amount_kas: float = 0.0
    to_address: str = ""
    fee_kas: float = 0.0
    error: Optional[str] = None
    verified_on_network: bool = False
    network: str = "mainnet"

    @property
    def explorer_url(self) -> str:
        if not self.txid:
            return ""
        if self.network == "mainnet":
            return f"https://explorer.kaspa.org/txs/{self.txid}"
        return f"https://explorer-tn10.kaspa.org/txs/{self.txid}"


class VidaTransactor:
    """
    Transaction engine for a Vida wallet.

    Usage:
        vida = Vida('wallet.json', network='mainnet')
        tx = VidaTransactor(vida)
        balance = await tx.get_balance()
        result = await tx.send(to_address='kaspa:...', amount_kas=10.0)
    """

    def __init__(self, vida: Vida):
        self.vida = vida
        self.network = "mainnet" if vida.network == "mainnet" else "testnet-10"
        self._client: Optional[RpcClient] = None

    # ── Connection ────────────────────────────────────────────────────────

    async def connect(self) -> RpcClient:
        """Connect to a public Kaspa node via the resolver."""
        if self._client and self._client.is_connected:
            return self._client
        client = RpcClient(resolver=Resolver(), network_id=self.network)
        await client.connect()
        self._client = client
        return client

    async def disconnect(self):
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None

    # ── Read operations ───────────────────────────────────────────────────

    async def get_balance(self) -> float:
        """Return confirmed balance in KAS."""
        client = await self.connect()
        resp = await client.get_balance_by_address({"address": self.vida.address})
        return sompi_to_kaspa(int(resp["balance"]))

    async def get_utxos(self) -> List[dict]:
        """Fetch spendable UTXOs for the wallet address."""
        client = await self.connect()
        resp = await client.get_utxos_by_addresses({"addresses": [self.vida.address]})
        return resp.get("entries", [])

    # ── UTXO selection ────────────────────────────────────────────────────

    @staticmethod
    def select_utxos(entries: List[dict], target_sompi: int) -> List[dict]:
        """
        Smallest-first UTXO selection.

        Why smallest-first: Kaspa's storage-mass rule punishes transactions
        whose outputs are much smaller than inputs. Consuming small UTXOs
        first keeps the change output proportionate, avoids mass rejections,
        and consolidates dust over time.

        Raises ValueError if funds are insufficient.
        """
        def amount_of(e: dict) -> int:
            return int(e["utxoEntry"]["amount"]) if "utxoEntry" in e else int(e["amount"])

        ordered = sorted(entries, key=amount_of)
        selected, total = [], 0
        for entry in ordered:
            selected.append(entry)
            total += amount_of(entry)
            if total >= target_sompi:
                return selected
        raise ValueError(
            f"Insufficient funds: have {sompi_to_kaspa(total)} KAS, "
            f"need {sompi_to_kaspa(target_sompi)} KAS"
        )

    # ── Send ──────────────────────────────────────────────────────────────

    async def send(
        self,
        to_address: str,
        amount_kas: float,
        session_pubkey: Optional[str] = None,
        priority_fee_sompi: int = DEFAULT_PRIORITY_FEE_SOMPI,
    ) -> SendResult:
        """
        Build, sign, broadcast, and verify a KAS transfer.

        Args:
            to_address: Destination kaspa:/kaspatest: address
            amount_kas: Amount to send in KAS
            session_pubkey: If provided, the spend must pass this session
                key's delegation policy (FULL/COMMAND/HYBRID) before the
                cold key signs. If omitted, this is a direct owner spend.
            priority_fee_sompi: Priority fee (default 0.0001 KAS)

        Returns:
            SendResult with txid + network verification status
        """
        # ── Validation gates ──
        import math
        if not isinstance(amount_kas, (int, float)) or not math.isfinite(amount_kas):
            return SendResult(success=False, error="Amount must be a finite number")
        if amount_kas <= 0:
            return SendResult(success=False, error="Amount must be positive")
        if amount_kas < DUST_THRESHOLD_KAS:
            return SendResult(
                success=False,
                error=f"Amount {amount_kas} KAS below dust threshold ({DUST_THRESHOLD_KAS} KAS)",
            )
        expected_prefix = "kaspa:" if self.network == "mainnet" else "kaspatest:"
        if not to_address.startswith(expected_prefix):
            return SendResult(
                success=False,
                error=f"Address prefix mismatch: expected {expected_prefix} on {self.network}",
            )
        # Full bech32 checksum validation — catches typo'd-but-prefixed addresses
        # so funds can't be sent to an unspendable address (TX-5).
        try:
            Address(to_address)
        except Exception:
            return SendResult(
                success=False,
                error="Invalid address (bech32 checksum failed) — refusing to send",
            )

        # ── Policy gate (session-key delegated spends) ──
        if session_pubkey is not None:
            session = self.vida._session_keys.get(session_pubkey)
            if session is None:
                return SendResult(success=False, error="Unknown session key")
            if not session.can_sign(amount_kas):
                return SendResult(
                    success=False,
                    error=(
                        f"Policy rejected: mode={session.mode.value}, "
                        f"amount={amount_kas} KAS, active={session.is_active}"
                    ),
                )

        try:
            client = await self.connect()

            # ── Gather + select UTXOs ──
            entries = await self.get_utxos()
            if not entries:
                return SendResult(success=False, error="No UTXOs available (zero balance?)")

            amount_sompi = kaspa_to_sompi(amount_kas)
            # Reserve generous headroom for fees when selecting (0.01 KAS)
            selected = self.select_utxos(entries, amount_sompi + kaspa_to_sompi(0.01))

            def amount_of(e: dict) -> int:
                return int(e["utxoEntry"]["amount"]) if "utxoEntry" in e else int(e["amount"])

            total_in = sum(amount_of(e) for e in selected)

            def build(fee_sompi: int):
                outs = [{"address": to_address, "amount": amount_sompi}]
                change = total_in - amount_sompi - fee_sompi
                if change > kaspa_to_sompi(DUST_THRESHOLD_KAS):
                    outs.append({"address": self.vida.address, "amount": change})
                # If change would be dust it is forfeited to fee (standard practice)
                return outs, create_transaction(
                    utxo_entry_source=selected,
                    outputs=outs,
                    priority_fee=fee_sompi,
                )

            # ── Pass 1: draft with floor fee to measure mass ──
            outputs, draft = build(priority_fee_sompi)
            network_id = "mainnet" if self.network == "mainnet" else "testnet-10"
            mass = calculate_transaction_mass(network_id, draft)

            # ── Fee = mass * rate * margin (Kaspa standard relay minimum) ──
            required_fee = int(mass * FEE_RATE_SOMPI_PER_MASS * FEE_SAFETY_MARGIN)
            fee_sompi = max(required_fee, priority_fee_sompi)

            # Guard: fee must not swallow the send amount (TX-6)
            if fee_sompi >= amount_sompi:
                return SendResult(
                    success=False,
                    error=(
                        f"Fee ({sompi_to_kaspa(fee_sompi)} KAS) >= amount "
                        f"({amount_kas} KAS). Send a larger amount."
                    ),
                )
            if total_in < amount_sompi + fee_sompi:
                return SendResult(success=False, error="Insufficient funds after fee")

            # ── Pass 2: rebuild with the correct fee ──
            outputs, tx = build(fee_sompi)

            # ── Sign with the cold key ──
            priv = PrivateKey(self.vida._private_key_hex)
            signed = sign_transaction(tx, [priv], True)

            # ── Broadcast ──
            resp = await client.submit_transaction({"transaction": signed, "allowOrphan": False})
            txid = resp.get("transactionId") or resp.get("transaction_id")
            if not txid:
                return SendResult(success=False, error=f"No txid in submit response: {resp}")

            # ── Record spend against session daily limit ──
            if session_pubkey is not None:
                self.vida._session_keys[session_pubkey].record_spend(amount_kas)

            # ── Verify: best-effort ONLY. The broadcast already succeeded above;
            #    a verification error must NEVER flip success to False, or the
            #    caller retries and double-spends (TX-1). ──
            try:
                verified = await self._verify_txid(txid)
            except Exception:
                verified = False

            fee_kas = sompi_to_kaspa(total_in - sum(o["amount"] for o in outputs))
            return SendResult(
                success=True,
                txid=txid,
                amount_kas=amount_kas,
                to_address=to_address,
                fee_kas=fee_kas,
                verified_on_network=verified,
                network=self.network,
            )

        except Exception as e:
            return SendResult(success=False, error=f"{type(e).__name__}: {e}")

    async def _verify_txid(self, txid: str, attempts: int = 15, delay_s: float = 2.0) -> bool:
        """
        Best-effort confirmation that the network accepted the transaction, by
        polling the indexer for the txid. Returns True if seen, False otherwise.
        A False result does NOT mean the tx failed (indexer lag is common) —
        the caller treats this as advisory only.

        Uses aiohttp if available, else the stdlib (urllib) in an executor so
        the wallet works with zero extra dependencies.
        """
        api_base = (
            "https://api.kaspa.org"
            if self.network == "mainnet"
            else "https://api-tn10.kaspa.org"
        )
        url = f"{api_base}/transactions/{txid}"

        if aiohttp is not None:
            async with aiohttp.ClientSession() as session:
                for _ in range(attempts):
                    try:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                return True
                    except Exception:
                        pass
                    await asyncio.sleep(delay_s)
            return False

        # Stdlib fallback — no third-party dependency required
        import urllib.request

        def _probe() -> bool:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "vida-wallet"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.status == 200
            except Exception:
                return False

        loop = asyncio.get_event_loop()
        for _ in range(attempts):
            if await loop.run_in_executor(None, _probe):
                return True
            await asyncio.sleep(delay_s)
        return False


# ── CLI helpers for quick manual use ─────────────────────────────────────────

async def _balance_cmd(wallet_path: str, network: str):
    vida = Vida(wallet_path, network=network)
    tx = VidaTransactor(vida)
    bal = await tx.get_balance()
    utxos = await tx.get_utxos()
    print(f"Address: {vida.address}")
    print(f"Balance: {bal} KAS ({len(utxos)} UTXOs)")
    await tx.disconnect()


async def _send_cmd(wallet_path: str, network: str, to_address: str, amount: float):
    vida = Vida(wallet_path, network=network)
    tx = VidaTransactor(vida)
    print(f"Sending {amount} KAS -> {to_address}")
    result = await tx.send(to_address=to_address, amount_kas=amount)
    if result.success:
        print(f"✔ txid: {result.txid}")
        print(f"  fee:  {result.fee_kas} KAS")
        print(f"  verified on network: {result.verified_on_network}")
        print(f"  explorer: {result.explorer_url}")
    else:
        print(f"✘ FAILED: {result.error}")
    await tx.disconnect()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage:")
        print("  python transactions.py balance <wallet.json> <mainnet|testnet>")
        print("  python transactions.py send <wallet.json> <mainnet|testnet> <to_address> <amount_kas>")
        sys.exit(1)

    cmd, wallet_path, network = sys.argv[1], sys.argv[2], sys.argv[3]
    if cmd == "balance":
        asyncio.run(_balance_cmd(wallet_path, network))
    elif cmd == "send":
        asyncio.run(_send_cmd(wallet_path, network, sys.argv[4], float(sys.argv[5])))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
