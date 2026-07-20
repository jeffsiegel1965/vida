"""Vida TAO (Bittensor) plugin rail — part of Vida, not a standalone wallet product.

Chain status (verified Jul 19, 2026):
- Finney mainnet: pre-dTAO. Uses add_stake/remove_stake for subnet access.
- dTAO: NOT deployed yet. When it arrives, payment model changes to subnet token swaps.
- 64 subnets active. All staking extrinsics verified against live chain.
"""

from .accounts import TaoAccountRecord, TaoAccountStore
from .client import BalanceInfo, HealthInfo, MockTaoClient, TaoNetworkClient
from .config import TaoConfig, TaoNetwork, load_tao_config
from .derive import TaoDerivedKeys, derive_tao_keys
from .plugin import TaoPlugin
from .pq import PQ_AVAILABLE, PQ_SCHEME, generate_pq_identity  # noqa: F401 — API surface
from .provision import ensure_tao_pq_identity, owner_sign_pq, provision_tao_account, unlock_tao_secrets
from .session import (  # noqa: F401 — API surface
    grant_tao_agent_session,
    load_tao_session_secrets,
    revoke_tao_agent_session,
)
from .substrate_client import SubstrateTaoClient, make_tao_client
from .tools import (
    HERMES_TOOLS,
    tao_list_subnets,
    tao_subnet_info,
    tao_subnet_query,
    vida_tao_balance,
    vida_tao_delegate,
    vida_tao_optimize,
    vida_tao_session_info,
    vida_tao_status,
    vida_tao_transfer,
    vida_tao_undelegate,
)

__all__ = [
    "TaoNetwork",
    "TaoConfig",
    "load_tao_config",
    "TaoNetworkClient",
    "MockTaoClient",
    "HealthInfo",
    "BalanceInfo",
    "TaoAccountRecord",
    "TaoAccountStore",
    "TaoPlugin",
    "SubstrateTaoClient",
    "make_tao_client",
    "derive_tao_keys",
    "TaoDerivedKeys",
    "provision_tao_account",
    "unlock_tao_secrets",
    "ensure_tao_pq_identity",
    "owner_sign_pq",
    "PQ_AVAILABLE",
    "PQ_SCHEME",
    "vida_tao_status",
    "vida_tao_balance",
    "grant_tao_agent_session",
    "revoke_tao_agent_session",
    "vida_tao_delegate",
    "vida_tao_undelegate",
    "vida_tao_transfer",
    "vida_tao_optimize",
    "vida_tao_session_info",
    "tao_list_subnets",
    "tao_subnet_info",
    "tao_subnet_query",
    "HERMES_TOOLS",
]
