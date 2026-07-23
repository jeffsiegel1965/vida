"""⚠️ MOVED TO VIDA COMMERCE.

Agent negotiation and orchestrator have moved to the vida-commerce project.
This module remains for backward compatibility but should not be used for
new development.

See: https://github.com/Vida-Wallet/vida-commerce
     -> vida_commerce/negotiation.py  (5 cooperative strategies)
     -> vida_commerce/agent.py        (contract administrator loop)
"""

import warnings

warnings.warn(
    "vida.agents.negotiation has moved to vida-commerce. Import from vida_commerce.negotiation instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compat — will be removed in a future version.
# New code should use vida_commerce.negotiation directly.
__all__ = []
