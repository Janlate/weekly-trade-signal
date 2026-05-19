import time

from tradingview_mcp.core.services.fundamentals.cache import JsonDiskCache


def test_cache_set_get(tmp_path):
    cache = JsonDiskCache(tmp_path / "cache")
    cache.set("k1", {"a": 1}, ttl_seconds=60)
    assert cache.get("k1") == {"a": 1}


def test_cache_miss_returns_none(tmp_path):
    cache = JsonDiskCache(tmp_path / "cache")
    assert cache.get("missing") is None


def test_cache_expired(tmp_path):
    cache = JsonDiskCache(tmp_path / "cache")
    cache.set("k", "v", ttl_seconds=0)
    time.sleep(0.01)
    assert cache.get("k") is None
