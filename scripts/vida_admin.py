"""Vida Admin UI — local web dashboard for managing the agent wallet.

Usage:
  uv run python scripts/vida_admin.py

Opens: http://127.0.0.1:8082
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── FastAPI + uvicorn ──
try:
    import uvicorn
    from fastapi import FastAPI, Form, Request
    from fastapi.responses import HTMLResponse
except ImportError:
    print("Installing fastapi + uvicorn...")
    subprocess.check_call([sys.executable, "-m", "uv", "pip", "install", "fastapi", "uvicorn", "jinja2"])
    import uvicorn
    from fastapi import FastAPI, Form, Request
    from fastapi.responses import HTMLResponse

app = FastAPI(title="Vida Admin")

# ── Data helpers ──

REPO = Path(__file__).resolve().parent.parent


def git_log(n: int = 10) -> list[dict]:
    """Last N commits."""
    try:
        out = subprocess.run(
            ["git", "log", f"--max-count={n}", "--format=%h|%s|%ar"],
            capture_output=True,
            text=True,
            cwd=REPO,
            timeout=5,
        )
        rows = []
        for line in out.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 2)
            rows.append({"sha": parts[0], "msg": parts[1], "ago": parts[2] if len(parts) > 2 else ""})
        return rows
    except Exception:
        return []


def test_count() -> dict:
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True,
            text=True,
            cwd=REPO,
            timeout=30,
        )
        line = out.stdout.strip().split("\n")[-1] if out.stdout else ""
        return {"output": line, "passed": "passed" in line}
    except Exception as e:
        return {"output": str(e), "passed": False}


def ruff_status() -> dict:
    try:
        out = subprocess.run(
            [sys.executable, "-m", "ruff", "check", ".", "--statistics"],
            capture_output=True,
            text=True,
            cwd=REPO,
            timeout=15,
        )
        return {
            "errors": 0 if not out.stdout.strip() else len(out.stdout.strip().split("\n")),
            "output": out.stdout.strip() or "clean",
        }
    except Exception as e:
        return {"errors": -1, "output": str(e)}


def list_sessions() -> list[dict]:
    sessions_dir = Path.home() / ".vida" / "sessions"
    if not sessions_dir.exists():
        return []
    sessions = []
    for f in sorted(sessions_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        if f.suffix == ".json":
            try:
                data = json.loads(f.read_text())
                sessions.append(
                    {
                        "id": f.stem,
                        "created": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "caps": f"{data.get('max_kas_per_tx', '?')} KAS/tx, {data.get('max_kas_per_day', '?')} KAS/day",
                        "expires": data.get("expires_at", "never"),
                    }
                )
            except Exception:
                sessions.append({"id": f.stem, "created": "?", "caps": "?", "expires": "?"})
    return sessions


def list_escrows() -> list[dict]:
    store = Path.home() / ".vida" / "escrows"
    if not store.exists():
        return []
    escrows = []
    for f in sorted(store.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        if f.suffix == ".json":
            try:
                data = json.loads(f.read_text())
                escrows.append(
                    {
                        "id": f.stem[:16] + "...",
                        "amount": f"{data.get('amount_kas', '?')} KAS",
                        "status": data.get("status", "?"),
                        "created": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d"),
                    }
                )
            except Exception:
                pass
    return escrows


# ── Routes ──

HTML_HEAD = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vida Admin</title>
<style>
  :root { color-scheme: dark; --bg: #0a100f; --card: #111a18; --border: rgba(255,255,255,0.09);
    --text: #e9f1ef; --muted: #a7b8b4; --accent: #70c7ba; --red: #f2a566; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; font-size: 15px; }
  .container { max-width: 960px; margin: 0 auto; padding: 1rem; }
  h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
  .subtitle { color: var(--muted); font-size: 0.9rem; margin: 0 0 1.5rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 0.75rem 1rem; }
  .card .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.25rem; font-weight: 600; margin-top: 0.25rem; }
  .card .value.green { color: var(--accent); }
  .card .value.red { color: var(--red); }
  h2 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; }
  td { color: var(--text); }
  .badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
  .badge.green { background: rgba(112,199,186,0.15); color: var(--accent); }
  .badge.red { background: rgba(242,165,102,0.15); color: var(--red); }
  .badge.gray { background: rgba(255,255,255,0.08); color: var(--muted); }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .actions { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
  button { background: var(--accent); color: var(--bg); border: none; border-radius: 6px; padding: 0.4rem 0.8rem; font-size: 0.85rem; cursor: pointer; }
  button:hover { opacity: 0.85; }
  pre { background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem; font-size: 0.8rem; overflow-x: auto; }
  .nav { display: flex; gap: 1rem; margin-bottom: 1rem; }
  .nav a { color: var(--muted); font-size: 0.9rem; }
  .nav a.active { color: var(--accent); }
</style>
</head>
<body>
<div class="container">
"""

