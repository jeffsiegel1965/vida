#!/usr/bin/env python3
"""Vida Wallet management API — session grant, revoke, adjust, overflow.

Backs the wallet dashboard UI.
"""

import json
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add vida repo to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vida.secure_wallet import SecureVida, grant_agent_session  # noqa: E402

# ── Config ──

WALLET_JSON = Path.home() / ".vida" / "wallet.json"
SESSION_DIR = Path.home() / ".vida" / "sessions"
SESSIONS_STORE = Path.home() / ".vida" / "sessions_meta.json"
API_PORT = 8769

os.makedirs(SESSION_DIR, exist_ok=True)

# ── In-memory state ──

_sessions: dict[str, dict] = {}
_overflow_threshold: float = 0.0
_overflow_dest: str = ""


def _load_meta():
    global _sessions
    if SESSIONS_STORE.exists():
        try:
            _sessions = json.loads(SESSIONS_STORE.read_text())
        except Exception:
            pass


def _save_meta():
    SESSIONS_STORE.write_text(json.dumps(_sessions, indent=2))


_load_meta()


def _wallet_address() -> str:
    if WALLET_JSON.exists():
        try:
            return json.loads(WALLET_JSON.read_text()).get("address", "")
        except Exception:
            pass
    return ""


def _wallet_network() -> str:
    if WALLET_JSON.exists():
        try:
            return json.loads(WALLET_JSON.read_text()).get("network", "mainnet")
        except Exception:
            pass
    return "mainnet"


# ── HTTP Handler ──

class Handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        p = self.path.strip("/").split("/")

        # GET /api/v1/wallet/sessions
        if p[:4] == ["api", "v1", "wallet", "sessions"]:
            now = time.time()
            active = []
            for sid, s in _sessions.items():
                if s.get("expires_at", 0) < now:
                    continue
                sp = SESSION_DIR / f"{sid}.json"
                daily = 0.0
                if sp.exists():
                    try:
                        sd = json.loads(sp.read_text())
                        es = sd.get("enc_spend")
                        if es:
                            # Just trust the file exists — decrypt requires machine_key
                            pass
                        ds = sd.get("spend", {}).get("daily_spent")
                        if ds is not None:
                            daily = float(ds)
                    except Exception:
                        pass
                active.append({
                    "id": sid,
                    "wallet_id": s.get("wallet_id", ""),
                    "mode": s.get("mode", "COMMAND"),
                    "expires_at": s.get("expires_at", 0),
                    "max_kas_per_tx": s.get("max_kas_per_tx", 0),
                    "max_kas_per_day": s.get("max_kas_per_day", 0),
                    "allowed_destinations": s.get("allowed_destinations", []),
                    "daily_spent": daily,
                    "active": s.get("expires_at", 0) > now,
                })
            return self._json({
                "ok": True, "sessions": active,
                "address": _wallet_address(),
                "overflow_threshold": _overflow_threshold,
                "overflow_dest": _overflow_dest,
            })

        # GET /api/v1/wallet/status
        if p[:4] == ["api", "v1", "wallet", "status"]:
            return self._json({
                "ok": True,
                "address": _wallet_address(),
                "network": _wallet_network(),
                "locked": WALLET_JSON.exists(),
                "active_sessions": len(_sessions),
                "overflow_threshold": _overflow_threshold,
                "overflow_dest": _overflow_dest,
            })

        # GET /health
        if p[0] == "health":
            return self._json({"status": "ok", "service": "vida-wallet-api"})

        return self._json({"error": "not found"}, status=404)

    def do_POST(self):
        p = self.path.strip("/").split("/")

        # POST /api/v1/wallet/grant
        if p[:4] == ["api", "v1", "wallet", "grant"]:
            body = self._body()
            wid = body.get("wallet_id", "default")
            pw = body.get("password", "")
            mode = body.get("mode", "COMMAND")
            max_tx = float(body.get("max_kas_per_tx", 0) or 0)
            max_day = float(body.get("max_kas_per_day", 0) or 0)
            hours = int(body.get("hours", 24))
            dests = body.get("destinations")

            if not pw:
                return self._json({"ok": False, "error": "password required"}, status=400)
            if not WALLET_JSON.exists():
                return self._json({"ok": False, "error": "no wallet provisioned"}, status=400)

            sid = f"{wid}-{int(time.time())}"
            sp = str(SESSION_DIR / f"{sid}.json")

            try:
                result = grant_agent_session(
                    wallet_path=str(WALLET_JSON),
                    password=pw,
                    session_path=sp,
                    hours=float(hours),
                    max_kas_per_tx=float(max_tx) if max_tx > 0 else 0.0,
                    max_kas_per_day=float(max_day) if max_day > 0 else 0.0,
                    allowed_destinations=dests,
                    allow_unlimited=(max_tx <= 0 and max_day <= 0),
                )
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, status=400)

            if not result.get("ok"):
                return self._json({"ok": False, "error": result.get("error", "grant failed")}, status=400)

            _sessions[sid] = {
                "wallet_id": wid, "mode": mode,
                "expires_at": time.time() + hours * 3600,
                "max_kas_per_tx": max_tx, "max_kas_per_day": max_day,
                "allowed_destinations": dests or [],
                "daily_spent": 0.0,
            }
            _save_meta()
            return self._json({"ok": True, "session_id": sid, "session_path": sp})

        # POST /api/v1/wallet/revoke
        if p[:4] == ["api", "v1", "wallet", "revoke"]:
            body = self._body()
            sid = body.get("session_id", "")
            if sid in _sessions:
                del _sessions[sid]
                # Also delete the session file.
                (SESSION_DIR / f"{sid}.json").unlink(missing_ok=True)
                _save_meta()
                return self._json({"ok": True, "revoked": sid})
            return self._json({"ok": False, "error": "session not found"}, status=404)

        # POST /api/v1/wallet/revoke-all
        if p[:4] == ["api", "v1", "wallet", "revoke-all"]:
            count = len(_sessions)
            for sid in list(_sessions):
                (SESSION_DIR / f"{sid}.json").unlink(missing_ok=True)
            _sessions.clear()
            _save_meta()
            return self._json({"ok": True, "revoked": count})

        # POST /api/v1/wallet/adjust
        if p[:4] == ["api", "v1", "wallet", "adjust"]:
            body = self._body()
            sid = body.get("session_id", "")
            if sid not in _sessions:
                return self._json({"ok": False, "error": "session not found"}, status=404)
            for field in ("max_kas_per_tx", "max_kas_per_day"):
                if field in body:
                    _sessions[sid][field] = float(body[field])
            if "mode" in body:
                _sessions[sid]["mode"] = body["mode"]
            if "allowed_destinations" in body:
                _sessions[sid]["allowed_destinations"] = body["allowed_destinations"]
            _save_meta()
            return self._json({"ok": True, "session_id": sid})

        # POST /api/v1/wallet/overflow
        if p[:4] == ["api", "v1", "wallet", "overflow"]:
            global _overflow_threshold, _overflow_dest
            body = self._body()
            _overflow_threshold = float(body.get("threshold", _overflow_threshold) or 0)
            _overflow_dest = str(body.get("destination", _overflow_dest) or "")
            return self._json({"ok": True, "threshold": _overflow_threshold, "destination": _overflow_dest})

        return self._json({"error": "not found"}, status=404)

    def log_message(self, *args, **kwargs):
        pass


# ── Main ──

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else API_PORT
    srv = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[vida-wallet-api] :{port} | {_wallet_address() or 'no wallet'} | {len(_sessions)} sessions")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


if __name__ == "__main__":
    main()
