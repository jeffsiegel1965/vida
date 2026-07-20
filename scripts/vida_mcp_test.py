#!/usr/bin/env python3
"""Quick test for Vida MCP server — validates it starts and lists tools."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(ROOT / ".venv" / "bin" / "python")
SERVER = str(ROOT / "scripts" / "vida_mcp_server.py")

proc = subprocess.Popen(
    [PYTHON, SERVER],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

init = json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}})
notif = json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})
list_tools = json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/list"})

out, err = proc.communicate(input=f"{init}\n{notif}\n{list_tools}\n", timeout=10)

for line in out.strip().splitlines():
    try:
        d = json.loads(line)
        if "result" in d and "tools" in d["result"]:
            tools = d["result"]["tools"]
            print(f"OK — {len(tools)} tools:")
            for t in tools:
                print(f"  {t['name']}: {t['description'][:80]}")
    except:
        pass

proc.kill()
