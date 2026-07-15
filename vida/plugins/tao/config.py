"""TAO plugin configuration — networks, endpoints, env overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaoNetwork(str, Enum):
    FINNEY = "finney"
    TEST = "test"
    MOCK = "mock"


# Defaults — overridable; not a promise that every endpoint is always up.
DEFAULT_ENDPOINTS: dict[TaoNetwork, list[str]] = {
    TaoNetwork.FINNEY: [
        "wss://entrypoint-finney.opentensor.ai:443",
        "wss://entrypoint-finney.io",
    ],
    TaoNetwork.TEST: [
        "wss://test.finney.opentensor.ai:443",
    ],
    TaoNetwork.MOCK: [],
}

# Bittensor / generic Substrate SS58 prefix commonly used on Finney.
DEFAULT_SS58_PREFIX = 42


@dataclass
class TaoConfig:
    network: TaoNetwork = TaoNetwork.MOCK
    endpoints: list[str] = field(default_factory=list)
    ss58_prefix: int = DEFAULT_SS58_PREFIX
    # Optional single override (wins over list)
    endpoint_override: Optional[str] = None
    request_timeout_sec: float = 30.0

    def resolved_endpoints(self) -> list[str]:
        if self.endpoint_override:
            return [self.endpoint_override]
        if self.endpoints:
            return list(self.endpoints)
        return list(DEFAULT_ENDPOINTS.get(self.network, []))


def load_tao_config(
    network: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> TaoConfig:
    """
    Load config from args + environment.

    Env:
      VIDA_TAO_NETWORK = finney | test | mock
      VIDA_TAO_ENDPOINT = wss://...
    """
    net_raw = (network or os.environ.get("VIDA_TAO_NETWORK") or "mock").strip().lower()
    try:
        net = TaoNetwork(net_raw)
    except ValueError as e:
        raise ValueError(
            f"unknown TAO network '{net_raw}' (use finney|test|mock)"
        ) from e

    ep = endpoint or os.environ.get("VIDA_TAO_ENDPOINT") or None
    return TaoConfig(
        network=net,
        endpoints=list(DEFAULT_ENDPOINTS.get(net, [])),
        endpoint_override=ep,
        ss58_prefix=DEFAULT_SS58_PREFIX,
    )
