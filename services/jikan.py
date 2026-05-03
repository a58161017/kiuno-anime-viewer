"""Jikan (unofficial MyAnimeList REST). Fetch by MAL id only — search done via AniList."""
from __future__ import annotations
from typing import Optional

from config import JIKAN_BASE
from services.http import cached_request


def fetch(mal_id: int) -> Optional[dict]:
    data = cached_request(
        "jikan", "GET", f"{JIKAN_BASE}/anime/{int(mal_id)}",
        cache_key=f"detail|{mal_id}",
    )
    if not data:
        return None
    return data.get("data")
