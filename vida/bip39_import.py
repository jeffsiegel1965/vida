"""
BIP39 wallet import/export — recover and export Vida wallets using standard mnemonics.

Supports:
- Kaspa standard derivation: m/44'/111111'/0'/0/0 (Vida default)
- Kasware derivation: m/44'/111111'/0'/0/{index}
- Ledger derivation: m/44'/111111'/{account}'/0/{index} or m/44'/111111'/0'/{account}/{index}

Usage:
    # Import from Kasware mnemonic:
    python scripts/import_wallet.py --mnemonic "twenty four words" --source kasware

    # Import from Ledger:
    python scripts/import_wallet.py --mnemonic "twenty four words" --source ledger --account 0

    # Export current wallet address (verify):
    python scripts/import_wallet.py --wallet vida_secure.json --show-address
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# ── Derivation paths ──

DERIVATION_PATHS = {
    "vida": "m/44'/111111'/0'/0/0",
    "kasware": "m/44'/111111'/0'/0/{index}",
    "ledger": "m/44'/111111'/{account}'/0/{index}",
    "ledger_alt": "m/44'/111111'/0'/{account}/{index}",
    "kaspa_cli": "m/44'/111111'/0'/0/0",  # same as Vida
}


def derive_address(
    mnemonic: str,
    path: str = "m/44'/111111'/0'/0/0",
    index: int = 0,
    account: int = 0,
    network: str = "mainnet",
) -> dict:
    """Derive a Kaspa address from a BIP39 mnemonic and derivation path.

    Args:
        mnemonic: 24-word BIP39 mnemonic phrase.
        path: Derivation path template with {index} and {account} placeholders.
        index: Address index for the path.
        account: Account number for Ledger paths.
        network: 'mainnet' or 'testnet-10'.

    Returns:
        {"ok": True, "address": str, "public_key": str, "derivation_path": str}
    """
    from kaspa import Mnemonic, NetworkType, PrivateKey, XPrv

    try:
        # Validate mnemonic
        seed = Mnemonic.to_seed(mnemonic.strip())
    except ValueError as e:
        return {"ok": False, "error": f"Invalid mnemonic: {e}"}

    try:
        # Resolve the derivation path
        resolved_path = path.format(index=index, account=account)

        # Derive private key
        xprv = XPrv.from_seed(seed)
        derived = xprv.derive_path(resolved_path)
        priv_key = PrivateKey(derived.private_key_bytes().hex())

        # Derive address
        net = NetworkType.Mainnet if network == "mainnet" else NetworkType.Testnet
        addr = priv_key.to_address(net)
        pub_key = priv_key.to_public_key()

        return {
            "ok": True,
            "address": str(addr),
            "public_key": pub_key.to_string(),
            "derivation_path": resolved_path,
        }
    except Exception as e:
        return {"ok": False, "error": f"Derivation failed: {e}"}


def import_wallet(
    mnemonic: str,
    output_path: str,
    password: str,
    source: str = "vida",
    account: int = 0,
    index: int = 0,
    network: str = "mainnet",
) -> dict:
    """Import a wallet from a BIP39 mnemonic into Vida's encrypted format.

    Args:
        mnemonic: 24-word BIP39 phrase.
        output_path: Where to save the vida_secure.json file.
        password: Password to encrypt the wallet with.
        source: 'vida', 'kasware', or 'ledger'.
        account: Account number (for Ledger import).
        index: Address index (for Kasware multi-address import).
        network: 'mainnet' or 'testnet-10'.

    Returns:
        {"ok": True, "address": str, "path": str}
    """
    from vida.secure_wallet import create_secure_wallet

    path = DERIVATION_PATHS.get(source, DERIVATION_PATHS["vida"])

    # First derive the address to verify
    result = derive_address(mnemonic, path, index=index, account=account, network=network)
    if not result["ok"]:
        return result

    # Create encrypted wallet
    try:
        wallet_result = create_secure_wallet(
            output_path,
            password,
            network=network,
            mnemonic_phrase=mnemonic,  # Use the imported mnemonic directly
        )
        return {
            "ok": True,
            "address": wallet_result["address"],
            "path": output_path,
            "derivation_path": result["derivation_path"],
            "source": source,
        }
    except FileExistsError:
        return {"ok": False, "error": f"Wallet file already exists at {output_path}. Use --overwrite to replace."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def show_wallet_address(wallet_path: str, password: Optional[str] = None) -> dict:
    """Display the address and metadata from an existing wallet file.

    Args:
        wallet_path: Path to vida_secure.json.
        password: Optional password to decrypt and verify.

    Returns:
        {"ok": True, "address": str, "network": str, "has_pq": bool}
    """
    from vida.secure_wallet import SecureVida

    p = Path(wallet_path)
    if not p.is_file():
        return {"ok": False, "error": f"Wallet file not found: {wallet_path}"}

    try:
        with open(p) as f:
            data = json.load(f)

        info = {
            "ok": True,
            "address": data.get("address", "unknown"),
            "network": data.get("network", "unknown"),
            "has_pq": "pq_public_key" in data,
            "version": data.get("version", 1),
        }

        # Verify with password if provided
        if password:
            try:
                w = SecureVida(wallet_path, password=password)
                info["unlocked"] = True
                info["derivation_path"] = DERIVATION_PATHS["vida"]
                w.lock()
            except ValueError as e:
                info["unlocked"] = False
                info["unlock_error"] = str(e)

        return info
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_derivation_paths() -> dict:
    """Return all supported derivation paths with descriptions."""
    return {
        "vida": {"path": "m/44'/111111'/0'/0/0", "description": "Vida default (single address)"},
        "kasware": {"path": "m/44'/111111'/0'/0/{index}", "description": "Kasware (multi-address, per-index)"},
        "ledger": {"path": "m/44'/111111'/{account}'/0/{index}", "description": "Ledger (account-based)"},
        "ledger_alt": {"path": "m/44'/111111'/0'/{account}/{index}", "description": "Ledger alternate (flat account)"},
        "kaspa_cli": {"path": "m/44'/111111'/0'/0/0", "description": "Kaspa CLI / KDX (same as Vida default)"},
    }


# ── CLI ──

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vida BIP39 wallet import/export")
    sub = parser.add_subparsers(dest="command")

    # import subcommand
    imp = sub.add_parser("import", help="Import wallet from mnemonic")
    imp.add_argument("--mnemonic", required=True, help="24-word BIP39 mnemonic")
    imp.add_argument("--source", default="vida", choices=["vida", "kasware", "ledger"], help="Wallet source")
    imp.add_argument("--account", type=int, default=0, help="Account number (Ledger)")
    imp.add_argument("--index", type=int, default=0, help="Address index (Kasware)")
    imp.add_argument("--network", default="mainnet", choices=["mainnet", "testnet-10"])
    imp.add_argument("--output", default="vida_secure.json", help="Output wallet file path")
    imp.add_argument("--password", required=True, help="Encryption password")
    imp.add_argument("--overwrite", action="store_true", help="Overwrite existing wallet file")

    # show subcommand
    show = sub.add_parser("show", help="Show wallet address info")
    show.add_argument("--wallet", default="vida_secure.json", help="Path to wallet file")
    show.add_argument("--password", default=None, help="Optional password for decryption test")

    # paths subcommand
    sub.add_parser("paths", help="List supported derivation paths")

    args = parser.parse_args()

    if args.command == "import":
        result = import_wallet(
            mnemonic=args.mnemonic,
            output_path=args.output,
            password=args.password,
            source=args.source,
            account=args.account,
            index=args.index,
            network=args.network,
        )
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["ok"] else 1)

    elif args.command == "show":
        result = show_wallet_address(args.wallet, args.password)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["ok"] else 1)

    elif args.command == "paths":
        paths = list_derivation_paths()
        print("Supported derivation paths:\n")
        for name, info in paths.items():
            print(f"  {name:15s} {info['path']:50s} {info['description']}")

    else:
        parser.print_help()
