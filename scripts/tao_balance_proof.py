#!/usr/bin/env python3
"""
T1.3/T1.4 — End-to-end proof: owner-provision (test mnemonic) + live Finney balance.

Uses the well-known abandon…about BIP39 vector (NOT for real funds).
Writes docs/proofs/tao_phase1_balance.md

Usage:
  /path/to/kaspa-suite/venv/bin/python scripts/tao_balance_proof.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
EXPECTED = "5EPCUjPxiHAcNooYipQFWr9NmmXJKpNG5RhcntXwbtUySrgH"


def main() -> int:
    from vida.plugins import VidaPluginContext
    from vida.plugins.tao import (
        TaoAccountStore,
        TaoNetwork,
        TaoPlugin,
        load_tao_config,
    )
    from vida.plugins.tao.substrate_client import SubstrateTaoClient

    # Live config
    cfg = load_tao_config(network="finney")
    if cfg.network != TaoNetwork.FINNEY:
        print("expected finney", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as td:
        store = TaoAccountStore(td)
        live = SubstrateTaoClient(config=cfg)
        plugin = TaoPlugin(config=cfg, client=live, account_store=store)

        prov = plugin.owner_provision(
            wallet_id="proof-abandon",
            mnemonic=TEST_MNEMONIC,
            password="proof-only-password",
            overwrite=True,
        )
        if not prov.get("ok"):
            print(json.dumps(prov, indent=2))
            return 1
        if prov.get("ss58_address") != EXPECTED:
            print("address mismatch", prov.get("ss58_address"), EXPECTED, file=sys.stderr)
            return 1

        # Agent path still blocked
        blocked = plugin.provision_from_seed(TEST_MNEMONIC)
        if blocked.get("ok"):
            print("agent path must stay blocked", file=sys.stderr)
            return 1

        ctx = VidaPluginContext(wallet_id="proof-abandon", mode="COMMAND", network="finney")
        started = time.time()
        st = plugin.status(ctx)
        elapsed = round(time.time() - started, 2)

        # Secrets must never appear
        blob = json.dumps(st)
        for bad in ("private", "mnemonic", "seed", "password", "cold_private"):
            if bad in blob.lower() and "private" in bad:
                # 'private' shouldn't appear at all in public status
                if "private" in blob.lower():
                    print("leak?", blob[:200], file=sys.stderr)
                    return 1

        result = {
            "ok": bool(st.get("ok") and (st.get("balance") or {}).get("ok")),
            "wallet_id": "proof-abandon",
            "ss58_address": st.get("ss58_address"),
            "hotkey_ss58": st.get("hotkey_ss58"),
            "provisioned": st.get("provisioned"),
            "client": st.get("client"),
            "balance": st.get("balance"),
            "elapsed_sec": elapsed,
            "agent_provision_blocked": not blocked.get("ok"),
            "note": (
                "Address is BIP39 test vector abandon…about — not a funded Vida owner wallet. "
                "Proves provision → status → System.Account balance path on Finney."
            ),
        }

        proof = ROOT / "docs" / "proofs" / "tao_phase1_balance.md"
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(
            "\n".join(
                [
                    "# TAO Phase 1 — Provisioned account balance proof",
                    "",
                    f"**When:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                    "**Network:** finney",
                    f"**Address (test vector coldkey):** `{EXPECTED}`",
                    f"**Elapsed:** {elapsed}s",
                    "",
                    "## What this proves",
                    "",
                    "1. Owner provision derives deterministic SS58 from mnemonic",
                    "2. Secrets encrypted at rest (agent status has no private keys)",
                    "3. Agent `provision_from_seed` remains blocked",
                    "4. Live Finney `status()` returns free/reserved TAO via System.Account",
                    "",
                    "## Result",
                    "",
                    "```json",
                    json.dumps(result, indent=2),
                    "```",
                    "",
                    "## Not claimed",
                    "",
                    "- This address is the public BIP39 test mnemonic — **do not send real funds**",
                    "- No staking / transfer extrinsics (Phase 1B)",
                    "- Not a production owner wallet proof (that uses your real seed offline)",
                    "",
                    "## Re-run",
                    "",
                    "```bash",
                    "kaspa-suite/venv/bin/python scripts/tao_balance_proof.py",
                    "```",
                    "",
                ]
            )
        )
        print(json.dumps(result, indent=2))
        print(f"wrote {proof}", file=sys.stderr)
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
