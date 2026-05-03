"""Download cover images for anime in anime.json.

- Saves to data/covers/<id-slug>.jpg
- Resizes to max COVER_MAX_PX on the longer side, JPEG quality 85
- Skips items already with cover.local set unless --retry-failed (then retries those that
  were marked failed with cover.local == "").

Failure is non-fatal: log + continue.
"""
from __future__ import annotations
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from config import (
    ANIME_JSON, COVER_MAX_PX, COVERS_DIR, REQUEST_TIMEOUT, USER_AGENT,
)


def _id_slug(anime_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", anime_id)


def _download_one(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img = img.convert("RGB")
        w, h = img.size
        long_side = max(w, h)
        if long_side > COVER_MAX_PX:
            scale = COVER_MAX_PX / long_side
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=85, optimize=True)
        return True
    except Exception as e:
        print(f"[download] failed {url}: {e}")
        return False


def run(retry_failed: bool = False) -> None:
    if not ANIME_JSON.exists():
        print(f"[download] {ANIME_JSON} not found — run enrich first")
        sys.exit(2)

    db = json.loads(ANIME_JSON.read_text(encoding="utf-8"))
    anime: dict = db.get("anime", {})
    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    ok = skipped = failed = 0
    items = list(anime.items())
    for i, (anime_id, rec) in enumerate(items, 1):
        cover = rec.get("cover") or {}
        url = cover.get("url")
        local = cover.get("local")

        # Skip if already downloaded
        if local and (Path(local).is_absolute() or (COVERS_DIR.parent / local).exists()):
            if not retry_failed or local:
                skipped += 1
                continue

        if not url:
            failed += 1
            continue

        slug_id = _id_slug(anime_id)
        dest = COVERS_DIR / f"{slug_id}.jpg"
        if dest.exists() and not retry_failed:
            rec["cover"]["local"] = f"data/covers/{slug_id}.jpg"
            rec.setdefault("enrichment", {})["cover_at"] = datetime.now().isoformat(timespec="seconds")
            skipped += 1
            continue

        if _download_one(url, dest):
            rec["cover"]["local"] = f"data/covers/{slug_id}.jpg"
            rec.setdefault("enrichment", {})["cover_at"] = datetime.now().isoformat(timespec="seconds")
            ok += 1
        else:
            rec["cover"]["local"] = ""
            failed += 1

        if i % 25 == 0 or i == len(items):
            print(f"[download] {i}/{len(items)} — ok={ok} skipped={skipped} failed={failed}")

    db["anime"] = anime
    db["updated_at"] = datetime.now().isoformat(timespec="seconds")
    ANIME_JSON.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[download] done. ok={ok} skipped={skipped} failed={failed}")
