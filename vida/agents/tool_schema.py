"""OpenAI-compatible function calling schema for Vida tools.

Makes every Vida covenant tool discoverable by LLM agents.
Format matches OpenAI function calling spec so it works with
any agent framework (LangChain, AutoGPT, custom orchestrators).

Usage:
    from vida.agents.tool_schema import TOOL_SCHEMA, TOOL_MAP
    # Give TOOL_SCHEMA to any LLM as available functions
    # Use TOOL_MAP to dispatch calls back to Vida
"""

from __future__ import annotations

from typing import Any

# ── Tool schema (OpenAI function calling format) ──

TOOL_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "covenant_status",
            "description": "Check the status of the covenant module: gates, kascov-lab availability, key balance",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_describe",
            "description": "Get a human-readable description of every covenant contract available",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_live_gates",
            "description": "Check whether live covenant deployment is enabled (env vars, binary path, key file)",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_plan_pot",
            "description": "Plan an agent pot: calculate funding amount based on per-tx and per-day spending limits",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_kas_per_tx": {
                        "type": "number",
                        "description": "Max KAS per transaction",
                    },
                    "max_kas_per_day": {
                        "type": "number",
                        "description": "Max KAS per day",
                    },
                    "allowed_destinations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of allowed destination addresses",
                    },
                },
                "required": ["max_kas_per_tx", "max_kas_per_day"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_spend_policy_check",
            "description": "Validate a planned spend against the pot's policy: max_tx, allowed destinations, network",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount in KAS"},
                    "destination": {"type": "string", "description": "Destination address"},
                    "wallet_id": {"type": "string", "description": "Pot wallet ID"},
                },
                "required": ["amount", "destination", "wallet_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_kascov_verify",
            "description": "Verify a covenant on the kascov explorer",
            "parameters": {
                "type": "object",
                "properties": {
                    "covenant_id": {"type": "string", "description": "Covenant ID to verify"},
                },
                "required": ["covenant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_quine_info",
            "description": "Get information about the QuineAgentPot SilverScript contract",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kaspa_balance",
            "description": "Check the KAS balance for a wallet address via the Kaspa REST API",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Kaspa address (optional, defaults to configured wallet)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kaspa_send",
            "description": "Send KAS to a destination address. Requires a session with sufficient caps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount in KAS"},
                    "destination": {"type": "string", "description": "Destination Kaspa address"},
                },
                "required": ["amount", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_kascov_search",
            "description": "Search covenants by name, id, or transaction",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_kascov_address",
            "description": "Check which covenants an address controls",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Kaspa address"},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_kascov_live",
            "description": "Check the kascov explorer live feed for recent covenant activity",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_validate_pot",
            "description": "Verify policy template hash integrity for a pot plan",
            "parameters": {
                "type": "object",
                "properties": {
                    "template": {"type": "object", "description": "Policy template dict"},
                },
                "required": ["template"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_estimate_fee",
            "description": "Estimate network fees for covenant fund or spend transactions",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["fund", "spend"], "description": "Transaction type"},
                    "amount": {"type": "number", "description": "Amount in KAS"},
                },
                "required": ["type", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_fee_schedule",
            "description": "Get the full fee structure for covenant operations",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "covenant_plan_with_fees",
            "description": "Plan an agent pot with detailed fee breakdown",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_kas_per_tx": {"type": "number", "description": "Max KAS per transaction"},
                    "max_kas_per_day": {"type": "number", "description": "Max KAS per day"},
                },
                "required": ["max_kas_per_tx", "max_kas_per_day"],
            },
        },
    },
]

# ── Tool dispatch map ──
# Maps tool names to their implementation. No aliases — every name maps to a real function.

TOOL_MAP: dict[str, str] = {
    "covenant_status": "covenant_status",
    "covenant_describe": "covenant_describe",
    "covenant_live_gates": "covenant_live_gates",
    "covenant_plan_pot": "covenant_plan_pot",
    "covenant_spend_policy_check": "covenant_spend_policy_check",
    "covenant_kascov_verify": "covenant_kascov_verify",
    "covenant_kascov_search": "covenant_kascov_search",
    "covenant_kascov_address": "covenant_kascov_address",
    "covenant_kascov_live": "covenant_kascov_live",
    "covenant_validate_pot": "covenant_validate_pot",
    "covenant_estimate_fee": "covenant_estimate_fee",
    "covenant_fee_schedule": "covenant_fee_schedule",
    "covenant_plan_with_fees": "covenant_plan_with_fees",
    "covenant_quine_info": "covenant_quine_info",
    "kaspa_balance": "kaspa_balance",
    "kaspa_send": "kaspa_send",
}
