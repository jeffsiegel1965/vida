"""Vida Discovery — pointers, receptors, and owner-controlled permissions.

Three-tier permission system:

  MANUAL    — Agent reports discoveries, owner approves before any connection
  BALANCED  — Trusted services auto-connect, unknown require owner approval
  PERMISSIVE — All services auto-connect, owner gets reports

Trust levels per service:
  trusted   — Owner-added pointers or built-in defaults, always allowed
  known     — Owner has previously approved this service
  unknown   — Newly discovered, needs owner decision
  blocked   — Owner has explicitly denied this service

Env var controls:
  VIDA_DISCOVERY_ENABLED     = true/false (master switch)
  VIDA_DISCOVERY_POLICY      = manual | balanced | permissive
  VIDA_DISCOVERY_LAN         = true/false (LAN receptor)
  VIDA_DISCOVERY_NETWORK     = true/false (node receptor)
  VIDA_DISCOVERY_AGENT       = true/false (agent receptor)
  VIDA_DISCOVERY_INTERVAL    = scan interval in seconds (default 60)
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger("vida.discovery")

# ── Policy modes ──

class Policy(Enum):
    MANUAL = "manual"
    BALANCED = "balanced"
    PERMISSIVE = "permissive"

class Trust(Enum):
    TRUSTED = "trusted"
    KNOWN = "known"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"

# ── Environment config ──

MASTER_ENABLED = os.environ.get("VIDA_DISCOVERY_ENABLED", "true").lower() in ("1", "true", "yes")
POLICY = Policy(os.environ.get("VIDA_DISCOVERY_POLICY", "balanced").lower())
RECEPTOR_LAN = os.environ.get("VIDA_DISCOVERY_LAN", "true").lower() in ("1", "true", "yes")
RECEPTOR_NETWORK = os.environ.get("VIDA_DISCOVERY_NETWORK", "true").lower() in ("1", "true", "yes")
RECEPTOR_AGENT = os.environ.get("VIDA_DISCOVERY_AGENT", "true").lower() in ("1", "true", "yes")
SCAN_INTERVAL = int(os.environ.get("VIDA_DISCOVERY_INTERVAL", "60"))

# Services that are always trusted
TRUSTED_TYPES = {"oracle", "marketplace", "mcp"}

DEFAULT_POINTERS = {
    "vida-oracle": {
        "url": os.environ.get("VIDA_ORACLE_URL", "http://127.0.0.1:8765"),
        "label": "Vida Oracle",
        "type": "oracle",
    },
    "vida-marketplace": {
        "url": os.environ.get("VIDA_MARKETPLACE_URL", "http://127.0.0.1:8768"),
        "label": "Vida Marketplace",
        "type": "marketplace",
    },
    "vida-mcp": {
        "url": os.environ.get("VIDA_MCP_URL", "http://127.0.0.1:8100"),
        "label": "Vida Wallet MCP",
        "type": "mcp",
    },
}


@dataclass
class ServiceEndpoint:
    """A discovered or configured service endpoint."""
    name: str
    url: str
    label: str
    type: str
    trust: str = "unknown"
    healthy: bool = False
    latency_ms: float = 0.0
    last_seen: float = 0.0
    version: str = ""
    details: dict = field(default_factory=dict)
    connected: bool = False  # whether agent has connected to this service


class ApprovalRequest:
    """A pending approval request for an unknown service."""
    def __init__(self, service: ServiceEndpoint):
        self.service = service
        self.created_at = time.time()
        self.decided: bool = False
        self.approved: bool = False
        self.decided_at: float = 0.0


class Discovery:
    """Service registry with owner-controlled permissions.

    Three policy modes control agent autonomy:
      MANUAL     — agent cannot connect to ANY discovered service without approval
      BALANCED   — trusted types auto-connect, unknown need approval
      PERMISSIVE — everything auto-connects, owner just gets reports

    Owner can also set per-service trust level via approve/block.
    """

    def __init__(self, pointers: Optional[dict] = None):
        self._enabled = MASTER_ENABLED
        self._policy = POLICY
        self._receptors = {
            "lan": RECEPTOR_LAN,
            "network": RECEPTOR_NETWORK,
            "agent": RECEPTOR_AGENT,
        }
        self._lock = threading.Lock()
        self._services: dict[str, ServiceEndpoint] = {}
        self._approvals: list[ApprovalRequest] = []
        self._report: list[dict] = []  # audit trail of discovery events
        self._last_scan = 0.0
        self._scanning = False
        self._max_report = 200

        # Load default pointers as trusted
        for name, cfg in (pointers or DEFAULT_POINTERS).items():
            self._services[name] = ServiceEndpoint(
                name=name, url=cfg["url"], label=cfg["label"],
                type=cfg["type"], trust="trusted",
            )

    # ── Policy controls ──

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        self._enabled = val
        self._log("system", f"Discovery {'enabled' if val else 'disabled'} by owner")

    @property
    def policy(self) -> Policy:
        return self._policy

    @policy.setter
    def policy(self, val: Policy):
        self._policy = val
        self._log("system", f"Policy set to {val.value}")

    def set_receptor(self, name: str, enabled: bool) -> bool:
        if name in self._receptors:
            self._receptors[name] = enabled
            self._log("receptor", f"Receptor '{name}' {'enabled' if enabled else 'disabled'}")
            return True
        return False

    def receptor_enabled(self, name: str) -> bool:
        return self._enabled and self._receptors.get(name, False)

    # ── Permission controls ──

    def approve(self, service_name: str) -> bool:
        """Owner approves a service — moves from unknown to known."""
        with self._lock:
            if service_name not in self._services:
                return False
            svc = self._services[service_name]
            old = svc.trust
            svc.trust = "known"
            self._log("approval", f"Service '{service_name}' approved by owner ({old} → known)")
            # Resolve pending approvals
            self._approvals = [a for a in self._approvals if a.service.name != service_name]
            return True

    def block(self, service_name: str) -> bool:
        """Owner blocks a service — moves to blocked trust level."""
        with self._lock:
            if service_name not in self._services:
                return False
            svc = self._services[service_name]
            old = svc.trust
            svc.trust = "blocked"
            svc.connected = False
            self._log("approval", f"Service '{service_name}' blocked by owner ({old} → blocked)")
            self._approvals = [a for a in self._approvals if a.service.name != service_name]
            return True

    def set_trust(self, service_name: str, trust: str) -> bool:
        """Owner sets trust level directly."""
        valid = {t.value for t in Trust}
        if trust not in valid:
            return False
        with self._lock:
            if service_name not in self._services:
                return False
            old = self._services[service_name].trust
            self._services[service_name].trust = trust
            self._log("approval", f"Service '{service_name}' trust set to '{trust}' (was '{old}')")
            if trust in ("trusted", "known", "blocked"):
                self._approvals = [a for a in self._approvals if a.service.name != service_name]
            return True

    # ── Connection gating ──

    def may_connect(self, service_name: str) -> tuple[bool, str]:
        """Check if agent is allowed to connect to this service under current policy.

        Returns (allowed, reason).
        """
        if not self._enabled:
            return False, "Discovery is disabled"

        with self._lock:
            if service_name not in self._services:
                return False, f"Service '{service_name}' not found"

            svc = self._services[service_name]

        # Trust-based gates
        if svc.trust == "trusted":
            return True, "Trusted service"
        if svc.trust == "known":
            return True, "Known service (owner-approved)"
        if svc.trust == "blocked":
            return False, "Service blocked by owner"

        # Unknown — policy decides
        if self._policy == Policy.PERMISSIVE:
            with self._lock:
                self._services[service_name].trust = "known"
            self._log("connect", f"Auto-approved '{service_name}' under permissive policy")
            return True, "Auto-approved under permissive policy"

        if self._policy == Policy.BALANCED and svc.type in TRUSTED_TYPES:
            with self._lock:
                self._services[service_name].trust = "known"
            self._log("connect", f"Auto-approved '{service_name}' (trusted type {svc.type})")
            return True, f"Known service type ({svc.type})"

        # Manual or balanced + unknown type = needs approval
        self._ensure_approval_request(svc)
        return False, f"Service '{service_name}' needs owner approval (policy: {self._policy.value})"

    def connect(self, service_name: str) -> tuple[bool, str]:
        """Agent requests to connect. Returns (allowed, reason)."""
        allowed, reason = self.may_connect(service_name)
        if allowed:
            with self._lock:
                if service_name in self._services:
                    self._services[service_name].connected = True
            self._log("connect", f"Connected to '{service_name}'")
        else:
            self._log("connect", f"Connection to '{service_name}' blocked: {reason}")
        return allowed, reason

    def _ensure_approval_request(self, svc: ServiceEndpoint):
        """Create a pending approval request if one doesn't exist."""
        with self._lock:
            for a in self._approvals:
                if a.service.name == svc.name:
                    return
            self._approvals.append(ApprovalRequest(svc))
            self._log("approval", f"Approval request created for '{svc.name}'")

    # ── Pointers ──

    def set_pointer(self, name: str, url: str, label: str = "", type_: str = "custom") -> bool:
        with self._lock:
            self._services[name] = ServiceEndpoint(
                name=name, url=url, label=label or name,
                type=type_, trust="trusted",
            )
            self._log("pointer", f"Pointer '{name}' set to {url}")
            return True

    def remove_pointer(self, name: str) -> bool:
        with self._lock:
            if name in self._services:
                del self._services[name]
                self._log("pointer", f"Pointer '{name}' removed")
                return True
            return False

    # ── Health probes ──

    def _probe(self, url: str, timeout: int = 5) -> tuple[bool, float, str, dict]:
        import urllib.request
        start = time.time()
        try:
            health_url = f"{url.rstrip('/')}/health"
            with urllib.request.urlopen(urllib.request.Request(health_url), timeout=timeout) as resp:
                latency = (time.time() - start) * 1000
                body = resp.read().decode()
                ok = resp.status < 400
                version = ""
                details = {}
                try:
                    data = json.loads(body)
                    version = str(data.get("version", data.get("data", {}).get("version", "")))
                    details = data
                except (json.JSONDecodeError, AttributeError):
                    pass
                return ok, round(latency, 1), version, details
        except Exception as e:
            return False, 0, "", {"error": str(e)[:100]}

    # ── Scan / receptors ──

    def _scan_pointers(self):
        with self._lock:
            services = dict(self._services)
        for name, svc in services.items():
            if svc.trust == "blocked":
                continue
            ok, lat, ver, details = self._probe(svc.url)
            with self._lock:
                if name in self._services:
                    changed = self._services[name].healthy != ok
                    self._services[name].healthy = ok
                    self._services[name].latency_ms = lat
                    self._services[name].version = ver
                    self._services[name].details = details
                    self._services[name].last_seen = time.time()
                    if changed:
                        self._log("health", f"'{name}' {'came online' if ok else 'went offline'} ({lat}ms)")

    def _scan_lan(self):
        if not self.receptor_enabled("lan"):
            return
        mcp_ports = [8100, 8765, 8768]
        local_ip = self._get_local_ip()
        if not local_ip:
            return
        subnet = ".".join(local_ip.split(".")[:3])
        discovered = []
        for suffix in range(2, 20):
            host = f"{subnet}.{suffix}"
            for port in mcp_ports:
                url = f"http://{host}:{port}"
                ok, lat, ver, details = self._probe(f"{url}/health", timeout=2)
                if ok:
                    name = f"lan-{host}-{port}"
                    with self._lock:
                        if name not in self._services:
                            self._services[name] = ServiceEndpoint(
                                name=name, url=url,
                                label=f"LAN {host}:{port}",
                                type="mcp" if port == 8100 else "custom",
                                trust="unknown",
                                healthy=True,
                                latency_ms=lat,
                                version=ver,
                                details=details,
                                last_seen=time.time(),
                            )
                            discovered.append(name)
        if discovered:
            self._log("scan", f"LAN scan discovered: {', '.join(discovered)}")

    def _scan_network(self):
        if not self.receptor_enabled("network"):
            return
        known_nodes = {
            "oracle-sf": "http://143.198.230.52:8765",
            "oracle-tor": "http://167.99.191.155:8765",
            "oracle-fra": "http://165.232.73.115:8765",
            "oracle-sgp": "http://159.65.11.201:8765",
            "oracle-dallas": "http://45.56.75.74:8765",
            "oracle-chicago": "http://172.234.217.220:8765",
            "oracle-miami": "http://172.238.203.159:8765",
            "oracle-newark": "http://162.216.16.109:8765",
            "oracle-la": "http://172.233.130.94:8765",
            "oracle-seattle": "http://172.234.249.69:8765",
            "oracle-atlanta": "http://173.230.131.178:8765",
            "ddgt-gateway": "http://45.56.120.132:8767",
        }
        for name, url in known_nodes.items():
            ok, lat, ver, details = self._probe(url, timeout=8)
            with self._lock:
                if name not in self._services:
                    self._services[name] = ServiceEndpoint(
                        name=name, url=url,
                        label=name.replace("-", " ").title(),
                        type="oracle",
                        trust="unknown",
                    )
                svc = self._services[name]
                changed = svc.healthy != ok
                svc.healthy = ok
                svc.latency_ms = lat
                svc.version = ver
                svc.details = details
                svc.last_seen = time.time()
                if changed:
                    self._log("health", f"'{name}' {'came online' if ok else 'went offline'} ({lat}ms)")

    def _scan_agents(self):
        if not self.receptor_enabled("agent"):
            return
        mkt_url = DEFAULT_POINTERS["vida-marketplace"]["url"]
        try:
            import urllib.request
            meetup_url = f"{mkt_url.rstrip('/')}/api/admin/meetups"
            with urllib.request.urlopen(urllib.request.Request(meetup_url), timeout=5) as resp:
                body = json.loads(resp.read().decode())
                meetups = body if isinstance(body, list) else body.get("meetups", [])
                for m in meetups:
                    agent_id = m.get("agent_id", m.get("id", "unknown"))
                    agent_url = m.get("url", m.get("endpoint", ""))
                    if agent_url:
                        name = f"agent-{agent_id[:12]}"
                        with self._lock:
                            if name not in self._services:
                                ok, lat, ver, details = self._probe(agent_url, timeout=3)
                                self._services[name] = ServiceEndpoint(
                                    name=name, url=agent_url,
                                    label=f"Agent {agent_id[:12]}",
                                    type="agent",
                                    trust="unknown",
                                    healthy=ok,
                                    latency_ms=lat,
                                    version=ver,
                                    details=details,
                                    last_seen=time.time(),
                                )
                                self._log("scan", f"Agent discovered: '{name}' at {agent_url}")
        except Exception:
            pass

    # ── Public API ──

    def scan(self):
        if not self._enabled:
            return
        if self._scanning:
            return
        self._scanning = True
        try:
            self._scan_pointers()
            self._scan_lan()
            self._scan_network()
            self._scan_agents()
            self._last_scan = time.time()
        finally:
            self._scanning = False

    def list_services(self, filter_type: str = "") -> list[dict]:
        with self._lock:
            services = list(self._services.values())
        results = []
        for s in services:
            if filter_type and s.type != filter_type:
                continue
            results.append({
                "name": s.name,
                "url": s.url,
                "label": s.label,
                "type": s.type,
                "trust": s.trust,
                "healthy": s.healthy,
                "latency_ms": s.latency_ms,
                "version": s.version,
                "connected": s.connected,
                "last_seen": datetime.fromtimestamp(s.last_seen, tz=timezone.utc).isoformat()
                if s.last_seen else "",
            })
        return sorted(results, key=lambda x: (not x["healthy"], x["name"]))

    def pending_approvals(self) -> list[dict]:
        with self._lock:
            return [{
                "name": a.service.name,
                "url": a.service.url,
                "label": a.service.label,
                "type": a.service.type,
                "created_at": datetime.fromtimestamp(a.created_at, tz=timezone.utc).isoformat(),
            } for a in self._approvals if not a.decided]

    def report(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(self._report[-limit:])

    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "policy": self._policy.value,
            "receptors": dict(self._receptors),
            "last_scan": datetime.fromtimestamp(self._last_scan, tz=timezone.utc).isoformat()
            if self._last_scan else "",
            "services_total": len(self._services),
            "pending_approvals": len(self.pending_approvals()),
            "connected": sum(1 for s in self._services.values() if s.connected),
            "trusted": sum(1 for s in self._services.values() if s.trust == "trusted"),
            "blocked": sum(1 for s in self._services.values() if s.trust == "blocked"),
        }

    def _log(self, category: str, message: str):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "message": message,
        }
        log.info("[%s] %s", category, message)
        with self._lock:
            self._report.append(entry)
            if len(self._report) > self._max_report:
                self._report = self._report[-self._max_report:]

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return ""


# ── Singleton ──

_discovery: Discovery | None = None


def get_discovery() -> Discovery:
    global _discovery
    if _discovery is None:
        _discovery = Discovery()
    return _discovery