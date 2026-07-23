"""⚠️ MOVED TO VIDA COMMERCE — vida_commerce/agent.py

Persistent deal/counterparty memory has moved to Vida Commerce.
See vida_commerce/agent.py → ContractMemory class.
"""

import warnings
warnings.warn(
    "vida.agents.memory has moved to vida_commerce.agent.ContractMemory",
    DeprecationWarning, stacklevel=2,
)
__all__ = []