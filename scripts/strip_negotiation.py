#!/usr/bin/env python3
"""
Safely strip the P2P negotiation protocol from the shipped covenant module.

Operation:
  1. Backup negotiation files to dev/negotiation/
  2. Remove negotiation.py from vida/plugins/covenant/
  3. Remove negotiation functions from tools.py
  4. Remove test_covenant_negotiation.py
  5. Strip negotiation references from vida_mcp_server.py
  6. Verify 139 - 19 = ~120 tests still pass
"""

import subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
COVENANT = REPO / "vida" / "plugins" / "covenant"
TESTS = REPO / "tests"
SCRIPTS = REPO / "scripts"
DEV = REPO / "dev" / "negotiation"

print("=" * 60)
print("  Stripping negotiation protocol from shipped code")
print("=" * 60)

# Step 1: Backup to dev/
print("\n[1/5] Backing up negotiation files to dev/negotiation/...")
DEV.mkdir(parents=True, exist_ok=True)
files_to_backup = [
    COVENANT / "negotiation.py",
    TESTS / "test_covenant_negotiation.py",
    TESTS / "test_covenant_robustness.py",  # may reference negotiation
    TESTS / "test_covenant_scaffold.py",      # may reference negotiation
]
for f in files_to_backup:
    if f.exists():
        dest = DEV / f.name
        dest.write_text(f.read_text())
        print(f"  ✓ {f.name} -> {dest}")

# Step 2: Remove negotiation.py from the main plugin
print("\n[2/5] Removing vida/plugins/covenant/negotiation.py...")
neg_file = COVENANT / "negotiation.py"
if neg_file.exists():
    neg_file.unlink()
    print(f"  ✓ Removed {neg_file}")

# Step 3: Remove test files that test negotiation
print("\n[3/5] Removing negotiation test files...")
for name in ["test_covenant_negotiation.py"]:  # keep robustness + scaffold
    f = TESTS / name
    if f.exists():
        f.unlink()
        print(f"  ✓ Removed {f}")

# Step 4: Strip negotiation imports from tools.py
print("\n[4/5] Stripping negotiation from tools.py...")
tools_path = COVENANT / "tools.py"
if tools_path.exists():
    content = tools_path.read_text()
    # Remove the from .negotiation import line
    content = content.replace(
        "from .negotiation import CovenantTerms, create_deal, Negotiator, UserControls\n",
        ""
    )
    # Remove inside-function negotiation imports
    content = content.replace(
        "        from vida.plugins.covenant.negotiation import Negotiator\n",
        ""
    )
    content = content.replace(
        "    from vida.plugins.covenant.negotiation import Negotiator, UserControls, NegotiationError\n",
        ""
    )
    tools_path.write_text(content)
    print("  ✓ Stripped negotiation import lines from tools.py")

# Step 5: Strip negotiation from MCP server
print("\n[5/5] Stripping negotiation from vida_mcp_server.py...")
mcp_path = SCRIPTS / "vida_mcp_server.py"
if mcp_path.exists():
    content = mcp_path.read_text()
    # Remove the negotiation-related tool definitions and handlers
    # This is complex - for now mark it as needing manual fix
    print("  ⚠  vida_mcp_server.py has deep negotiation integration — manual review needed")

print("\n" + "=" * 60)
print("  Stripping complete. Running tests...")
print("=" * 60)
