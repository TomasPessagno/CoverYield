"""Runtime configuration, read from environment variables.

COVERYIELD_MODE                "local" (default) or "hosted"
REDIS_URL / KV_URL             if set, chains are stored in Redis (shared across
                               instances); otherwise in memory
COVERYIELD_REFRESH_COOLDOWN    seconds between live refreshes of the same ticker
                               (default: 0 locally, 600 when hosted)

Locally there is no cooldown: it's your own connection, so "Scan now" always
fetches live. The hosted site caps each ticker at one live fetch per cooldown
window, shared by all visitors.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Mode = Literal["local", "hosted"]

# Locally, a stored chain older than this is refetched on the next view (like a cache).
LOCAL_MAX_AGE_SECONDS = 600.0
HOSTED_COOLDOWN_SECONDS = 600.0


@dataclass(frozen=True)
class Settings:
    mode: Mode
    redis_url: str | None
    refresh_cooldown_seconds: float
    # None: stored chains never expire on their own (the snapshot job keeps them fresh).
    max_age_seconds: float | None


def load_settings() -> Settings:
    mode: Mode = "hosted" if os.environ.get("COVERYIELD_MODE", "").lower() == "hosted" else "local"
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("KV_URL") or None
    default_cooldown = HOSTED_COOLDOWN_SECONDS if mode == "hosted" else 0.0
    cooldown = float(os.environ.get("COVERYIELD_REFRESH_COOLDOWN", default_cooldown))
    max_age = None if mode == "hosted" else LOCAL_MAX_AGE_SECONDS
    return Settings(mode, redis_url, cooldown, max_age)
