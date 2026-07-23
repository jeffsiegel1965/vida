"""⚠️ MOVED TO VIDA COMMERCE — vida_commerce/agent.py

Negotiation templates and strategies have moved to Vida Commerce.
The wallet no longer negotiates — that's the commerce layer's job.

See vida_commerce/negotiation.py for 5 cooperative strategies.
"""

import warnings

warnings.warn(
    "vida.agents.negotiation.models has moved to vida_commerce.negotiation",
    DeprecationWarning,
    stacklevel=2,
)
__all__ = []
