"""
TAO account records — schema + store.

Infrastructure only: no seed derivation, no key generation.
Owner-provisioned records can be stored later; agent code only reads public fields.
"""

from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class TaoAccountRecord:
    """Public account metadata for a Vida wallet's TAO side."""

    wallet_id: str
    network: str
    ss58_address: str = ""
    ss58_prefix: int = 42
    version: int = 1
    plugin: str = "tao"
    created_at: str = ""
    provisioned: bool = False
    # Filled only after owner derivation slice — never required for infra tests
    derivation_method: str = ""
    # Encrypted cold material blob (hex/json) — owner path only; agent must not need this
    enc_cold_material: Optional[dict[str, Any]] = None
    # ML-DSA-65 forward identity (public + encrypted secret) — not on-chain funds
    pq_public_key: Optional[str] = None
    enc_pq_sk: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        """Fields safe to show an agent / logs (no enc material)."""
        return {
            "version": self.version,
            "plugin": self.plugin,
            "wallet_id": self.wallet_id,
            "network": self.network,
            "ss58_address": self.ss58_address,
            "ss58_prefix": self.ss58_prefix,
            "created_at": self.created_at,
            "provisioned": self.provisioned,
            "derivation_method": self.derivation_method,
            "has_enc_cold_material": self.enc_cold_material is not None,
            "pq_ready": bool(self.pq_public_key and self.enc_pq_sk),
            "pq_public_key": self.pq_public_key,
            "pq_scheme": "ML-DSA-65" if self.pq_public_key else None,
            "pq_on_chain": False,
            "meta": dict(self.meta),
        }

    def to_storage_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaoAccountRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class TaoAccountStore:
    """
    Filesystem store for TAO account records.

    Default layout: {root}/{wallet_id}/tao_account.json (mode 0600)
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, wallet_id: str) -> Path:
        safe = wallet_id.replace("/", "_").replace("..", "_")
        return self.root / safe / "tao_account.json"

    def save(self, record: TaoAccountRecord) -> Path:
        path = self.path_for(record.wallet_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not record.created_at:
            record.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record.to_storage_dict(), indent=2, sort_keys=True))
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        tmp.replace(path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return path

    def load(self, wallet_id: str) -> Optional[TaoAccountRecord]:
        path = self.path_for(wallet_id)
        if not path.is_file():
            return None
        data = json.loads(path.read_text())
        return TaoAccountRecord.from_dict(data)

    def exists(self, wallet_id: str) -> bool:
        return self.path_for(wallet_id).is_file()

    def delete(self, wallet_id: str) -> bool:
        path = self.path_for(wallet_id)
        if path.is_file():
            path.unlink()
            return True
        return False
