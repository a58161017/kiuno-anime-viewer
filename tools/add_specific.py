"""一次加入指定 AniList id 清單的條目到 anime.json (含 Bangumi/MAL/封面)。
用法：直接編輯下面的 ENTRIES，跑 python tools/add_specific.py
"""
from __future__ import annotations
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
from PIL import Image

from config import ANIME_JSON, COVERS_DIR, COVER_MAX_PX, GENRE_ZH_MAP, USER_AGENT, REQUEST_TIMEOUT
from pipeline.enrich import _build_record
from services import anilist, jikan, bangumi

# 要新增的條目 (anilist_id, doc_raw_for_record, section, user_rating)
ENTRIES = [
    (180745, "(4.3星)歡迎來到實力至上主義的教室 第四季 2年級篇 第一學期", "季番", 4.3),
    (182205, "(4.2星)關於我轉生變成史萊姆這檔事 第四季", "季番", 4.2),
    (199547, "(4.7星)婚姻劇毒", "季番", 4.7),
]


def parse_doc_raw(s: str):
    """從 doc_raw 抽 title_main_zh / episodes 等 (簡化版)"""
    m = re.match(r"^\((\d(?:\.\d)?)\s*星\)(.+)$", s)
    if m:
        title = m.group(2).strip()
    else:
        title = s.strip()
    # 去尾端 (集數)
    m2 = re.match(r"^(.*?)\s*\((\d{1,3})\)\s*$", title)
    if m2:
        title = m2.group(1).strip()
        eps = int(m2.group(2))
    else:
        eps = None
    return title, eps


def download_cover(url, dest):
    if not url:
        return False
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        long = max(w, h)
        if long > COVER_MAX_PX:
            s = COVER_MAX_PX / long
            img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=85, optimize=True)
        return True
    except Exception as e:
        print(f"  [cover] failed: {e}")
        return False


def main():
    anime_db = json.load(open(ANIME_JSON, encoding="utf-8"))
    anime = anime_db["anime"]
    genre_zh = json.load(open(GENRE_ZH_MAP, encoding="utf-8"))

    for aid, doc_raw, section, user_rating in ENTRIES:
        anime_id = f"anilist:{aid}"
        title, eps = parse_doc_raw(doc_raw)
        print(f"\n=== AniList:{aid}  {title} ===")
        if anime_id in anime:
            print("  已存在 → skip")
            continue
        ani_media = anilist.fetch(aid)
        if not ani_media:
            print(f"  AniList fetch 失敗 → skip")
            continue
        mal_id = ani_media.get("idMal")
        mal_data = jikan.fetch(mal_id) if mal_id else None
        # Bangumi 用 native title 搜
        native = (ani_media.get("title") or {}).get("native") or ""
        bgm_data = None
        for q in (native, title):
            if not q: continue
            for h in bangumi.search(q)[:1]:
                bid = h.get("id")
                if bid:
                    bgm_data = bangumi.fetch(bid)
                    break
            if bgm_data: break

        entry = {
            "title_raw": title,
            "title_main_zh": title,
            "section_origin": section,
            "user_rating": user_rating,
            "episodes_in_doc": eps,
            "source_doc_raw": doc_raw,
        }
        matched = {"needs_review": False}
        now_iso = datetime.now().isoformat(timespec="seconds")
        rec = _build_record(entry, matched, None, ani_media, mal_data, bgm_data,
                            genre_zh, {}, now_iso)
        # 用 doc 原文蓋掉 primary_zh (避免 Bangumi 把第四季合併到主作品)
        rec["titles"]["primary_zh"] = title

        # 下載封面
        cover_url = (rec.get("cover") or {}).get("url")
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", anime_id)
        dest = COVERS_DIR / f"{slug}.jpg"
        if download_cover(cover_url, dest):
            rec["cover"]["local"] = f"data/covers/{slug}.jpg"
            rec["enrichment"]["cover_at"] = now_iso
            print(f"  cover → {dest.name}")
        anime[anime_id] = rec
        print(f"  ✓ {rec['titles']['primary_zh']}  ({rec.get('year')}, {rec.get('episodes')}ep)")

    anime_db["anime"] = anime
    anime_db["updated_at"] = datetime.now().isoformat(timespec="seconds")
    json.dump(anime_db, open(ANIME_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n寫入 {ANIME_JSON}，總 {len(anime)} 筆")


if __name__ == "__main__":
    main()
