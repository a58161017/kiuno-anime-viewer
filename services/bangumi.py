"""Bangumi (bgm.tv) v0 REST client. Best-effort — failures don't block enrich.

Public API:
  - search(title) -> list[dict]: subjects matching the title
  - fetch(subject_id: int) -> dict | None: full subject detail incl. infobox/rating
"""
from __future__ import annotations
from typing import Optional

from config import BANGUMI_BASE
from services.http import cached_request


def search(title: str) -> list[dict]:
    if not title:
        return []
    body = {
        "keyword": title,
        "filter": {"type": [2]},
    }
    data = cached_request(
        "bangumi", "POST", f"{BANGUMI_BASE}/v0/search/subjects",
        params={"limit": 8, "offset": 0},
        json_body=body,
        cache_key=f"search|{title}",
    )
    if not data:
        return []
    return data.get("data", []) or []


def fetch(subject_id: int) -> Optional[dict]:
    data = cached_request(
        "bangumi", "GET", f"{BANGUMI_BASE}/v0/subjects/{subject_id}",
        cache_key=f"detail|{subject_id}",
    )
    if not data:
        return None
    return data
