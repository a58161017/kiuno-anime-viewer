"""AniList GraphQL client.

Public API:
  - search(title, format_hint=None) -> list[dict]: top candidates with id/title/year/episodes
  - fetch(media_id: int) -> dict | None: full Media object including relations
"""
from __future__ import annotations
from typing import Optional

from config import ANILIST_GRAPHQL
from services.http import cached_request

SEARCH_QUERY = """
query ($search: String, $format: MediaFormat) {
  Page(perPage: 8) {
    media(search: $search, type: ANIME, format: $format, sort: SEARCH_MATCH) {
      id  idMal
      title { romaji english native }
      format  episodes
      startDate { year month }
      season seasonYear
      averageScore meanScore
      coverImage { extraLarge large }
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id  idMal  siteUrl
    title { romaji english native }
    format  episodes  duration
    startDate { year month day }
    endDate { year month day }
    season seasonYear
    studios(isMain: true) { nodes { name } }
    averageScore meanScore  popularity favourites
    genres
    tags { name rank category isGeneralSpoiler isMediaSpoiler }
    description(asHtml: false)
    coverImage { extraLarge large color }
    bannerImage
    relations {
      edges {
        relationType(version: 2)
        node { id type format title { romaji english native } }
      }
    }
  }
}
"""

FORMAT_MAP = {
    "movie": "MOVIE",
    "tv": "TV",
    "tv_short": "TV_SHORT",
    "ova": "OVA",
    "ona": "ONA",
    "special": "SPECIAL",
}


def search(title: str, format_hint: Optional[str] = None) -> list[dict]:
    if not title:
        return []
    variables = {"search": title}
    fmt = FORMAT_MAP.get(format_hint or "")
    if fmt:
        variables["format"] = fmt
    data = cached_request(
        "anilist", "POST", ANILIST_GRAPHQL,
        json_body={"query": SEARCH_QUERY, "variables": variables},
        cache_key=f"search|{title}|{fmt or ''}",
    )
    if not data or "data" not in data:
        return []
    return data["data"]["Page"]["media"] or []


def fetch(media_id: int) -> Optional[dict]:
    data = cached_request(
        "anilist", "POST", ANILIST_GRAPHQL,
        json_body={"query": DETAIL_QUERY, "variables": {"id": int(media_id)}},
        cache_key=f"detail|{media_id}",
    )
    if not data or "data" not in data:
        return None
    return data["data"]["Media"]
