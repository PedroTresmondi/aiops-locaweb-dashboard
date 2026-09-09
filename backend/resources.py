"""One model build at a time, including concurrent cold-start requests."""

from functools import lru_cache, wraps
from threading import RLock


_build_lock = RLock()


def cached_resource(function):
    # lru_cache alone can evaluate the same missing key in multiple threads.
    # The shared reentrant lock also bounds memory when different models start.
    cached = lru_cache(maxsize=1)(function)

    @wraps(function)
    def read(*args, **kwargs):
        with _build_lock:
            return cached(*args, **kwargs)

    def clear():
        with _build_lock:
            cached.cache_clear()

    read.cache_clear = clear
    read.cache_info = cached.cache_info
    return read
