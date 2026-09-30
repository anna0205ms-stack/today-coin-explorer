"""Process-wide pacing for Upbit requests across concurrent scanner workers."""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_next_start = 0.0


def wait_for_request_slot(interval: float = 0.13) -> None:
    """Serialize start times, while leaving network and analysis work parallel."""
    global _next_start
    with _lock:
        delay = _next_start - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        _next_start = time.monotonic() + max(0.13, interval)