HTML_FOOT = """
</div></body></html>"""


def render_page(title: str, body: str, active: str = "dashboard") -> str:
    nav = f"""
    <div class="nav">
      <a href="/" class="{"active" if active == "dashboard" else ""}">Dashboard</a>
      <a href="/sessions" class="{"active" if active == "sessions" else ""}">Sessions</a>
      <a href="/covenants" class="{"active" if active == "covenants" else ""}">Covenants</a>
      <a href="/config" class="{"active" if active == "config" else ""}">Config</a>
      <a href="/logs" class="{"active" if active == "logs" else ""}">Activity</a>
    </div>
    """
    return f"{HTML_HEAD}{nav}<h1>{title}</h1>{body}{HTML_FOOT}"


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    tests = test_count()
    ruff = ruff_status()
    sessions = list_sessions()
    escrows = list_escrows()
    commits = git_log(5)

    # Build HTML tables to avoid nested f-string issues
    html_sessions = ""
    if sessions:
        rows = "".join(
            f"<tr><td><code>{s['id']}</code></td><td>{s['created']}</td><td>{s['caps']}</td><td>{s['expires']}</td></tr>"
            for s in sessions[:5]
        )
        html_sessions = f"<table><tr><th>ID</th><th>Created</th><th>Caps</th><th>Expires</th></tr>{rows}</table>"

    html_escrows = ""
    if escrows:
        rows = "".join(
            f'<tr><td><code>{e["id"]}</code></td><td>{e["amount"]}</td><td><span class="badge green">{e["status"]}</span></td><td>{e["created"]}</td></tr>'
            for e in escrows[:5]
        )
        html_escrows = f"<table><tr><th>ID</th><th>Amount</th><th>Status</th><th>Created</th></tr>{rows}</table>"

    # Count session files
    session_count = len(sessions)
    open_sessions = sum(
        1
        for s in sessions
        if "never" in s.get("expires", "") or s.get("expires", "") > datetime.now().strftime("%Y-%m-%d")
    )

    body = f"""
    <div class="grid">
      <div class="card"><div class="label">Tests</div><div class="value {"green" if tests["passed"] else "red"}">{tests["output"] or "?"}</div></div>
      <div class="card"><div class="label">Ruff Errors</div><div class="value {"green" if ruff["errors"] == 0 else "red"}">{ruff["errors"]}</div></div>
      <div class="card"><div class="label">Sessions</div><div class="value green">{open_sessions} / {session_count}</div></div>
      <div class="card"><div class="label">Escrows</div><div class="value green">{len(escrows)}</div></div>
    </div>

    <h2>Recent Commits</h2>
    <table>
      <tr><th>SHA</th><th>Message</th><th>When</th></tr>
      {"".join(f"<tr><td><code>{c['sha']}</code></td><td>{c['msg']}</td><td>{c['ago']}</td></tr>" for c in commits)}
    </table>

    <h2>Active Sessions</h2>
    {html_sessions if sessions else '<p style="color:var(--muted)">No sessions yet.</p>'}

        <h2>Recent Escrows</h2>
    {html_escrows if escrows else '<p style="color:var(--muted)">No escrows yet.</p>'}
    """
    return render_page("Dashboard", body)


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page():
    sessions = list_sessions()
    rows = (
        "".join(
            f"<tr><td><code>{s['id']}</code></td><td>{s['created']}</td><td>{s['caps']}</td><td>{s['expires']}</td></tr>"
            for s in sessions
        )
        if sessions
        else '<tr><td colspan="4" style="color:var(--muted)">No sessions found.</td></tr>'
    )

    body = f"""
    <div class="actions">
      <form action="/session/create" method="post" style="display:inline">
        <input type="number" name="hours" value="24" min="1" max="720" style="width:60px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:0.3rem">
        <input type="number" name="max_tx" value="1" min="0.1" step="0.1" style="width:70px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:0.3rem">
        <input type="number" name="max_day" value="5" min="0.1" step="0.1" style="width:70px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:0.3rem">
        <button type="submit">Grant Session</button>
      </form>
      <small style="color:var(--muted);align-self:center">hours / max KAS/tx / max KAS/day</small>
    </div>
    <table>
      <tr><th>ID</th><th>Created</th><th>Caps</th><th>Expires</th></tr>
      {rows}
    </table>
    """
    return render_page("Sessions", body, active="sessions")


