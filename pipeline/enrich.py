"""Enrich matched entries with metadata from AniList + Jikan + Bangumi.

Reads:  entries.raw.json + entries.matched.json + manual_overrides.json
Writes: anime.json (dict-by-id) + unmapped_tags.json

For each matched entry:
  - Fetch AniList Media detail (relations, cover, genres, tags)
  - Fetch Jikan /anime/{idMal} (MAL score)
  - Fetch Bangumi /v0/subjects/{id} (zh synopsis, score)
  - Build canonical record, aggregate ratings, generate tag list
  - Skip if all sources were enriched within ENRICH_TTL_DAYS (unless --force)

manual_overrides.json shape (deep merge over the canonical record after enrichment):
{
  "anilist:142853": {
     "categories": ["custom"],
     "tags": ["+額外標籤", "-星級-4.5"]      // prefix '+' adds, '-' removes
  }
}
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import (
    ANIME_JSON, DATA, ENTRIES_RAW, ENRICH_TTL_DAYS, GENRE_ZH_MAP,
    GRAPH_DEFAULTS, MANUAL_OVERRIDES, UNMAPPED_TAGS,
)
from services import anilist, bangumi, jikan
from services.rating import aggregate, star_tag_value

# Bangumi 的中文資料是簡體，使用者要繁體 (台灣)。s2tw 帶詞彙轉換 (e.g. 鼠標→滑鼠).
try:
    from opencc import OpenCC
    _s2tw = OpenCC("s2twp")
    def _to_traditional(s):
        return _s2tw.convert(s) if s else s
except Exception:
    def _to_traditional(s):
        return s

ENTRIES_MATCHED = DATA / "entries.matched.json"
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_fresh(iso_ts: Optional[str]) -> bool:
    if not iso_ts:
        return False
    try:
        ts = datetime.fromisoformat(iso_ts)
    except ValueError:
        return False
    return (datetime.now() - ts) < timedelta(days=ENRICH_TTL_DAYS)


def _strip_html(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = HTML_TAG_RE.sub("", s)
    return s.replace("<br>", "\n").replace("&amp;", "&").strip() or None


def _build_record(entry: dict, matched: dict, override: dict | None,
                  ani_media: dict, mal_data: Optional[dict], bgm_data: Optional[dict],
                  genre_zh: dict, unmapped_tags: dict, now_iso: str) -> dict:
    titles_a = ani_media.get("title") or {}
    start = ani_media.get("startDate") or {}
    year = start.get("year")

    # ----- Studios (main) -----
    studios = [s["name"] for s in (ani_media.get("studios") or {}).get("nodes", []) if s.get("name")]

    # ----- Genres (categories, mapped to zh) -----
    genres_en = ani_media.get("genres") or []
    categories = []
    for g in genres_en:
        zh = genre_zh.get(g, g)
        if zh not in categories:
            categories.append(zh)

    # ----- Tags (curated) -----
    tags: list[str] = []
    rank_min = GRAPH_DEFAULTS["tag_keep_rank_min"]
    for t in ani_media.get("tags") or []:
        rank = t.get("rank") or 0
        if rank < rank_min:
            continue
        if t.get("isMediaSpoiler") or t.get("isGeneralSpoiler"):
            continue
        name = t.get("name")
        if not name:
            continue
        zh = genre_zh.get(name, name)  # tag map shares the genre map; misses go to unmapped
        if zh not in tags:
            tags.append(zh)
        if zh == name and zh not in unmapped_tags:
            unmapped_tags[zh] = {"first_seen": now_iso}

    # Add derived tags
    if year:
        tags.append(f"年份-{year}")
    for s in studios:
        tags.append(f"studio-{s}")
    section = entry.get("section_origin")
    if section:
        tags.append(section)
    fmt = ani_media.get("format")
    if fmt:
        tags.append(f"format-{fmt.lower()}")

    # ----- Ratings -----
    sources: dict = {}
    if ani_media.get("averageScore"):
        sources["anilist"] = {
            "id": ani_media["id"],
            "score": ani_media["averageScore"],
            "scale": 100,
            "fetched_at": now_iso,
        }
    if mal_data and mal_data.get("score"):
        sources["mal"] = {
            "id": mal_data.get("mal_id"),
            "score": mal_data.get("score"),
            "scale": 10,
            "fetched_at": now_iso,
        }
    if bgm_data and (bgm_data.get("rating") or {}).get("score"):
        sources["bangumi"] = {
            "id": bgm_data.get("id"),
            "score": bgm_data["rating"]["score"],
            "scale": 10,
            "fetched_at": now_iso,
        }
    aggregated = aggregate(sources)
    star_tag = star_tag_value(aggregated)
    if star_tag:
        tags.append(star_tag)

    # ----- Synopsis (Bangumi 簡體 → 繁體) -----
    synopsis_en = _strip_html(ani_media.get("description"))
    synopsis_zh = None
    if bgm_data and bgm_data.get("summary"):
        synopsis_zh = _to_traditional(bgm_data["summary"].strip()) or None

    # ----- Relations -----
    relations: dict[str, list[str]] = {"prequel": [], "sequel": [], "side_story": [], "other": []}
    for edge in (ani_media.get("relations") or {}).get("edges", []):
        rt = (edge.get("relationType") or "").upper()
        node = edge.get("node") or {}
        if node.get("type") != "ANIME":
            continue
        nid = node.get("id")
        if not nid:
            continue
        ref = f"anilist:{nid}"
        if rt == "PREQUEL":
            relations["prequel"].append(ref)
        elif rt == "SEQUEL":
            relations["sequel"].append(ref)
        elif rt in ("SIDE_STORY", "PARENT", "ALTERNATIVE", "SPIN_OFF"):
            relations["side_story"].append(ref)

    # ----- External links -----
    external = {"anilist": ani_media.get("siteUrl")}
    if ani_media.get("idMal"):
        external["mal"] = f"https://myanimelist.net/anime/{ani_media['idMal']}"
    if bgm_data and bgm_data.get("id"):
        external["bangumi"] = f"https://bgm.tv/subject/{bgm_data['id']}"

    # 標題優先使用使用者 Doc 裡的原文（保留「第二季」「第三季」等季別），Bangumi 中文
    # 名作為次要別名（s2tw 簡轉繁台灣詞彙）。
    user_title = entry.get("title_raw") or entry.get("title_main_zh")
    bgm_zh = _to_traditional((bgm_data or {}).get("name_cn"))
    aliases = []
    if bgm_zh and bgm_zh != user_title:
        aliases.append(bgm_zh)
    record = {
        "id": f"anilist:{ani_media['id']}",
        "format": (ani_media.get("format") or "").lower() or "tv",
        "section_origin": section,
        "titles": {
            "primary_zh": user_title or bgm_zh,
            "zh_aliases": aliases,
            "ja": (bgm_data or {}).get("name") or titles_a.get("native"),
            "ja_romaji": titles_a.get("romaji"),
            "en": titles_a.get("english"),
        },
        "year": year,
        "season": (ani_media.get("season") or "").title() or None,
        "episodes": ani_media.get("episodes"),
        "studios": studios,
        "categories": categories,
        "tags": tags,
        "rating": {
            "score": aggregated,
            "sources": sources,
        },
        "synopsis_zh": synopsis_zh,
        "synopsis_en": synopsis_en,
        "cover": {
            "url": (ani_media.get("coverImage") or {}).get("extraLarge") or (ani_media.get("coverImage") or {}).get("large"),
            "local": None,
        },
        "external_links": external,
        "relations": relations,
        "user": {
            "self_rating_raw": entry.get("user_rating"),
            "doc_episode_count": entry.get("episodes_in_doc"),
            "added_at": now_iso,
        },
        "source_doc_raw": entry.get("source_doc_raw"),
        "enrichment": {
            "anilist_at": now_iso,
            "mal_at": now_iso if mal_data else None,
            "bangumi_at": now_iso if bgm_data else None,
            "cover_at": None,
            "needs_review": matched.get("needs_review", False),
        },
    }

    # Apply manual overrides (deep, with +/− tag prefix support)
    if override:
        if "categories" in override and isinstance(override["categories"], list):
            record["categories"] = override["categories"]
        if "tags" in override and isinstance(override["tags"], list):
            tag_set = list(record["tags"])
            for op in override["tags"]:
                if not isinstance(op, str):
                    continue
                if op.startswith("+"):
                    name = op[1:]
                    if name and name not in tag_set:
                        tag_set.append(name)
                elif op.startswith("-"):
                    name = op[1:]
                    tag_set = [t for t in tag_set if t != name]
                else:
                    if op not in tag_set:
                        tag_set.append(op)
            record["tags"] = tag_set
        for key in ("synopsis_zh", "synopsis_en"):
            if key in override:
                record[key] = override[key]

    return record


def run(source: str = "all", force: bool = False, only_new: bool = False) -> None:
    matched = _load(ENTRIES_MATCHED, {"matched": {}}).get("matched", {})
    raw = _load(ENTRIES_RAW, {"entries": {}}).get("entries", {})
    if not matched:
        print(f"[enrich] nothing matched in {ENTRIES_MATCHED} — run `match` first")
        sys.exit(2)

    anime_db = _load(ANIME_JSON, {"version": 1, "anime": {}})
    anime: dict = anime_db.get("anime", {})

    genre_zh = _load(GENRE_ZH_MAP, {})
    overrides = _load(MANUAL_OVERRIDES, {})
    unmapped_tags = _load(UNMAPPED_TAGS, {})

    todo = list(matched.items())
    print(f"[enrich] {len(todo)} matched entries; source={source} force={force} only_new={only_new}")

    enriched_n = skipped_n = failed_n = 0
    for i, (slug, m) in enumerate(todo, 1):
        best = m.get("best") or {}
        ani_id = best.get("anilist_id")
        if not ani_id:
            failed_n += 1
            continue

        anime_id = f"anilist:{ani_id}"
        if only_new and anime_id in anime:
            skipped_n += 1
            continue

        existing = anime.get(anime_id)
        if existing and not force and _is_fresh(existing.get("enrichment", {}).get("anilist_at")):
            skipped_n += 1
            continue

        ani_media = anilist.fetch(ani_id)
        if not ani_media:
            failed_n += 1
            continue

        mal_data = None
        if source in ("all", "mal") and best.get("mal_id"):
            mal_data = jikan.fetch(best["mal_id"])

        bgm_data = None
        if source in ("all", "bangumi") and best.get("bangumi_id"):
            bgm_data = bangumi.fetch(best["bangumi_id"])

        entry = raw.get(slug, {})
        override = overrides.get(anime_id)
        now_iso = datetime.now().isoformat(timespec="seconds")

        record = _build_record(
            entry, m, override, ani_media, mal_data, bgm_data,
            genre_zh, unmapped_tags, now_iso,
        )
        # Preserve cover.local across re-enrich
        if existing and existing.get("cover", {}).get("local"):
            record["cover"]["local"] = existing["cover"]["local"]
            record["enrichment"]["cover_at"] = existing.get("enrichment", {}).get("cover_at")

        anime[anime_id] = record
        enriched_n += 1

        if i % 10 == 0 or i == len(todo):
            print(f"[enrich] {i}/{len(todo)} — enriched={enriched_n} skipped={skipped_n} failed={failed_n}")

    anime_db["anime"] = anime
    anime_db["version"] = anime_db.get("version", 1)
    anime_db["updated_at"] = datetime.now().isoformat(timespec="seconds")

    _save(ANIME_JSON, anime_db)
    _save(UNMAPPED_TAGS, unmapped_tags)
    print(f"[enrich] done. enriched={enriched_n} skipped={skipped_n} failed={failed_n}")
