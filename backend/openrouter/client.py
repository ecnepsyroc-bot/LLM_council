"""Robust OpenRouter HTTP client."""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .circuit_breaker import CircuitBreaker
from .config import OpenRouterConfig, RetryConfig
from .exceptions import (
    CircuitBreakerOpenError,
    InvalidRequestError,
    ModelNotFoundError,
    OpenRouterConnectionError,
    OpenRouterError,
    OpenRouterTimeoutError,
    RateLimitError,
    ServerError,
)
from .retry import RetryableOperation

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """
    Robust HTTP client for OpenRouter API.

    Features:
    - Retry with exponential backoff
    - Circuit breaker per model
    - Rate limit detection and respect
    - Configurable timeouts
    - Comprehensive error handling
    - Request/response logging
    """

    def __init__(self, config: Optional[OpenRouterConfig] = None):
        self.config = config or OpenRouterConfig()
        self.circuit_breaker = CircuitBreaker(self.config.circuit_breaker)

        # HTTP client will be created per-request for proper async handling
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://llm-council.local",
                    "X-Title": "LLM Council",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _handle_response_error(self, response: httpx.Response, model: str) -> None:
        """Convert HTTP errors to appropriate exceptions."""
        status = response.status_code

        try:
            error_data = response.json()
            message = error_data.get("error", {}).get("message", response.text)
        except Exception:
            message = response.text

        if status == 429:
            # Rate limit - extract Retry-After if available
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(retry_after)

        elif status == 404:
            raise ModelNotFoundError(model)

        elif status == 400:
            raise InvalidRequestError(message, status)

        elif status == 401:
            raise InvalidRequestError("Invalid API key", 401)

        elif status == 403:
            raise InvalidRequestError("Access forbidden", 403)

        elif status >= 500:
            raise ServerError(message, status)

        elif status >= 400:
            raise InvalidRequestError(message, status)

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send a query to a model and get a response.

        Args:
            model: Model identifier (e.g., "openai/gpt-4")
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters to pass to the API

        Returns:
            Dict with "content" and optional "reasoning_details"

        Raises:
            OpenRouterError subclass on failure
        """
        # Check circuit breaker
        circuit_key = model if self.config.circuit_breaker.per_model else "global"
        await self.circuit_breaker.can_execute(circuit_key)

        # Build request
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self.config.default_temperature,
            "max_tokens": max_tokens or self.config.default_max_tokens,
            **kwargs,
        }

        connect_timeout, read_timeout = self.config.timeout.get_timeout(model)

        if self.config.log_requests:
            logger.info(f"OpenRouter request: model={model}, messages={len(messages)}")

        try:
            client = await self._get_client()

            response = await client.post(
                "/chat/completions",
                json=payload,
                timeout=httpx.Timeout(connect_timeout, read=read_timeout),
            )

            if response.status_code != 200:
                self._handle_response_error(response, model)

            data = response.json()

            # Record success
            await self.circuit_breaker.record_success(circuit_key)

            # Extract response
            result: Dict[str, Any] = {
                "content": data["choices"][0]["message"]["content"]
            }

            # Check for reasoning details (o1, etc.)
            if "reasoning_content" in data["choices"][0]["message"]:
                result["reasoning_details"] = data["choices"][0]["message"][
                    "reasoning_content"
                ]

            if self.config.log_responses:
                logger.info(
                    f"OpenRouter response: model={model}, length={len(result['content'])}"
                )

            return result

        except httpx.TimeoutException:
            await self.circuit_breaker.record_failure(circuit_key)
            raise OpenRouterTimeoutError(read_timeout)

        except httpx.ConnectError as e:
            await self.circuit_breaker.record_failure(circuit_key)
            raise OpenRouterConnectionError(str(e))

        except (RateLimitError, ServerError):
            await self.circuit_breaker.record_failure(circuit_key)
            raise

        except OpenRouterError:
            # Don't record client errors as circuit failures
            raise

        except Exception as e:
            await self.circuit_breaker.record_failure(circuit_key)
            logger.exception(f"Unexpected error querying {model}")
            raise OpenRouterError(f"Unexpected error: {e}")

    async def query_with_retry(
        self,
        model: str,
        messages: List[Dict[str, str]],
        retry_config: Optional[RetryConfig] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Query with automatic retry on transient failures.

        Uses exponential backoff with jitter.
        """
        config = retry_config or self.config.retry

        async with RetryableOperation(config, f"query_{model}") as op:
            return await op.execute(
                self.query,
                model=model,
                messages=messages,
                **kwargs,
            )

    async def stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a response from a model.

        Yields events with:
        - type: "content" | "done" | "error"
        - content: Partial content (for "content" type)
        - full_content: Complete content (for "done" type)
        """
        circuit_key = model if self.config.circuit_breaker.per_model else "global"
        await self.circuit_breaker.can_execute(circuit_key)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self.config.default_temperature,
            "max_tokens": max_tokens or self.config.default_max_tokens,
            "stream": True,
            **kwargs,
        }

        connect_timeout, read_timeout = self.config.timeout.get_timeout(model)
        full_content = ""

        try:
            client = await self._get_client()

            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                timeout=httpx.Timeout(connect_timeout, read=read_timeout),
            ) as response:

                if response.status_code != 200:
                    # Read full response for error details
                    await response.aread()
                    self._handle_response_error(response, model)

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data = line[6:]  # Remove "data: " prefix

                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]

                        if "content" in delta:
                            content = delta["content"]
                            full_content += content
                            yield {
                                "type": "content",
                                "content": content,
                                "full_content": full_content,
                            }

                    except json.JSONDecodeError:
                        continue

            # Record success
            await self.circuit_breaker.record_success(circuit_key)

            yield {"type": "done", "full_content": full_content}

        except httpx.TimeoutException:
            await self.circuit_breaker.record_failure(circuit_key)
            yield {"type": "error", "error": f"Timeout after {read_timeout}s"}

        except httpx.ConnectError as e:
            await self.circuit_breaker.record_failure(circuit_key)
            yield {"type": "error", "error": f"Connection failed: {e}"}

        except OpenRouterError as e:
            if isinstance(e, (RateLimitError, ServerError)):
                await self.circuit_breaker.record_failure(circuit_key)
            yield {"type": "error", "error": str(e)}

        except Exception as e:
            await self.circuit_breaker.record_failure(circuit_key)
            logger.exception(f"Unexpected error streaming {model}")
            yield {"type": "error", "error": f"Unexpected error: {e}"}

    async def validate_model(self, model: str) -> bool:
        """
        Check if a model is available and accessible.

        Returns True if valid, False otherwise.
        """
        try:
            # Send minimal request to test model
            await self.query(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
            )
            return True
        except ModelNotFoundError:
            return False
        except InvalidRequestError:
            # Model exists but request was invalid (still accessible)
            return True
        except Exception:
            return False

    def get_circuit_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring."""
        stats = self.circuit_breaker.get_all_stats()
        return {
            key: {
                "state": stat.state.value,
                "failure_count": stat.failure_count,
                "success_count": stat.success_count,
                "last_failure": stat.last_failure_time,
            }
            for key, stat in stats.items()
        }
