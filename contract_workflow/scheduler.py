from __future__ import annotations

from datetime import datetime, timedelta, timezone


class InMemoryLeaseRegistry:
    """Illustrates scheduler competition without a platform scheduler dependency."""

    def __init__(self) -> None:
        self._leases: dict[str, tuple[str, datetime]] = {}

    def acquire(self, key: str, owner: str, ttl_seconds: int) -> bool:
        now = datetime.now(timezone.utc)
        active = self._leases.get(key)
        if active and active[1] > now and active[0] != owner:
            return False
        self._leases[key] = (owner, now + timedelta(seconds=ttl_seconds))
        return True

    def release(self, key: str, owner: str) -> None:
        if self._leases.get(key, (None,))[0] == owner:
            del self._leases[key]
