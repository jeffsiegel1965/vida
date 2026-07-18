"""
Invoke local covenant tooling (kascov-lab / Node #1074 helpers).

Never logs private keys. Live calls require explicit env gates.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence


# Repo-relative defaults
_REPO = Path(__file__).resolve().parents[3]

# kascov-lab binary and WASM dirs are host-specific.
# Set these via env vars for live TN10 work.
DEFAULT_LAB: Optional[Path] = None
DEFAULT_KEY: Optional[Path] = None
DEFAULT_WASM: Optional[Path] = None
DEFAULT_NODE_HELPER = _REPO / "scripts" / "covenant_fund_agent_pot.js"
DEFAULT_SPEND_HELPER = _REPO / "scripts" / "covenant_spend_agent_pot.js"


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _resolve_path(key: str, default: Path | None) -> Path | None:
    """Return env var value or default, handling None safely."""
    val = os.environ.get(key)
    if val is not None:
        return Path(val)
    return default


def _safe_path(p: Path | None) -> Path:
    """Return Path or empty sentinel for safe chaining on None."""
    return p if p is not None else Path("")


def live_gates_ok() -> dict[str, Any]:
    """Check env + binary/key presence for live TN10 work."""
    lab = _resolve_path("VIDA_KASCOV_LAB", DEFAULT_LAB)
    key = _resolve_path("VIDA_KASCOV_KEY", DEFAULT_KEY)
    node_helper = _resolve_path("VIDA_COVENANT_NODE_HELPER", DEFAULT_NODE_HELPER)
    spend_helper = _resolve_path("VIDA_COVENANT_SPEND_HELPER", DEFAULT_SPEND_HELPER)
    wasm = _resolve_path("VIDA_KASPA_WASM", DEFAULT_WASM)
    return {
        "live_env": _truthy("VIDA_COVENANT_LIVE"),
        "lab_path": str(lab) if lab else "",
        "lab_ok": lab is not None and lab.is_file() and os.access(lab, os.X_OK),
        "key_path": str(key) if key else "",
        "key_ok": key is not None and key.is_file() and key.stat().st_size > 0,
        "node": shutil.which("node") or "",
        "node_helper": str(node_helper) if node_helper else "",
        "node_helper_ok": node_helper is not None and node_helper.is_file(),
        "spend_helper": str(spend_helper) if spend_helper else "",
        "spend_helper_ok": spend_helper is not None and spend_helper.is_file(),
        "wasm_dir": str(wasm) if wasm else "",
        "wasm_ok": wasm is not None and ((wasm / "kaspa.js").is_file() or (wasm / "kaspa_bg.wasm").is_file()),
    }


def can_run_lab_demo() -> bool:
    g = live_gates_ok()
    return bool(g["live_env"] and g["lab_ok"] and g["key_ok"])


def can_fund_agent_pot() -> bool:
    g = live_gates_ok()
    return bool(
        g["live_env"]
        and g["key_ok"]
        and g["node"]
        and g["node_helper_ok"]
        and g["wasm_ok"]
    )


def can_spend_agent_pot() -> bool:
    g = live_gates_ok()
    return bool(
        g["live_env"]
        and g["key_ok"]
        and g["node"]
        and g["spend_helper_ok"]
        and g["wasm_ok"]
    )


def run_lab_demo(*, transitions: int = 1, timeout: int = 120) -> dict[str, Any]:
    """Run kascov-lab demo (genesis → N transitions → burn)."""
    g = live_gates_ok()
    if not g["live_env"]:
        return {
            "ok": False,
            "error": "set VIDA_COVENANT_LIVE=1 to allow live TN10 lab calls",
            "gates": g,
        }
    if not g["lab_ok"]:
        return {
            "ok": False,
            "error": f"kascov-lab missing/not executable: {g['lab_path']}",
            "gates": g,
        }
    if not g["key_ok"]:
        return {"ok": False, "error": f"key file missing: {g['key_path']}", "gates": g}
    if transitions < 0 or transitions > 5:
        return {"ok": False, "error": "transitions must be 0..5"}

    key = Path(g["key_path"])
    if key.resolve() != DEFAULT_KEY.resolve():
        DEFAULT_KEY.write_bytes(key.read_bytes())
        DEFAULT_KEY.chmod(0o600)

    cmd = [g["lab_path"], "demo", "--transitions", str(transitions)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "RUST_LOG": os.environ.get("RUST_LOG", "warn")},
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "kascov-lab timed out", "cmd": cmd}
    except OSError as e:
        return {"ok": False, "error": f"exec failed: {e}", "cmd": cmd}

    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    parsed = _parse_lab_demo_output(out)
    return {
        "ok": proc.returncode == 0 and bool(parsed.get("covenant_id")),
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        **parsed,
        "tooling": "kascov-lab",
        "network": "testnet-12",
    }


def fund_agent_pot(
    *,
    pot_sompi: int,
    max_tx_sompi: int,
    allowed_destinations: Optional[Sequence[str]] = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Fund a covenant-bound agent pot UTXO via Node + #1074 WASM helper."""
    g = live_gates_ok()
    if not g["live_env"]:
        return {
            "ok": False,
            "error": "set VIDA_COVENANT_LIVE=1 to allow live fund_agent_pot",
            "gates": g,
        }
    if not can_fund_agent_pot():
        return {
            "ok": False,
            "error": "need node + covenant_fund_agent_pot.js + wasm + key",
            "gates": g,
        }
    if pot_sompi < 1_000_000:
        return {"ok": False, "error": "pot_sompi too small (min 0.01 KAS)"}
    if max_tx_sompi <= 0 or max_tx_sompi > pot_sompi:
        return {"ok": False, "error": "max_tx_sompi must be in (0, pot_sompi]"}

    dests = list(allowed_destinations or [])
    payload = {
        "pot_sompi": pot_sompi,
        "max_tx_sompi": max_tx_sompi,
        "allowed_destinations": dests,
        "key_path": g["key_path"],
        "wasm_dir": g["wasm_dir"],
        "network": "testnet-12",
        "compute_budget": 65535,
        "single_output": True,
    }
    cmd = [g["node"], g["node_helper"], json.dumps(payload)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "node fund helper timed out"}
    except OSError as e:
        return {"ok": False, "error": f"node exec failed: {e}"}

    result: dict[str, Any] = {"ok": False, "returncode": proc.returncode}
    for line in reversed((proc.stdout or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                result = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    result.setdefault("stdout", proc.stdout or "")
    result.setdefault("stderr", proc.stderr or "")
    result["returncode"] = proc.returncode
    if proc.returncode != 0 and result.get("ok") is not True:
        result["ok"] = False
        result.setdefault("error", f"node helper exit {proc.returncode}")
    return result


def spend_agent_pot(
    *,
    amount_sompi: int,
    destination: str,
    max_tx_sompi: int = 0,
    allowed_destinations: Optional[Sequence[str]] = None,
    covenant_id: Optional[str] = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Broadcast a pot spend via Node helper after gates pass."""
    g = live_gates_ok()
    if not g["live_env"]:
        return {
            "ok": False,
            "error": "set VIDA_COVENANT_LIVE=1 to allow live spend_agent_pot",
            "gates": g,
        }
    if not can_spend_agent_pot():
        return {
            "ok": False,
            "error": "need node + covenant_spend_agent_pot.js + wasm + key",
            "gates": g,
        }

    # Validate covenant_id to prevent shell injection
    if covenant_id and not re.match(r"^[a-f0-9]{64}$", covenant_id):
        return {"ok": False, "error": f"invalid covenant_id format: {covenant_id}"}

    payload = {
        "amount_sompi": int(amount_sompi),
        "destination": destination,
        "max_tx_sompi": int(max_tx_sompi or 0),
        "allowed_destinations": list(allowed_destinations or []),
        "covenant_id": covenant_id or "",
        "key_path": g["key_path"],
        "wasm_dir": g["wasm_dir"],
        "network": "testnet-12",
        "compute_budget": 65535,
    }
    cmd = [g["node"], g["spend_helper"], json.dumps(payload)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "node spend helper timed out"}
    except OSError as e:
        return {"ok": False, "error": f"node exec failed: {e}"}

    result: dict[str, Any] = {"ok": False, "returncode": proc.returncode}
    for line in reversed((proc.stdout or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                result = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    result.setdefault("stdout", proc.stdout or "")
    result.setdefault("stderr", proc.stderr or "")
    result["returncode"] = proc.returncode
    if proc.returncode != 0 and result.get("ok") is not True:
        result["ok"] = False
        result.setdefault("error", f"node helper exit {proc.returncode}")
    return result


def _parse_lab_demo_output(text: str) -> dict[str, Any]:
    covenant_id = None
    genesis_tx = transition_tx = burn_tx = None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "GENESIS" in line and "covenant" in line:
            parts = line.split()
            try:
                covenant_id = parts[parts.index("covenant") + 1]
            except (ValueError, IndexError):
                pass
            for j in range(i + 1, min(i + 4, len(lines))):
                if "tx" in lines[j]:
                    genesis_tx = lines[j].split()[-1]
                    break
        if "TRANSITION" in line and "tx" in line:
            transition_tx = line.split()[-1]
        if line.strip().startswith("BURN") and "tx" in line:
            burn_tx = line.split()[-1]
    out: dict[str, Any] = {}
    if covenant_id:
        out["covenant_id"] = covenant_id
    txs2 = {}
    if genesis_tx:
        txs2["genesis"] = genesis_tx
    if transition_tx:
        txs2["transition"] = transition_tx
    if burn_tx:
        txs2["burn"] = burn_tx
    if txs2:
        out["txs"] = txs2
    return out
