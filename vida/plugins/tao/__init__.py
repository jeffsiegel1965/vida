"""Vida TAO (Bittensor) plugin rail — part of Vida, not a standalone wallet product.

Chain status (verified Jul 19, 2026):
- Finney mainnet: pre-dTAO. Uses add_stake/remove_stake for subnet access.
- dTAO: NOT deployed yet. When it arrives, payment model changes to subnet token swaps.
- 64 subnets active. All staking extrinsics verified against live chain.
"""

from .config import TaoNetwork, TaoConfig, load_tao_config
from .client import TaoNetworkClient, MockTaoClient, HealthInfo, BalanceInfo
from .accounts import TaoAccountRecord, TaoAccountStore
from .plugin import TaoPlugin
from .substrate_client import SubstrateTaoClient, make_tao_client
from .derive import derive_tao_keys, TaoDerivedKeys
from .provision import provision_tao_account, unlock_tao_secrets, ensure_tao_pq_identity, owner_sign_pq
from .pq import PQ_AVAILABLE, PQ_SCHEME, generate_pq_identity
from .tools import (
    vida_tao_status,
    vida_tao_balance,
    vida_tao_delegate,
    vida_tao_undelegate,
    vida_tao_transfer,
    vida_tao_optimize,
    vida_tao_session_info,
    tao_list_subnets,
    tao_subnet_info,
    tao_subnet_query,
    HERMES_TOOLS,
)
from .session import grant_tao_agent_session, revoke_tao_agent_session, load_tao_session_secrets

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