@app.get("/covenants", response_class=HTMLResponse)
async def covenants_page():
    from vida.plugins.covenant.fees import describe_fees

    fees = describe_fees()
    body = f"""
    <h2>Escrows</h2>
    <p style="color:var(--muted)">Escrow list coming soon. View in ~/.vida/escrows/ for now.</p>
    <h2>Channels</h2>
    <p style="color:var(--muted)">KCC-0402 aligned. 36 tests. Voucher-based off-chain payments.</p>
    <h2>Fee Schedule</h2>
    <pre>{json.dumps(fees, indent=2)}</pre>
    """
    return render_page("Covenants", body, active="covenants")


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    fee_addr = os.environ.get("VIDA_FEE_ADDRESS", "default (env not set)")
    donate_addr = os.environ.get("VIDA_DONATION_ADDRESS", "default (env not set)")
    tao_fee_addr = os.environ.get("VIDA_TAO_FEE_ADDRESS", "default (env not set)")

    body = f"""
    <h2>Environment</h2>
    <table>
      <tr><td>VIDA_FEE_ADDRESS</td><td><code>{fee_addr}</code></td></tr>
      <tr><td>VIDA_DONATION_ADDRESS</td><td><code>{donate_addr}</code></td></tr>
      <tr><td>VIDA_TAO_FEE_ADDRESS</td><td><code>{tao_fee_addr}</code></td></tr>
      <tr><td>Network</td><td><code>mainnet</code> (testnet-10 for covenant testing)</td></tr>
      <tr><td>Tests</td><td>221 total</td></tr>
      <tr><td>License</td><td>MIT (core) + Commercial (covenants)</td></tr>
    </table>
    <p style="color:var(--muted);margin-top:1rem">Set these via env vars in your shell before starting the server.</p>
    """
    return render_page("Config", body, active="config")


@app.get("/logs", response_class=HTMLResponse)
async def logs_page():
    body = """
    <h2>Recent Activity</h2>
    <p style="color:var(--muted)">Log viewer coming soon. Run <code>tail -f ~/.vida/logs/*.log</code> in the terminal for now.</p>
    <h2>On-Chain Proofs</h2>
    <table>
      <tr><th>Tx</th><th>What</th><th>Link</th></tr>
      <tr><td>d32b4504...</td><td>Agent send, 10 KAS</td><td><a href="https://explorer.kaspa.org/txs/d32b4504ecc218d29b8c661cadf21b026697a9e1d69409240b539064aa5825e7" target="_blank">explorer</a></td></tr>
    </table>
    """
    return render_page("Activity", body, active="logs")


if __name__ == "__main__":
    print(f"Vida Admin UI: http://127.0.0.1:8082")
    uvicorn.run(app, host="127.0.0.1", port=8082, log_level="info")
