#!/usr/bin/env python3
"""
Live Finney E2E test for Vida TAO plugin.

Does NOT print the full mnemonic to stdout by default (writes 0600 file).
Stake only runs if free balance >= min and --stake is passed.

Usage:
  # Full live path without stake (health + new wallet + balance):
  kaspa-suite/venv/bin/python scripts/tao_live_e2e.py

  # After you fund the printed address:
  export VIDA_TAO_MNEMONIC_FILE=./data/tao_live_e2e/mnemonic.txt
  export VIDA_TAO_PASSWORD='your-password'
  kaspa-suite/venv/bin/python scripts/tao_live_e2e.py --reuse --stake --netuid 1 --amount 0.01

  # Or fund first then one-shot with existing mnemonic file:
  ...
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DIR = ROOT / "data" / "tao_live_e2e"


def _write_secret(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", default="finney")
    ap.add_argument("--workdir", default=str(DEFAULT_DIR))
    ap.add_argument("--wallet-id", default="live-e2e")
    ap.add_argument("--reuse", action="store_true", help="reuse mnemonic/account in workdir")
    ap.add_argument("--stake", action="store_true", help="attempt tiny delegate if funded")
    ap.add_argument("--netuid", type=int, default=1)
    ap.add_argument("--amount", type=float, default=0.01)
    ap.add_argument("--hotkey", default="", help="validator hotkey ss58 (required for real stake)")
    ap.add_argument("--min-balance", type=float, default=0.02, help="min free TAO to attempt stake")
    ap.add_argument("--write-proof", action="store_true")
    args = ap.parse_args()

    from mnemonic import Mnemonic

    from vida.plugins import VidaPluginContext
    from vida.plugins.tao import (
        TaoAccountStore,
        TaoPlugin,
        load_tao_config,
    )
    from vida.plugins.tao.substrate_client import SubstrateTaoClient

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, stat.S_IRWXU)
    store_dir = work / "accounts"
    mnemonic_path = work / "mnemonic.txt"
    password_path = work / "password.txt"  # local e2e only; 0600

    report: dict = {
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "network": args.network,
        "steps": [],
    }

    def step(name: str, ok: bool, **extra):
        entry = {"step": name, "ok": ok, **extra}
        report["steps"].append(entry)
        print(json.dumps(entry))
        return ok

    # --- 1. Live health ---
    cfg = load_tao_config(network=args.network)
    client = SubstrateTaoClient(config=cfg)
    try:
        client.connect()
        health = client.health()
        step(
            "health",
            health.ok,
            endpoint=health.endpoint,
            chain=health.chain_name,
            block=health.block_number,
            error=health.error,
        )
        if not health.ok:
            return 1
    except Exception as e:
        step("health", False, error=f"{type(e).__name__}: {e}")
        return 1

    # --- 2. Mnemonic (owner material on disk only) ---
    password = os.environ.get("VIDA_TAO_PASSWORD")
    if args.reuse and mnemonic_path.is_file():
        mnemonic = mnemonic_path.read_text().strip()
        if not password and password_path.is_file():
            password = password_path.read_text().strip()
        step("mnemonic", True, source="reuse_file", path=str(mnemonic_path))
    else:
        env_file = os.environ.get("VIDA_TAO_MNEMONIC_FILE")
        env_mn = os.environ.get("VIDA_TAO_MNEMONIC")
        if env_file:
            mnemonic = Path(env_file).read_text().strip()
            step("mnemonic", True, source="env_file")
        elif env_mn:
            mnemonic = env_mn.strip()
            step("mnemonic", True, source="env")
        else:
            mnemonic = Mnemonic("english").generate(strength=256)  # 24 words
            _write_secret(mnemonic_path, mnemonic + "\n")
            step(
                "mnemonic",
                True,
                source="generated",
                path=str(mnemonic_path),
                note="24-word mnemonic written 0600 — NOT printed here",
            )
        if not password:
            # generate e2e password stored local only
            password = os.urandom(16).hex()
            _write_secret(password_path, password + "\n")
            step("password", True, source="generated_local_0600", path=str(password_path))
        elif not password_path.is_file():
            _write_secret(password_path, password + "\n")

    if not password:
        step("password", False, error="VIDA_TAO_PASSWORD required or generate path failed")
        return 1

    # --- 3. Owner provision ---
    store = TaoAccountStore(store_dir)
    plugin = TaoPlugin(config=cfg, client=client, account_store=store)
    prov = plugin.owner_provision(
        wallet_id=args.wallet_id,
        mnemonic=mnemonic,
        password=password,
        overwrite=True,
    )
    step(
        "provision",
        bool(prov.get("ok")),
        ss58_address=prov.get("ss58_address"),
        hotkey_ss58=prov.get("hotkey_ss58"),
        error=prov.get("error"),
    )
    if not prov.get("ok"):
        return 1

    addr = prov["ss58_address"]
    hot = prov.get("hotkey_ss58") or ""

    # Agent path still blocked
    blocked = plugin.provision_from_seed("should not work")
    step("agent_provision_blocked", not blocked.get("ok"), error=blocked.get("error"))

    # --- 4. Live balance via status ---
    # Fresh client after previous close inside status
    plugin2 = TaoPlugin(
        config=cfg,
        client=SubstrateTaoClient(config=cfg),
        account_store=store,
    )
    ctx = VidaPluginContext(
        wallet_id=args.wallet_id,
        mode="FULL",
        network=args.network,
        max_per_tx=1.0,
        daily_limit=1.0,
        allowed_subnets=[args.netuid],
        allowed_actions=["delegate", "undelegate"],
    )
    st = plugin2.status(ctx)
    bal = st.get("balance") or {}
    free_s = bal.get("free_tao") or "0"
    try:
        free = Decimal(str(free_s))
    except Exception:
        free = Decimal("0")
    step(
        "balance",
        bool(bal.get("ok")),
        ss58_address=addr,
        free_tao=str(free),
        reserved_tao=str(bal.get("reserved_tao")),
        block=(st.get("client") or {}).get("block_number"),
        error=bal.get("error"),
    )

    # --- 5. Stake (only if funded + requested) ---
    stake_result = None
    if not args.stake:
        step(
            "stake",
            True,
            skipped=True,
            reason="pass --stake to attempt (requires funds + hotkey)",
            fund_address=addr,
            fund_min_tao=args.min_balance,
        )
    elif free < Decimal(str(args.min_balance)):
        step(
            "stake",
            False,
            skipped=True,
            reason=f"free {free} < min {args.min_balance}",
            fund_address=addr,
            how="Send TAO to fund_address on Finney, then re-run with --reuse --stake",
        )
    else:
        hotkey = args.hotkey or hot
        if not args.hotkey:
            step(
                "stake",
                False,
                error="real stake needs --hotkey <validator_ss58> (cold//hotkey is not a validator)",
                free_tao=str(free),
            )
        else:
            plugin3 = TaoPlugin(
                config=cfg,
                client=SubstrateTaoClient(config=cfg),
                account_store=store,
            )
            stake_result = plugin3.delegate(
                ctx,
                amount_tao=float(args.amount),
                netuid=int(args.netuid),
                hotkey=hotkey,
                confirm=True,
                password=password,
            )
            step(
                "stake",
                bool(stake_result.get("ok")),
                **{
                    k: stake_result.get(k)
                    for k in ("extrinsic_hash", "error", "action", "netuid", "amount_tao", "hotkey", "call")
                    if k in stake_result or stake_result.get(k) is not None
                },
            )

    report["address"] = addr
    report["hotkey_ss58"] = hot
    report["free_tao"] = str(free)
    report["ok"] = all(s.get("ok") for s in report["steps"] if not s.get("skipped"))

    out_path = work / "last_report.json"
    # Avoid writing secrets into report
    out_path.write_text(json.dumps(report, indent=2))
    os.chmod(out_path, stat.S_IRUSR | stat.S_IWUSR)
    print("---")
    print(
        json.dumps(
            {
                "summary_ok": report["ok"],
                "address": addr,
                "free_tao": str(free),
                "report": str(out_path),
                "mnemonic_file": str(mnemonic_path) if mnemonic_path.is_file() else None,
                "next": (
                    f"Fund {addr} with a little TAO on Finney, then:\n"
                    f"  VIDA_TAO_PASSWORD from {password_path}\n"
                    f"  python scripts/tao_live_e2e.py --reuse --stake --hotkey <VALIDATOR_SS58> --amount 0.01"
                ),
            },
            indent=2,
        )
    )

    if args.write_proof:
        proof = ROOT / "docs" / "proofs" / "tao_live_e2e.md"
        proof.write_text(
            "\n".join(
                [
                    "# TAO Live E2E",
                    "",
                    f"**When:** {report['when']}",
                    f"**Network:** {args.network}",
                    f"**Address:** `{addr}`",
                    f"**Free TAO:** {free}",
                    "",
                    "## Steps",
                    "",
                    "```json",
                    json.dumps(report["steps"], indent=2),
                    "```",
                    "",
                    "## Stake",
                    "",
                    (
                        f"Attempted: `{stake_result}`"
                        if stake_result is not None
                        else "Not attempted or skipped (needs funds + validator hotkey)."
                    ),
                    "",
                    "Mnemonic is **not** in this proof (stays in 0600 workdir file).",
                    "",
                ]
            )
        )
        print(f"wrote {proof}", file=sys.stderr)

    # success if health+provision+balance worked; stake optional
    core_ok = all(
        s["ok"] for s in report["steps"] if s["step"] in ("health", "provision", "balance", "agent_provision_blocked")
    )
    return 0 if core_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
