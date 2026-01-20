"""Tests for response caching layer."""

import pytest
import time
from backend.council.cache import (
    ResponseCache,
    CacheEntry,
    get_cache,
    configure_cache,
)


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_entry_not_expired_without_ttl(self):
        """Entry without TTL should never expire."""
        entry = CacheEntry(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={},
            expires_at=None
        )
        assert not entry.is_expired()

    def test_entry_expired_with_past_ttl(self):
        """Entry with past expiry should be expired."""
        entry = CacheEntry(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={},
            expires_at=time.time() - 1  # 1 second ago
        )
        assert entry.is_expired()

    def test_entry_not_expired_with_future_ttl(self):
        """Entry with future expiry should not be expired."""
        entry = CacheEntry(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={},
            expires_at=time.time() + 3600  # 1 hour from now
        )
        assert not entry.is_expired()

    def test_hit_count_increments(self):
        """Hit count should increment on record_hit."""
        entry = CacheEntry(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={}
        )
        assert entry.hit_count == 0
        entry.record_hit()
        assert entry.hit_count == 1
        entry.record_hit()
        assert entry.hit_count == 2


class TestResponseCache:
    """Test ResponseCache class."""

    def test_generate_key_deterministic(self):
        """Same inputs should generate same key."""
        cache = ResponseCache()
        key1 = cache.generate_key("test query", ["model1", "model2"])
        key2 = cache.generate_key("test query", ["model1", "model2"])
        assert key1 == key2

    def test_generate_key_different_queries(self):
        """Different queries should generate different keys."""
        cache = ResponseCache()
        key1 = cache.generate_key("query 1", ["model1"])
        key2 = cache.generate_key("query 2", ["model1"])
        assert key1 != key2

    def test_generate_key_model_order_independent(self):
        """Model order should not affect key."""
        cache = ResponseCache()
        key1 = cache.generate_key("test", ["model1", "model2"])
        key2 = cache.generate_key("test", ["model2", "model1"])
        assert key1 == key2

    def test_generate_key_case_insensitive(self):
        """Query case should not affect key."""
        cache = ResponseCache()
        key1 = cache.generate_key("Test Query", ["model1"])
        key2 = cache.generate_key("test query", ["model1"])
        assert key1 == key2

    def test_set_and_get(self):
        """Should store and retrieve entries."""
        cache = ResponseCache()
        cache.set(
            key="test_key",
            stage1_data=[{"model": "test", "response": "hello"}],
            stage2_data=[],
            stage3_data={"response": "final"},
            metadata={"test": True}
        )

        result = cache.get("test_key")
        assert result is not None
        assert result["stage1"] == [{"model": "test", "response": "hello"}]
        assert result["stage3"] == {"response": "final"}
        assert result["cached"] is True

    def test_get_nonexistent_key(self):
        """Getting nonexistent key should return None."""
        cache = ResponseCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_disabled(self):
        """Disabled cache should not store or retrieve."""
        cache = ResponseCache(enabled=False)
        cache.set(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={}
        )
        result = cache.get("test")
        assert result is None

    def test_cache_expiry(self):
        """Expired entries should not be returned."""
        cache = ResponseCache(default_ttl=1)
        cache.set(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={},
            ttl=0  # Immediate expiry
        )
        time.sleep(0.1)
        result = cache.get("test")
        assert result is None

    def test_lru_eviction(self):
        """LRU eviction should remove oldest entry."""
        cache = ResponseCache(max_size=2)

        # Add 3 entries
        for i in range(3):
            cache.set(
                key=f"key_{i}",
                stage1_data=[],
                stage2_data=[],
                stage3_data={},
                metadata={}
            )

        # First entry should be evicted
        assert cache.get("key_0") is None
        assert cache.get("key_1") is not None
        assert cache.get("key_2") is not None

    def test_invalidate(self):
        """Invalidate should remove specific entry."""
        cache = ResponseCache()
        cache.set(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={}
        )

        assert cache.get("test") is not None
        result = cache.invalidate("test")
        assert result is True
        assert cache.get("test") is None

    def test_invalidate_nonexistent(self):
        """Invalidating nonexistent key should return False."""
        cache = ResponseCache()
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_clear(self):
        """Clear should remove all entries."""
        cache = ResponseCache()
        for i in range(5):
            cache.set(
                key=f"key_{i}",
                stage1_data=[],
                stage2_data=[],
                stage3_data={},
                metadata={}
            )

        count = cache.clear()
        assert count == 5
        assert cache.stats.size == 0

    def test_stats_tracking(self):
        """Statistics should track hits and misses."""
        cache = ResponseCache()
        cache.set(
            key="exists",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={}
        )

        # Hit
        cache.get("exists")
        # Miss
        cache.get("nonexistent")

        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1

    def test_hit_rate_calculation(self):
        """Hit rate should be calculated correctly."""
        cache = ResponseCache()
        cache.set(
            key="test",
            stage1_data=[],
            stage2_data=[],
            stage3_data={},
            metadata={}
        )

        # 3 hits, 1 miss
        cache.get("test")
        cache.get("test")
        cache.get("test")
        cache.get("nonexistent")

        assert cache.stats.hit_rate == 75.0


class TestGlobalCache:
    """Test global cache functions."""

    def test_get_cache_singleton(self):
        """get_cache should return same instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_configure_cache(self):
        """configure_cache should create new instance."""
        cache1 = configure_cache(max_size=50, enabled=True)
        cache2 = get_cache()
        assert cache1 is cache2
        assert cache1._max_size == 50
