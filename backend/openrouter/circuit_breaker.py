"""Circuit breaker pattern implementation."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from .config import CircuitBreakerConfig
from .exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitStats:
    """Statistics for a single circuit."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    When a service fails repeatedly, the circuit "opens" and
    subsequent requests fail fast without actually calling the service.
    After a timeout, the circuit moves to "half-open" state and
    allows a test request through.
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._circuits: Dict[str, CircuitStats] = {}
        self._lock = asyncio.Lock()

    def _get_circuit(self, key: str) -> CircuitStats:
        """Get or create circuit for a key."""
        if key not in self._circuits:
            self._circuits[key] = CircuitStats()
        return self._circuits[key]

    async def can_execute(self, key: str) -> bool:
        """
        Check if a request can proceed.

        Returns True if allowed, raises CircuitBreakerOpenError if not.
        """
        async with self._lock:
            circuit = self._get_circuit(key)

            if circuit.state == CircuitState.CLOSED:
                return True

            if circuit.state == CircuitState.OPEN:
                # Check if timeout has passed
                time_since_open = time.time() - circuit.last_state_change

                if time_since_open >= self.config.timeout:
                    # Move to half-open
                    circuit.state = CircuitState.HALF_OPEN
                    circuit.last_state_change = time.time()
                    circuit.success_count = 0
                    logger.info(f"Circuit {key}: OPEN -> HALF_OPEN")
                    return True
                else:
                    # Still open
                    remaining = self.config.timeout - time_since_open
                    raise CircuitBreakerOpenError(key, remaining)

            # Half-open: allow one request through
            return True

    async def record_success(self, key: str) -> None:
        """Record a successful request."""
        async with self._lock:
            circuit = self._get_circuit(key)

            if circuit.state == CircuitState.HALF_OPEN:
                circuit.success_count += 1

                if circuit.success_count >= self.config.success_threshold:
                    # Recovery confirmed, close circuit
                    circuit.state = CircuitState.CLOSED
                    circuit.failure_count = 0
                    circuit.success_count = 0
                    circuit.last_state_change = time.time()
                    logger.info(f"Circuit {key}: HALF_OPEN -> CLOSED (recovered)")

            elif circuit.state == CircuitState.CLOSED:
                # Reset failure count on success
                circuit.failure_count = 0

    async def record_failure(self, key: str) -> None:
        """Record a failed request."""
        async with self._lock:
            circuit = self._get_circuit(key)
            circuit.failure_count += 1
            circuit.last_failure_time = time.time()

            if circuit.state == CircuitState.HALF_OPEN:
                # Failed during test, back to open
                circuit.state = CircuitState.OPEN
                circuit.last_state_change = time.time()
                logger.warning(f"Circuit {key}: HALF_OPEN -> OPEN (test failed)")

            elif circuit.state == CircuitState.CLOSED:
                if circuit.failure_count >= self.config.failure_threshold:
                    # Too many failures, open circuit
                    circuit.state = CircuitState.OPEN
                    circuit.last_state_change = time.time()
                    logger.warning(
                        f"Circuit {key}: CLOSED -> OPEN "
                        f"({circuit.failure_count} failures)"
                    )

    def get_stats(self, key: str) -> Optional[CircuitStats]:
        """Get statistics for a circuit."""
        return self._circuits.get(key)

    def get_all_stats(self) -> Dict[str, CircuitStats]:
        """Get statistics for all circuits."""
        return dict(self._circuits)

    async def reset(self, key: str) -> None:
        """Manually reset a circuit to closed state."""
        async with self._lock:
            if key in self._circuits:
                self._circuits[key] = CircuitStats()
                logger.info(f"Circuit {key}: manually reset to CLOSED")

    async def reset_all(self) -> None:
        """Reset all circuits to closed state."""
        async with self._lock:
            self._circuits.clear()
            logger.info("All circuits reset to CLOSED")
