"""
kascov — a tiny zero-dependency client for the kascov JSON API.

CORS-open API, no keys. Integrated into Vida covenant plugin.

https://kascov.io · https://github.com/Knitser/kascov · MIT
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, Optional

DEFAULT_BASE = "https://kascov.io"


class KascovClient:
    """Zero-dependency client for kascov covenant explorer API."""

    def __init__(self, network: str = "testnet-10", base: str = DEFAULT_BASE) -> None:
        self.network = network
        self.base = base.rstrip("/")

    def _get(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base}{path}",
            headers={"accept": "application/json", "user-agent": "vida-covenant-plugin"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.load(res)
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": f"kascov HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"ok": False, "error": f"kascov unreachable: {e.reason}"}
        except (OSError, json.JSONDecodeError) as e:
            return {"ok": False, "error": f"kascov response error: {e}"}

    def live(self) -> Dict[str, Any]:
        """Small fast feed: stats + chain tip + newest ~150 events."""
        return self._get(f"/data/{self.network}-live.json")

    def coin(self, covenant_id: str) -> Dict[str, Any]:
        """One coin's full story: events, UTXOs, holders."""
        return self._get(f"/data/{self.network}/c/{covenant_id}.json")

    def tx(self, txid: str) -> Dict[str, Any]:
        """Which covenant(s) did this transaction move?"""
        return self._get(f"/data/{self.network}/tx/{txid}.json")

    def address(self, addr_or_pubkey: str) -> Dict[str, Any]:
        """Smart coins an address funded, received, or controls."""
        return self._get(f"/data/{self.network}/addr/{urllib.parse.quote(addr_or_pubkey)}.json")

    def digest(self) -> Dict[str, Any]:
        """Last-24h digest: births/moves/burns."""
        return self._get(f"/data/{self.network}/digest.json")

    def galaxy(self) -> Dict[str, Any]:
        """Whole-network app graph."""
        return self._get(f"/data/{self.network}/galaxy.json")

    def templates(self) -> Dict[str, Any]:
        """Contract-type analytics."""
        return self._get(f"/data/{self.network}/templates.json")

    def activity(self, range: str = "24h") -> Dict[str, Any]:
        """Births/moves/burns per DAA bucket. range: 1h|6h|24h|48h|all"""
        return self._get(f"/data/{self.network}/activity.json?range={range}")

    # ── Tool wrappers for Vida Hermes integration ──

    def verify_covenant(self, covenant_id: str) -> Dict[str, Any]:
        """Verify a covenant exists on-chain via kascov."""
        result = self.coin(covenant_id)
        if result.get("ok") is False:
            return result
        if "covenant_id" in result or "events" in result:
            return {
                "ok": True,
                "verified": True,
                "source": "kascov",
                "network": self.network,
                "covenant_id": result.get("covenant_id") or result.get("id") or covenant_id,
                "events": len(result.get("events", [])),
                "status": "active" if result.get("active") else "retired" if result.get("burned") else "unknown",
            }
        return {"ok": True, "verified": False, "source": "kascov", "note": "not found in kascov index"}

    def search(self, query: str) -> Dict[str, Any]:
        """Search covenants by name, id, or transaction."""
        return self._get(f"/api/search?q={urllib.parse.quote(query)}")


# Singleton for reuse
_DEFAULT_CLIENT: KascovClient | None = None


def get_kascov(network: str = "testnet-10") -> KascovClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None or _DEFAULT_CLIENT.network != network:
        _DEFAULT_CLIENT = KascovClient(network=network)
    return _DEFAULT_CLIENT