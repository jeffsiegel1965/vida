#!/usr/bin/env python3
"""
Vida Wallet Setup — RUN THIS YOURSELF in a terminal. Do not run through an AI agent.

    python scripts/setup_owner_wallet.py      # from the repo root, inside your venv

What it does:
  1. Asks you to choose a password (typed hidden, never shown)
  2. Generates a 24-word seed phrase and shows it ONCE on your screen
  3. Writes the encrypted wallet file (useless without your password)
  4. Verifies the wallet unlocks and shows its receive address

WRITE THE 24 WORDS ON PAPER. They are the master backup for your funds.
Anyone with the words has your money. No one without them (or your
password + wallet file) can touch it.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'vida'))
from secure_wallet import create_secure_wallet, SecureVida

WALLET = Path(__file__).resolve().parent.parent / "vida_secure.json"


def main():
    print("=" * 64)
    print("  VIDA SECURE WALLET SETUP (owner-only)")
    print("=" * 64)

    if WALLET.exists():
        print(f"\nERROR: {WALLET} already exists.")
        print("Refusing to overwrite. Move or delete it first (make sure any")
        print("funds are recovered elsewhere before deleting).")
        sys.exit(1)

    restore = input("\nRestore from an existing 24-word phrase? [y/N]: ").strip().lower()
    phrase = None
    if restore == "y":
        phrase = getpass.getpass("Paste your 24 words (input hidden): ").strip()
        if len(phrase.split()) != 24:
            print("ERROR: that was not 24 words.")
            sys.exit(1)

    while True:
        pw = getpass.getpass("\nChoose a password (min 10 chars, input hidden): ")
        if len(pw) < 10:
            print("Too short — 10 characters minimum.")
            continue
        pw2 = getpass.getpass("Type it again: ")
        if pw != pw2:
            print("Passwords do not match, try again.")
            continue
        break

    print("\nCreating encrypted wallet (scrypt is intentionally slow, ~1-2s)...")
    result = create_secure_wallet(WALLET, pw, network="mainnet", mnemonic_phrase=phrase)

    print("\n" + "=" * 64)
    if phrase is None:
        print("  YOUR 24-WORD SEED PHRASE — WRITE IT DOWN NOW, ON PAPER:")
        print("=" * 64 + "\n")
        words = result["mnemonic"].split()
        for i in range(0, 24, 4):
            print("   " + "  ".join(f"{n+1:>2}.{w}" for n, w in enumerate(words[i:i+4], start=i)))
        print("\n" + "=" * 64)
        print("  This is shown ONCE. It is NOT saved anywhere in plaintext.")
    else:
        print("  Wallet RESTORED from your existing phrase.")
    print("=" * 64)

    print(f"\nReceive address : {result['address']}")
    print(f"PQ identity     : {'ready (ML-DSA-65)' if result['pq_public_key'] else 'UNAVAILABLE'}")
    print(f"Encrypted file  : {WALLET}")

    # Verify unlock round-trip before declaring success
    print("\nVerifying wallet unlocks with your password...")
    w = SecureVida(WALLET, password=pw)
    sig = w.sign("setup-verification")
    ok = w.verify("setup-verification", sig)
    w.lock()
    print(f"Unlock + sign + verify: {'OK' if ok else 'FAILED'}")
    if not ok:
        sys.exit(1)

    print("\nDone. To let the agent spend autonomously (with limits), run:")
    print("  python scripts/grant_session.py")
    print("\nOptional — support Vida development with KAS:")
    print("  kaspa:qqnnn7wlwz92a70v7km4j3c74lgvnymc60rl2p4gza7dgu6l4pv8g0560yzzn")


if __name__ == "__main__":
    main()
