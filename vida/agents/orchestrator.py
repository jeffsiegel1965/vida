"""⚠️ MOVED TO VIDA COMMERCE — vida_commerce/agent.py

The agent loop (goal → plan → execute → verify) has moved to Vida Commerce.
The contract administrator agent handles contract lifecycle, negotiation, and memory.

Import from vida_commerce.agent instead:
    from vida_commerce.agent import ContractAdminAgent

This file remains as a forwarding notice only. No functionality.
"""

import warnings

warnings.warn(
    "vida.agents.orchestrator has moved to vida_commerce.agent",
    DeprecationWarning,
    stacklevel=2,
)
__all__ = []
