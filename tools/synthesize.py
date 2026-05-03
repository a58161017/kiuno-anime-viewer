"""把仍 unresolved 的條目通通塞進 anime.json：
- 優先嘗試 Bangumi 搜尋，找到就用 Bangumi 的中文資料 + 封面，分配 anilist:9xxxxxx id
- Bangumi 也沒找到 → 用 entry 自身的標題作 stub (沒封面、沒簡介)
最後：unresolved 清空、anime.json 加進新條目、再跑 download + graph。
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rapidfuzz import fuzz
from opencc import OpenCC

from config import ANIME_JSON, ENTRIES_RAW, GENRE_ZH_MAP, UNRESOLVED
from services import bangumi
from services.rating import aggregate, star_tag_value

t2s = OpenCC("t2s")
s2tw = OpenCC("s2twp")


def to_simp(s):
    return t2s.convert(s) if s else ""

def to_trad(s):
    return s2tw.convert(s) if s else s


def char_ratio(a, b):
    if not a or not b:
        return 0
    return fuzz.ratio(to_simp(a), to_simp(b))


HTML_RE = re.compile(r"<[^>]+>")
def strip_html(s):
    if not s: return None
    s = HTML_RE.sub("", s)
    return s.replace("<br>", "\n").strip() or None


# Bangumi platform → our format
PLATFORM_MAP = {
    "TV": "tv",
    "OVA": "ova",
    "Movie": "movie",
    "WEB": "ona",
}


def build_record_from_bangumi(entry, bgm_subject, anilist_id_str):
    """從 Bangumi subject 建一個 anime 記錄。"""
    name = bgm_subject.get("name") or ""
    name_cn_raw = bgm_subject.get("name_cn") or ""
    name_cn = to_trad(name_cn_raw)
    summary = to_trad(bgm_subject.get("summary") or "")
    date_str = bgm_subject.get("date") or ""
    year = None
    if date_str and len(date_str) >= 4 and date_str[:4].isdigit():
        year = int(date_str[:4])

    platform = bgm_subject.get("platform") or "TV"
    fmt = PLATFORM_MAP.get(platform, "tv")

    # Bangumi rating
    rating = bgm_subject.get("rating") or {}
    score = rating.get("score") or None
    sources = {}
    if score:
        sources["bangumi"] = {
            "id": bgm_subject.get("id"),
            "score": score,
            "scale": 10,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
    aggregated = aggregate(sources)

    # Bangumi tags → 我們的 tags（前 10 個 by count）
    tags = []
    for t in (bgm_subject.get("tags") or [])[:10]:
        n = t.get("name")
        if n:
            tags.append(to_trad(n))

    # Studios / 製作 from infobox
    studios = []
    for box in bgm_subject.get("infobox") or []:
        if not isinstance(box, dict): continue
        if box.get("key") in ("動畫製作", "动画制作", "製作", "制作", "Animation Studio"):
            v = box.get("value")
            if isinstance(v, str): studios.append(to_trad(v))
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, dict) and x.get("v"): studios.append(to_trad(x["v"]))
            break

    # Episodes
    eps = bgm_subject.get("eps") or bgm_subject.get("total_episodes") or None

    # Cover URL — 用 large
    images = bgm_subject.get("images") or {}
    cover_url = images.get("large") or images.get("medium") or images.get("common") or None

    # Derived tags
    section = entry.get("section_origin")
    if year: tags.append(f"年份-{year}")
    if star_tag_value(aggregated): tags.append(star_tag_value(aggregated))
    for s in studios: tags.append(f"studio-{s}")
    if section: tags.append(section)
    if fmt: tags.append(f"format-{fmt}")
    tags.append("source-bangumi")

    record = {
        "id": anilist_id_str,
        "format": fmt,
        "section_origin": section,
        "titles": {
            "primary_zh": entry.get("title_raw") or name_cn or entry.get("title_main_zh"),
            "zh_aliases": [n for n in [name_cn] if n] or [],
            "ja": name,
            "ja_romaji": None,
            "en": None,
        },
        "year": year,
        "season": None,
        "episodes": eps,
        "studios": studios,
        "categories": [],   # Bangumi 沒明確 genre → 空，使用者可手動補
        "tags": tags,
        "rating": {"score": aggregated, "sources": sources},
        "synopsis_zh": strip_html(summary),
        "synopsis_en": None,
        "cover": {"url": cover_url, "local": None},
        "external_links": {
            "bangumi": f"https://bgm.tv/subject/{bgm_subject.get('id')}",
        },
        "relations": {"prequel": [], "sequel": [], "side_story": []},
        "user": {
            "self_rating_raw": entry.get("user_rating"),
            "doc_episode_count": entry.get("episodes_in_doc"),
            "added_at": datetime.now().isoformat(timespec="seconds"),
        },
        "source_doc_raw": entry.get("source_doc_raw"),
        "enrichment": {
            "anilist_at": None,
            "mal_at": None,
            "bangumi_at": datetime.now().isoformat(timespec="seconds"),
            "cover_at": None,
            "needs_review": True,
            "synthetic": True,
            "synthetic_source": "bangumi",
        },
    }
    return record


def build_record_stub(entry, anilist_id_str):
    """Bangumi 也找不到時的最小 stub。沒封面、沒簡介。"""
    section = entry.get("section_origin")
    fmt = "movie" if section == "劇場版" else "tv"
    tags = []
    if section: tags.append(section)
    if fmt: tags.append(f"format-{fmt}")
    tags.append("source-stub")
    return {
        "id": anilist_id_str,
        "format": fmt,
        "section_origin": section,
        "titles": {
            "primary_zh": entry.get("title_raw") or entry.get("title_main_zh"),
            "zh_aliases": [],
            "ja": None, "ja_romaji": None, "en": None,
        },
        "year": None, "season": None,
        "episodes": entry.get("episodes_in_doc"),
        "studios": [],
        "categories": [],
        "tags": tags,
        "rating": {"score": None, "sources": {}},
        "synopsis_zh": None, "synopsis_en": None,
        "cover": {"url": None, "local": None},
        "external_links": {},
        "relations": {"prequel": [], "sequel": [], "side_story": []},
        "user": {
            "self_rating_raw": entry.get("user_rating"),
            "doc_episode_count": entry.get("episodes_in_doc"),
            "added_at": datetime.now().isoformat(timespec="seconds"),
        },
        "source_doc_raw": entry.get("source_doc_raw"),
        "enrichment": {
            "anilist_at": None, "mal_at": None, "bangumi_at": None,
            "cover_at": None, "needs_review": True,
            "synthetic": True, "synthetic_source": "stub",
        },
    }


def main():
    raw_db = json.load(open(ENTRIES_RAW, encoding="utf-8"))["entries"]
    u = json.load(open(UNRESOLVED, encoding="utf-8"))
    anime_db = json.load(open(ANIME_JSON, encoding="utf-8"))
    anime = anime_db["anime"]

    # 找出最大已用的 anilist id，從那之後的高位往上分配（避開真實 id 範圍）
    SYNTH_BASE = 9_000_000
    next_id = SYNTH_BASE
    used_ids = set()
    for k in anime.keys():
        if k.startswith("anilist:"):
            try:
                used_ids.add(int(k.split(":", 1)[1]))
            except ValueError:
                pass

    bangumi_used = 0
    stub_used = 0
    skipped = 0
    new_records = []

    targets = [(slug, item) for slug, item in u.items() if not item.get("manual_override")]
    print(f"處理 {len(targets)} 條 unresolved (沒有 manual_override 的)")
    for slug, item in targets:
        entry = raw_db.get(slug)
        if not entry:
            skipped += 1
            continue
        title_zh = entry.get("title_main_zh") or ""
        title_raw = entry.get("title_raw") or title_zh
        title_simp = to_simp(title_raw)

        # Bangumi search
        hits = []
        for q in (title_raw, title_simp, title_zh):
            if not q: continue
            res = bangumi.search(q)
            for h in res[:5]:
                if h not in hits:
                    hits.append(h)
            if hits: break

        # Pick best by char_ratio
        chosen = None
        best_r = 0
        for h in hits[:8]:
            zh = h.get("name_cn") or h.get("name") or ""
            r = char_ratio(title_raw, zh)
            if r > best_r:
                best_r = r; chosen = h

        # 取嚴格一點：要 ≥ 60 才視為 bangumi 命中
        while next_id in used_ids:
            next_id += 1
        new_aid = f"anilist:{next_id}"
        next_id += 1

        if chosen and best_r >= 60:
            detail = bangumi.fetch(chosen["id"])
            if detail:
                rec = build_record_from_bangumi(entry, detail, new_aid)
                anime[new_aid] = rec
                new_records.append((new_aid, rec, "bangumi", best_r))
                bangumi_used += 1
                continue

        # Fallback stub
        rec = build_record_stub(entry, new_aid)
        anime[new_aid] = rec
        new_records.append((new_aid, rec, "stub", 0))
        stub_used += 1

    anime_db["anime"] = anime
    anime_db["updated_at"] = datetime.now().isoformat(timespec="seconds")
    json.dump(anime_db, open(ANIME_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 清掉 unresolved（targets 都被處理了）
    new_unresolved = {k: v for k, v in u.items() if v.get("manual_override")}
    json.dump(new_unresolved, open(UNRESOLVED, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n=== 結果 ===")
    print(f"Bangumi 命中: {bangumi_used}")
    print(f"Stub (找不到): {stub_used}")
    print(f"Skipped: {skipped}")
    print(f"unresolved 剩餘: {len(new_unresolved)}\n")

    print("=== Bangumi 命中的條目 ===")
    for aid, rec, src, r in new_records:
        if src == "bangumi":
            print(f"  {aid}  {rec['titles']['primary_zh']}  (year={rec['year']}, ratio={r})")

    print("\n=== Stub 條目（無封面、無簡介，需要你手動補資料）===")
    for aid, rec, src, _ in new_records:
        if src == "stub":
            print(f"  {aid}  {rec['titles']['primary_zh']}")


if __name__ == "__main__":
    main()
