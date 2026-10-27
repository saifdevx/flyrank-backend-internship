"""In-memory token bucket. A burst is allowed, then requests are refused until tokens refill."""
import threading
import time


class TokenBuckets:
    def __init__(self):
        self._lock = threading.Lock()
        self._buckets = {}   # key -> [tokens, last_timestamp]

    def consume(self, key, capacity, refill_per_sec, now=None):
        """Take one token. Returns (allowed, seconds_until_next_token)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._buckets.get(key, (capacity, now))
            tokens = min(capacity, tokens + (now - last) * refill_per_sec)
            if tokens >= 1:
                self._buckets[key] = [tokens - 1, now]
                allowed, retry = True, 0.0
            else:
                self._buckets[key] = [tokens, now]
                allowed, retry = False, (1 - tokens) / refill_per_sec if refill_per_sec > 0 else 60.0
            if len(self._buckets) > 20000:                     # keep memory bounded
                self._sweep(now)
            return allowed, retry

    def _sweep(self, now):
        for key in [k for k, (_, last) in self._buckets.items() if now - last > 600]:
            del self._buckets[key]

    def reset(self):
        with self._lock:
            self._buckets.clear()


limiter = TokenBuckets()
