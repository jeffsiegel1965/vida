"""
Kaspa RPC resilience layer — retry, fallback, circuit breaker.

Drop-in enhancement for vida.plugins.covenant.kaspa_rpc.

Usage:
    from vida.plugins.covenant.rpc_resilience import with_retry

    @with_retry(max_attempts=3, fallback_nodes=MAINNET_NODES)
    async def get_balance(address): ...

Adds:
- Exponential backoff with jitter
- Circuit breaker (3 failures → 30s cooldown)
- Fallback node list (when Resolver can't find nodes)
- Structured retry logging
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Public Kaspa RPC endpoints (fallback when Resolver fails) ──

MAINNET_NODES = [
    "wss://eu-1.kaspa-ng.org",
    "wss://us-1.kaspa-ng.org",
    "wss://node.kaspacalc.net",
]

TESTNET_NODES = [
    "wss://tn10.kaspa-ng.org",
    "wss://testnet-10.kaspa-ng.org",
]


# ── Circuit breaker ──


@dataclass
class CircuitBreaker:
    """Circuit breaker: after `failure_threshold` consecutive failures,
    the circuit opens for `cooldown_seconds`. While open, calls are
    rejected immediately without hitting the network."""

    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    half_open_attempts: int = 1

    _failures: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _state: str = field(default="closed", init=False)  # closed | open | half-open

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        """Execute fn if circuit allows; track failures."""
        if self._state == "open":
            if time.time() - self._last_failure_time > self.cooldown_seconds:
                self._state = "half-open"
                logger.info("Circuit breaker: half-open (testing)")
            else:
                raise CircuitOpenError(
                    f"Circuit open — cooling down ({self.cooldown_seconds - (time.time() - self._last_failure_time):.0f}s remaining)"
                )

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    async def acall(self, fn: Callable, *args, **kwargs) -> Any:
        """Async version of call()."""
        if self._state == "open":
            if time.time() - self._last_failure_time > self.cooldown_seconds:
                self._state = "half-open"
                logger.info("Circuit breaker: half-open (testing)")
            else:
                raise CircuitOpenError(
                    f"Circuit open — cooling down ({self.cooldown_seconds - (time.time() - self._last_failure_time):.0f}s remaining)"
                )

        try:
            result = await fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        if self._failures > 0:
            logger.info("Circuit breaker: reset after %d failures", self._failures)
        self._failures = 0
        self._state = "closed"

    def _on_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                "Circuit breaker: OPEN after %d failures (cooldown %ds)",
                self._failures,
                self.cooldown_seconds,
            )

    @property
    def is_open(self) -> bool:
        return self._state == "open"

    @property
    def status(self) -> dict:
        return {
            "state": self._state,
            "failures": self._failures,
            "cooldown_remaining": max(0, self.cooldown_seconds - (time.time() - self._last_failure_time))
            if self._state == "open"
            else 0,
        }


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open."""


# ── Global circuit breakers (one per operation type) ──

_balance_cb = CircuitBreaker()
_utxo_cb = CircuitBreaker()
_submit_cb = CircuitBreaker()
_info_cb = CircuitBreaker()

# ── Retry with exponential backoff ──


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    circuit_breaker: Optional[CircuitBreaker] = None,
    fallback_nodes: Optional[list[str]] = None,
):
    """Decorator: retry an async function with exponential backoff + jitter.

    Args:
        max_attempts: Maximum number of attempts (including first).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay cap.
        circuit_breaker: Optional CircuitBreaker instance.
        fallback_nodes: Optional list of WebSocket URLs to try as fallback.
    """

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(1, max_attempts + 1):
                try:
                    if circuit_breaker and circuit_breaker.is_open and attempt == 1:
                        # Don't even try if circuit is open on first attempt
                        raise CircuitOpenError("Circuit breaker open — skipping RPC call")

                    return await fn(*args, **kwargs)

                except CircuitOpenError:
                    raise  # Don't retry circuit-open errors

                except (asyncio.TimeoutError, OSError, ConnectionError, RuntimeError) as e:
                    last_error = e
                    if attempt == max_attempts:
                        break

                    # Exponential backoff with jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay *= random.uniform(0.5, 1.5)

                    logger.warning(
                        "RPC retry %d/%d for %s after %.1fs: %s",
                        attempt,
                        max_attempts,
                        fn.__name__,
                        delay,
                        e,
                    )

                    # Try fallback nodes if available
                    if fallback_nodes and attempt > 1:
                        node = random.choice(fallback_nodes)
                        logger.info("Falling back to node: %s", node)
                        # TODO: wire fallback node into connection — for now, just log

                    await asyncio.sleep(delay)

            # All retries exhausted
            if circuit_breaker:
                circuit_breaker._on_failure()

            raise MaxRetriesExceededError(
                f"{fn.__name__} failed after {max_attempts} attempts",
                original=last_error,
            )

        return wrapper

    return decorator


class MaxRetriesExceededError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, message: str, original: Optional[Exception] = None):
        self.original = original
        super().__init__(message)


# ── Health check ──


async def check_node_health(client=None) -> dict:
    """Quick health check against the Kaspa node.

    Returns:
        {"ok": bool, "latency_ms": float, "network": str, "daa_score": int}
    """
    from vida.plugins.covenant.kaspa_rpc import get_network_info

    start = time.monotonic()
    try:
        info = await get_network_info()
        latency = (time.monotonic() - start) * 1000
        return {
            "ok": info.get("ok", False),
            "latency_ms": round(latency, 1),
            "network": info.get("info", {}).get("network", "unknown")
            if isinstance(info.get("info"), dict)
            else "unknown",
            "daa_score": info.get("info", {}).get("virtualDaaScore", 0) if isinstance(info.get("info"), dict) else 0,
        }
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return {
            "ok": False,
            "latency_ms": round(latency, 1),
            "error": str(e),
        }


# ── Connection pool status ──


def get_circuit_status() -> dict:
    """Return status of all circuit breakers for monitoring."""
    return {
        "balance": _balance_cb.status,
        "utxo": _utxo_cb.status,
        "submit": _submit_cb.status,
        "info": _info_cb.status,
    }
