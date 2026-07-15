#!/usr/bin/env python3
"""
T1.1 live health check for Vida TAO plugin.

Usage (needs substrate-interface):
  VIDA_TAO_NETWORK=finney python scripts/tao_health_check.py
  VIDA_TAO_NETWORK=finney python scripts/tao_health_check.py --address 5...

No keys. No derivation. Optional public address for balance smoke test.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Vida TAO live health check")
    ap.add_argument("--network", default=None, help="finney|test (default env or finney)")
    ap.add_argument("--endpoint", default=None, help="optional wss:// override")
    ap.add_argument("--address", default=None, help="optional SS58 for balance smoke test")
    ap.add_argument("--write-proof", action="store_true", help="write docs/proofs/tao_phase1_health.md")
    args = ap.parse_args()

    from vida.plugins.tao.config import load_tao_config, TaoNetwork
    from vida.plugins.tao.substrate_client import SubstrateTaoClient

    net = args.network or "finney"
    cfg = load_tao_config(network=net, endpoint=args.endpoint)
    if cfg.network == TaoNetwork.MOCK:
        print("ERROR: use finney or test for live check", file=sys.stderr)
        return 2

    client = SubstrateTaoClient(config=cfg)
    started = time.time()
    try:
        client.connect()
        health = client.health()
        result = {
            "ok": health.ok,
            "network": health.network,
            "endpoint": health.endpoint,
            "chain_name": health.chain_name,
            "block_number": health.block_number,
            "error": health.error,
            "elapsed_sec": round(time.time() - started, 2),
            "ss58_prefix": cfg.ss58_prefix,
        }
        if args.address:
            bal = client.get_balance(args.address)
            result["balance"] = {
                "ok": bal.ok,
                "address": bal.address,
                "free_tao": str(bal.free_tao),
                "reserved_tao": str(bal.reserved_tao),
                "error": bal.error,
            }
        print(json.dumps(result, indent=2))

        if args.write_proof and health.ok:
            proof_dir = ROOT / "docs" / "proofs"
            proof_dir.mkdir(parents=True, exist_ok=True)
            path = proof_dir / "tao_phase1_health.md"
            lines = [
                "# TAO Phase 1 — Live health proof",
                "",
                f"**When:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                f"**Network:** {health.network}",
                f"**Endpoint:** {health.endpoint}",
                f"**Chain:** {health.chain_name}",
                f"**Block:** {health.block_number}",
                f"**Elapsed:** {result['elapsed_sec']}s",
                "",
                "No keys were used. Health only (+ optional public balance).",
                "",
                "```json",
                json.dumps(result, indent=2),
                "```",
                "",
            ]
            path.write_text("\n".join(lines))
            print(f"wrote {path}", file=sys.stderr)
        return 0 if health.ok else 1
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
