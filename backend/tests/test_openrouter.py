"""Tests for OpenRouter client hardening."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.openrouter import (
    OpenRouterClient,
    OpenRouterConfig,
    RetryConfig,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitState,
    OpenRouterError,
    RateLimitError,
    ServerError,
    ModelNotFoundError,
    InvalidRequestError,
    CircuitBreakerOpenError,
)
from backend.openrouter.retry import calculate_delay, with_retry


class TestRetryConfig:
    """Tests for retry configuration."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_custom_config(self):
        """Custom config values are respected."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=2.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.initial_delay == 2.0
        assert config.jitter is False


class TestCalculateDelay:
    """Tests for delay calculation."""

    def test_exponential_backoff(self):
        """Delay increases exponentially."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        delay0 = calculate_delay(0, config)
        delay1 = calculate_delay(1, config)
        delay2 = calculate_delay(2, config)

        assert delay0 == 1.0  # 1 * 2^0
        assert delay1 == 2.0  # 1 * 2^1
        assert delay2 == 4.0  # 1 * 2^2

    def test_max_delay_cap(self):
        """Delay is capped at max_delay."""
        config = RetryConfig(initial_delay=1.0, max_delay=10.0, jitter=False)

        delay = calculate_delay(10, config)  # Would be 1024 without cap
        assert delay == 10.0

    def test_retry_after_respected(self):
        """Retry-After header is respected."""
        config = RetryConfig(initial_delay=1.0, max_delay=60.0, jitter=False)

        delay = calculate_delay(0, config, retry_after=30)
        assert delay == 30.0

    def test_retry_after_capped(self):
        """Retry-After is capped at max_delay."""
        config = RetryConfig(initial_delay=1.0, max_delay=10.0, jitter=False)

        delay = calculate_delay(0, config, retry_after=100)
        assert delay == 10.0

    def test_jitter_adds_randomness(self):
        """Jitter adds randomness to delays."""
        config = RetryConfig(initial_delay=10.0, jitter=True)

        delays = [calculate_delay(0, config) for _ in range(100)]

        # Should have some variation
        assert len(set(delays)) > 1
        # Should be within expected range (0.5 to 1.5 times base)
        assert all(5.0 <= d <= 15.0 for d in delays)


class TestCircuitBreaker:
    """Tests for circuit breaker."""

    @pytest.fixture
    def breaker(self):
        """Create circuit breaker with low thresholds for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=1.0,  # Short timeout for tests
        )
        return CircuitBreaker(config)

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, breaker):
        """Circuit starts in closed state."""
        assert await breaker.can_execute("test") is True
        stats = breaker.get_stats("test")
        assert stats.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_failures(self, breaker):
        """Circuit opens after threshold failures."""
        key = "test"

        # Record failures
        for _ in range(3):
            await breaker.record_failure(key)

        # Should be open now
        stats = breaker.get_stats(key)
        assert stats.state == CircuitState.OPEN

        # Should raise error
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.can_execute(key)

    @pytest.mark.asyncio
    async def test_success_resets_failures(self, breaker):
        """Success resets failure count."""
        key = "test"

        await breaker.record_failure(key)
        await breaker.record_failure(key)
        await breaker.record_success(key)

        stats = breaker.get_stats(key)
        assert stats.failure_count == 0
        assert stats.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, breaker):
        """Circuit moves to half-open after timeout."""
        key = "test"

        # Open the circuit
        for _ in range(3):
            await breaker.record_failure(key)

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Should allow request (half-open)
        assert await breaker.can_execute(key) is True
        stats = breaker.get_stats(key)
        assert stats.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_closes_after_successes(self, breaker):
        """Circuit closes after success threshold in half-open."""
        key = "test"

        # Open and wait for half-open
        for _ in range(3):
            await breaker.record_failure(key)
        await asyncio.sleep(1.1)
        await breaker.can_execute(key)  # Move to half-open

        # Record successes
        await breaker.record_success(key)
        await breaker.record_success(key)

        stats = breaker.get_stats(key)
        assert stats.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_half_open_failure(self, breaker):
        """Circuit reopens if failure during half-open."""
        key = "test"

        # Open and wait for half-open
        for _ in range(3):
            await breaker.record_failure(key)
        await asyncio.sleep(1.1)
        await breaker.can_execute(key)  # Move to half-open

        # Fail during half-open
        await breaker.record_failure(key)

        stats = breaker.get_stats(key)
        assert stats.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_manual_reset(self, breaker):
        """Circuit can be manually reset."""
        key = "test"

        # Open the circuit
        for _ in range(3):
            await breaker.record_failure(key)

        # Reset
        await breaker.reset(key)

        stats = breaker.get_stats(key)
        assert stats.state == CircuitState.CLOSED
        assert stats.failure_count == 0


class TestOpenRouterExceptions:
    """Tests for exception types."""

    def test_rate_limit_error(self):
        """RateLimitError has correct attributes."""
        err = RateLimitError(retry_after=30)
        assert err.status_code == 429
        assert err.retry_after == 30
        assert "30 seconds" in str(err)

    def test_model_not_found_error(self):
        """ModelNotFoundError includes model name."""
        err = ModelNotFoundError("openai/gpt-5")
        assert err.status_code == 404
        assert err.model == "openai/gpt-5"
        assert "gpt-5" in str(err)

    def test_server_error(self):
        """ServerError has correct defaults."""
        err = ServerError()
        assert err.status_code == 500
        assert "server error" in str(err).lower()

    def test_circuit_breaker_error(self):
        """CircuitBreakerOpenError includes model and reset time."""
        err = CircuitBreakerOpenError("openai/gpt-4", 45.5)
        assert err.model == "openai/gpt-4"
        assert err.reset_time == 45.5
        assert "45.5s" in str(err)


class TestOpenRouterClientConfig:
    """Tests for client configuration."""

    def test_default_config(self):
        """Default config is valid."""
        config = OpenRouterConfig()
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.default_temperature == 0.7
        assert config.default_max_tokens == 4096

    def test_timeout_config_defaults(self):
        """Timeout config has sensible defaults."""
        config = OpenRouterConfig()
        connect, read = config.timeout.get_timeout("any-model")
        assert connect == 10.0
        assert read == 120.0

    def test_timeout_config_overrides(self):
        """Timeout config allows per-model overrides."""
        from backend.openrouter.config import TimeoutConfig

        timeout = TimeoutConfig(
            connect_timeout=5.0,
            read_timeout=60.0,
            model_timeouts={"slow-model": (10.0, 300.0)},
        )

        # Default model
        connect, read = timeout.get_timeout("normal-model")
        assert connect == 5.0
        assert read == 60.0

        # Overridden model
        connect, read = timeout.get_timeout("slow-model")
        assert connect == 10.0
        assert read == 300.0


class TestWithRetryDecorator:
    """Tests for the @with_retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_without_retry(self):
        """Function succeeds on first try."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3))
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_server_error(self):
        """Function retries on ServerError."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3, initial_delay=0.01))
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ServerError("Temporary failure")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """Function raises after max retries exceeded."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=2, initial_delay=0.01))
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ServerError("Always fails")

        with pytest.raises(ServerError):
            await always_fails()

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_non_retryable_raises_immediately(self):
        """Non-retryable exceptions are raised immediately."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3))
        async def invalid_request():
            nonlocal call_count
            call_count += 1
            raise InvalidRequestError("Bad request")

        with pytest.raises(InvalidRequestError):
            await invalid_request()

        assert call_count == 1  # No retries
