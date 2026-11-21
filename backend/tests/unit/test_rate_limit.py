"""Unit tests: rate-limit stores (#15)."""
from app.middleware.rate_limit import MemoryStore


def test_memory_store_allows_under_limit():
    s = MemoryStore()
    for _ in range(3):
        allowed, retry = s.hit("ip1", limit=3, window=60)
        assert allowed is True
        assert retry == 0


def test_memory_store_blocks_over_limit():
    s = MemoryStore()
    for _ in range(3):
        s.hit("ip1", limit=3, window=60)
    allowed, retry = s.hit("ip1", limit=3, window=60)
    assert allowed is False
    assert retry >= 1


def test_memory_store_isolated_per_key():
    s = MemoryStore()
    for _ in range(3):
        s.hit("ip1", limit=3, window=60)
    # a different IP is unaffected
    allowed, _ = s.hit("ip2", limit=3, window=60)
    assert allowed is True


def test_memory_store_window_expiry():
    s = MemoryStore()
    # Fill the window, then simulate time passing by using window=0 so old hits drop.
    for _ in range(3):
        s.hit("ip1", limit=3, window=0)
    allowed, _ = s.hit("ip1", limit=3, window=0)
    # window=0 => all previous hits are older than window, so allowed again
    assert allowed is True
