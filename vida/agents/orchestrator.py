"""⚠️ Deprecated. The agent loop has been moved out of the wallet."""

import warnings

warnings.warn(
    "vida.agents.orchestrator is deprecated. The agent loop has been moved out of the wallet.",
    DeprecationWarning,
    stacklevel=2,
)
__all__ = []
