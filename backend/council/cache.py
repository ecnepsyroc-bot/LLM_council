"""
Response caching layer for LLM Council.

Provides in-memory caching with optional TTL for council deliberation results.
Caches are keyed by query hash + model configuration to ensure consistency.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from threading import Lock
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""

    key: str
    stage1_data: list[dict]
    stage2_data: list[dict]
    stage3_data: dict
    metadata: dict
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    hit_count: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hit_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate as percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100


class ResponseCache:
    """
    In-memory cache for council deliberation responses.

    Thread-safe implementation with TTL support and LRU eviction.
    """

    def __init__(
        self,
        max_size: int = 100,
        default_ttl: Optional[int] = 3600,  # 1 hour default
        enabled: bool = True
    ):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries to store
            default_ttl: Default time-to-live in seconds (None = no expiry)
            enabled: Whether caching is enabled
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._enabled = enabled
        self._stats = CacheStats()
        self._access_order: list[str] = []  # For LRU tracking

    @property
    def enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable caching."""
        self._enabled = value

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            self._stats.size = len(self._cache)
            return self._stats

    def generate_key(
        self,
        query: str,
        models: list[str],
        voting_method: str = "borda",
        options: Optional[dict] = None
    ) -> str:
        """
        Generate a cache key from query parameters.

        Args:
            query: The user query
            models: List of council models
            voting_method: The voting method used
            options: Additional options that affect output

        Returns:
            SHA256 hash as cache key
        """
        # Normalize inputs for consistent hashing
        key_data = {
            "query": query.strip().lower(),
            "models": sorted(models),
            "voting_method": voting_method,
            "options": options or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    def get(self, key: str) -> Optional[dict]:
        """
        Retrieve an entry from cache.

        Args:
            key: Cache key

        Returns:
            Dict with stage1, stage2, stage3, metadata or None if not found
        """
        if not self._enabled:
            return None

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                logger.debug(f"Cache miss: {key[:8]}...")
                return None

            if entry.is_expired():
                self._remove_entry(key)
                self._stats.expirations += 1
                self._stats.misses += 1
                logger.debug(f"Cache expired: {key[:8]}...")
                return None

            # Record hit and update access order
            entry.record_hit()
            self._stats.hits += 1
            self._update_access_order(key)

            logger.debug(f"Cache hit: {key[:8]}... (hits: {entry.hit_count})")

            return {
                "stage1": entry.stage1_data,
                "stage2": entry.stage2_data,
                "stage3": entry.stage3_data,
                "metadata": entry.metadata,
                "cached": True,
                "cache_age": time.time() - entry.created_at
            }

    def set(
        self,
        key: str,
        stage1_data: list[dict],
        stage2_data: list[dict],
        stage3_data: dict,
        metadata: dict,
        ttl: Optional[int] = None
    ) -> None:
        """
        Store an entry in cache.

        Args:
            key: Cache key
            stage1_data: Stage 1 responses
            stage2_data: Stage 2 rankings
            stage3_data: Stage 3 synthesis
            metadata: Deliberation metadata
            ttl: Time-to-live in seconds (None uses default)
        """
        if not self._enabled:
            return

        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._evict_lru()

            # Calculate expiry
            effective_ttl = ttl if ttl is not None else self._default_ttl
            expires_at = None
            if effective_ttl is not None:
                expires_at = time.time() + effective_ttl

            # Create and store entry
            entry = CacheEntry(
                key=key,
                stage1_data=stage1_data,
                stage2_data=stage2_data,
                stage3_data=stage3_data,
                metadata=metadata,
                expires_at=expires_at
            )

            self._cache[key] = entry
            self._update_access_order(key)

            logger.debug(f"Cache set: {key[:8]}... (ttl: {effective_ttl}s)")

    def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was found and removed
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._access_order.clear()
            self._stats = CacheStats()
            logger.info(f"Cache cleared: {count} entries removed")
            return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                self._remove_entry(key)
                self._stats.expirations += 1

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

            return len(expired_keys)

    def _update_access_order(self, key: str) -> None:
        """Update LRU access order (must hold lock)."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _remove_entry(self, key: str) -> None:
        """Remove an entry (must hold lock)."""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            self._access_order.remove(key)

    def _evict_lru(self) -> None:
        """Evict least recently used entry (must hold lock)."""
        if self._access_order:
            lru_key = self._access_order[0]
            self._remove_entry(lru_key)
            self._stats.evictions += 1
            logger.debug(f"Cache evicted (LRU): {lru_key[:8]}...")


# Global cache instance
_cache: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache


def configure_cache(
    max_size: int = 100,
    default_ttl: Optional[int] = 3600,
    enabled: bool = True
) -> ResponseCache:
    """
    Configure the global cache instance.

    Args:
        max_size: Maximum entries
        default_ttl: Default TTL in seconds
        enabled: Whether caching is enabled

    Returns:
        The configured cache instance
    """
    global _cache
    _cache = ResponseCache(
        max_size=max_size,
        default_ttl=default_ttl,
        enabled=enabled
    )
    return _cache


async def cached_council_query(
    query: str,
    models: list[str],
    run_council_fn,
    voting_method: str = "borda",
    options: Optional[dict] = None,
    cache_ttl: Optional[int] = None,
    bypass_cache: bool = False
) -> tuple[list, list, dict, dict]:
    """
    Execute a council query with caching.

    Args:
        query: User query
        models: Council models
        run_council_fn: Async function to run council (called if cache miss)
        voting_method: Voting method
        options: Additional options
        cache_ttl: Override TTL for this query
        bypass_cache: Skip cache lookup (still stores result)

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    cache = get_cache()

    # Generate cache key
    cache_key = cache.generate_key(query, models, voting_method, options)

    # Check cache unless bypassed
    if not bypass_cache:
        cached = cache.get(cache_key)
        if cached:
            return (
                cached["stage1"],
                cached["stage2"],
                cached["stage3"],
                {**cached["metadata"], "from_cache": True, "cache_age": cached["cache_age"]}
            )

    # Cache miss - run the council
    stage1, stage2, stage3, metadata = await run_council_fn(query)

    # Store in cache
    cache.set(
        key=cache_key,
        stage1_data=stage1,
        stage2_data=stage2,
        stage3_data=stage3,
        metadata=metadata,
        ttl=cache_ttl
    )

    return stage1, stage2, stage3, {**metadata, "from_cache": False}
