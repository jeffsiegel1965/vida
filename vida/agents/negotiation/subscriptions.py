"""⚠️ MOVED TO VIDA COMMERCE — vida_commerce/agent.py

Subscription management has moved to Vida Commerce.
See vida_commerce/agent.py for contract lifecycle management.
"""

import warnings

warnings.warn(
    "vida.agents.negotiation.subscriptions has moved to vida_commerce",
    DeprecationWarning,
    stacklevel=2,
)
__all__ = []
