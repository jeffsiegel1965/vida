"""
Known TN10 covenant proofs (read-only metadata).

Does not load private keys. Does not broadcast.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Canonical micro-proof from 2026-07-14 kascov-lab run (testnet-10).
TN10_MICROPROOF: dict[str, Any] = {
    "network": "testnet-10",
    "date": "2026-07-14",
    "covenant_id": "9fe45342dc674e7cb2fd70061cb51746d47e4fba228a5c0861a8b6748790204f",
    "txs": {
        "genesis": "42f13ec89e5c996091c5be0f7d7cb5c2e9cb1a18c4b7de2f7e723950a77c34fe",
        "transition": "bf0d2c826da11f1b426dccbe61895cf15d18700e4ad4caf4e15e3674f2a511ef",
        "burn": "6dbe577adb05afd4afc34c31475b558d52adee78323a2ebf44f72260993266d6",
    },
    "funding_outpoint": "769bb4a73a20bfbe8e9dee098820e9ff1606e6b158dc2336f2d00d66fb606170:8",
    "funder_address": "kaspatest:qplmcgy7gvgvsjrcmvphwnasu577y8agpe3crtl0zwna9h34dadeg8f024trj",
    "tooling": "kascov-lab (rusty-kaspa pin 98a4ccd…); not PyPI kaspa 2.0.1",
    "doc": "docs/proofs/covenant_tn10_microproof.md",
    "claim": (
        "Own TN10 covenant lifecycle (genesis→transition→burn) accepted. "
        "Does not mean Vida plugin live deploy is enabled."
    ),
}


def tn10_microproof() -> dict[str, Any]:
    """Return a copy of the embedded micro-proof record."""
    import copy

    return copy.deepcopy(TN10_MICROPROOF)


def proof_doc_exists(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[3]
    return (root / "docs" / "proofs" / "covenant_tn10_microproof.md").is_file()
