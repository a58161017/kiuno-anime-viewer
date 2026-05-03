"""Interactive single-entry add.

Usage:
    python run.py add "(4.8星)BOCCHI THE ROCK!(12)"

Steps:
    1. Parse the line into an entry.
    2. Run match_one to get top 3 candidates.
    3. Prompt user to pick: 1/2/3 / m=manual id / s=skip.
    4. Enrich the chosen entry, download cover.
    5. Append the line to raw/anime_list.txt under the inferred section if not present.
    6. Patch graph.json incrementally (rebuild, since rebuild is fast for ~1k nodes).

The CLI assumes the existing raw/anime_list.txt already has the canonical section headers.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import (
    ANIME_JSON, ENTRIES_RAW, MANUAL_OVERRIDES, RAW_LIST,
)
from pipeline import download as dl_mod
from pipeline import enrich as enrich_mod
from pipeline import graph as graph_mod
from pipeline.match import match_one
from pipeline.parse import parse_line
from services import anilist


SECTION_HEADER = {
    "劇場版": "--------------劇場版(完結)--------------",
    "季番":   "--------------季番(完結)--------------",
    "已完結": "--------------已完結--------------",
}


def _prompt_choice(candidates: list[dict]) -> Optional[dict]:
    if not candidates:
        print("[add] no candidates returned. you can manually enter an AniList id.")
        return _prompt_manual_id()
    print("\n候選：")
    for i, c in enumerate(candidates[:3], 1):
        title = c.get("title_zh") or c.get("title_romaji") or c.get("title_english") or "?"
        year = c.get("year") or "?"
        ep = c.get("episodes") or "?"
        fmt = c.get("format") or "?"
        conf = c.get("confidence")
        print(f"  {i}. {title}  (year={year}, ep={ep}, fmt={fmt}, AniList={c.get('anilist_id')}) — conf={conf}")
    while True:
        choice = input("選擇 [1/2/3 / m=手動填 AniList id / s=skip]: ").strip().lower()
        if choice in ("1", "2", "3"):
            idx = int(choice) - 1
            if idx < len(candidates):
                return candidates[idx]
            print("超出範圍")
        elif choice == "m":
            return _prompt_manual_id()
        elif choice == "s":
            return None
        else:
            print("輸入 1/2/3/m/s")


def _prompt_manual_id() -> Optional[dict]:
    while True:
        v = input("AniList id (or 'cancel'): ").strip()
        if v.lower() == "cancel":
            return None
        try:
            ani_id = int(v.split(":")[-1])
        except ValueError:
            print("not a number")
            continue
        media = anilist.fetch(ani_id)
        if not media:
            print(f"AniList:{ani_id} returned nothing — try another?")
            continue
        titles = media.get("title") or {}
        return {
            "anilist_id": ani_id,
            "mal_id": media.get("idMal"),
            "bangumi_id": None,
            "title_romaji": titles.get("romaji"),
            "title_english": titles.get("english"),
            "title_native": titles.get("native"),
            "title_zh": None,
            "year": (media.get("startDate") or {}).get("year"),
            "format": media.get("format"),
            "episodes": media.get("episodes"),
            "confidence": 1.0,
        }


def _ensure_in_raw_file(line: str, section_name: str) -> None:
    """Append the raw line to anime_list.txt under the right section if missing."""
    if not RAW_LIST.exists():
        RAW_LIST.parent.mkdir(parents=True, exist_ok=True)
        RAW_LIST.write_text("\n".join(SECTION_HEADER.values()) + "\n", encoding="utf-8")

    text = RAW_LIST.read_text(encoding="utf-8")
    if line.strip() in {ln.strip() for ln in text.splitlines()}:
        return

    header = SECTION_HEADER.get(section_name, SECTION_HEADER["季番"])
    lines = text.splitlines()
    if header not in lines:
        lines.append("")
        lines.append(header)

    insert_at = lines.index(header) + 1
    while insert_at < len(lines) and not lines[insert_at].startswith("---"):
        insert_at += 1
    lines.insert(insert_at, line.strip())
    RAW_LIST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _save_raw_entry(entry: dict) -> None:
    raw_db = json.loads(ENTRIES_RAW.read_text(encoding="utf-8")) if ENTRIES_RAW.exists() else {"version": 1, "entries": {}}
    raw_db.setdefault("entries", {})[entry["slug"]] = entry
    raw_db["updated_at"] = datetime.now().isoformat(timespec="seconds")
    ENTRIES_RAW.write_text(json.dumps(raw_db, ensure_ascii=False, indent=2), encoding="utf-8")


def run(raw_line: str) -> None:
    section_name = "季番"
    fmt_hint = "tv"
    if "劇場版" in raw_line or "電影" in raw_line or "movie" in raw_line.lower():
        section_name = "劇場版"
        fmt_hint = "movie"

    entry = parse_line(raw_line, section_name, fmt_hint)
    if not entry:
        print(f"[add] could not parse: {raw_line}")
        sys.exit(2)
    print(f"[add] parsed: title='{entry['title_main_zh']}', rating={entry['user_rating']}, eps={entry['episode_groups']}")

    result = match_one(entry)
    pick = _prompt_choice(result["candidates"])
    if not pick:
        print("[add] skipped.")
        return

    # Persist raw entry, then run enrich for just this id
    _save_raw_entry(entry)
    _ensure_in_raw_file(raw_line, section_name)

    # Surgical enrich: stuff the matched record in entries.matched.json then call enrich
    matched_path = enrich_mod.ENTRIES_MATCHED
    matched_db = json.loads(matched_path.read_text(encoding="utf-8")) if matched_path.exists() else {"version": 1, "matched": {}}
    matched_db["matched"][entry["slug"]] = {
        "best": pick,
        "candidates": [pick],
        "confidence": pick.get("confidence", 1.0),
        "needs_review": False,
        "manual": True,
        "matched_at": datetime.now().isoformat(timespec="seconds"),
    }
    matched_path.write_text(json.dumps(matched_db, ensure_ascii=False, indent=2), encoding="utf-8")

    # Enrich just-new + download + graph rebuild
    enrich_mod.run(source="all", force=False, only_new=True)
    dl_mod.run(retry_failed=False)
    graph_mod.run()

    print(f"[add] done. AniList:{pick['anilist_id']} -> anime.json")
