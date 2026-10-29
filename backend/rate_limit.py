# -*- coding: utf-8 -*-
"""轻量内存限流（C 侧，10/31）：不引入 Redis，单实例演示足够。"""
import os
import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int = 60):
        if limit <= 0:
            return True, 0, 0
        now = time.monotonic()
        with self._lock:
            bucket = self._events[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
                return False, 0, retry_after
            bucket.append(now)
            return True, max(0, limit - len(bucket)), 0


limiter = SlidingWindowLimiter()


def _int_env(name: str, default: int) -> int:
    try:
        return int((os.getenv(name) or str(default)).strip())
    except ValueError:
        return default


def is_rate_limit_enabled() -> bool:
    """Mock 联调默认不限流；真实模式或显式开关开启时生效。"""
    force = (os.getenv("RATE_LIMIT_ENFORCE_IN_MOCK") or "0").strip() == "1"
    has_key = bool((os.getenv("LLM_API_KEY") or "").strip())
    mock = (os.getenv("LLM_ENABLE_MOCK") or "0").strip() == "1"
    return force or has_key or not mock


def limit_for_path(path: str) -> int:
    if path in ("/api/analyze-image", "/api/analyze-pdf", "/api/files"):
        return _int_env("UPLOAD_RATE_LIMIT_PER_MINUTE", 10)
    if path in ("/api/analyze", "/api/check", "/api/ask", "/api/compare"):
        return _int_env("RATE_LIMIT_PER_MINUTE", 60)
    return 0
