"""把先前的 stub (anilist:9000xxx 沒封面沒簡介) 再嘗試找正確的 AniList id。
策略：
  - Bangumi 搜尋 (繁+簡) 找到主作品 → 用其 name (日文) 餵 AniList
  - AniList 搜尋多種 query (title 清掉副標、清掉 OVA/SP 後綴)
  - 候選依 fuzzy ratio + 季別比對 + 集數比對排序
  - confidence ≥ THRESHOLD 才接受；接受時更新 anime.json (新 anilist:<real> 取代舊 anilist:9000xxx)
  - 同步更新 season_picks.json / user_lists.json 內的引用
"""
from __future__ import annotations
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
from rapidfuzz import fuzz
from opencc import OpenCC
from PIL import Image

from config import (
    ANIME_JSON, COVERS_DIR, COVER_MAX_PX, GENRE_ZH_MAP, USER_AGENT, REQUEST_TIMEOUT,
    USER_LISTS,
)
from pipeline.enrich import _build_record
from pipeline.match import _extract_season, _cjk_only
from services import anilist, bangumi, jikan

t2s = OpenCC("t2s")
def to_simp(s): return t2s.convert(s) if s else ""

SEASON_PICKS = ANIME_JSON.parent / "season_picks.json"

# 從 entry title 清掉雜訊
NOISE_RE = re.compile(
    r"\s*(?:OVA|OAD|OAV|SP|SE|劇場版|総集編|総集篇|總集編|總集篇|"
    r"特別篇|特別編|外傳|番外編|番外篇|PV)\s*$",
    re.IGNORECASE,
)
def clean_title(s):
    if not s: return ""
    prev = None
    while prev != s:
        prev = s
        s = NOISE_RE.sub("", s).strip()
    return s


def char_ratio(a, b):
    if not a or not b: return 0
    return fuzz.ratio(to_simp(a), to_simp(b))


def find_real_anilist_id(title):
    """嘗試找到對應的真實 AniList id。回傳 (id, ani_media, bgm_subject) 或 None"""
    title_simp = to_simp(title)
    cleaned = clean_title(title)
    cleaned_simp = to_simp(cleaned)

    # 先 Bangumi 搜尋拿候選 (含日文 name)
    bgm_candidates = []
    for q in {title, title_simp, cleaned, cleaned_simp}:
        if not q: continue
        for h in bangumi.search(q)[:5]:
            bid = h.get("id")
            if bid and h not in bgm_candidates:
                bgm_candidates.append(h)

    # 收集所有可能的 AniList query (Bangumi name 含 ja + name_cn)
    queries = set()
    if cleaned: queries.add(cleaned)
    if cleaned_simp != cleaned: queries.add(cleaned_simp)
    for h in bgm_candidates[:6]:
        for k in ("name", "name_cn"):
            v = h.get(k)
            if v: queries.add(v)

    # AniList 搜尋每個 query，累積候選
    ani_pool = {}
    for q in list(queries)[:8]:
        for m in (anilist.search(q) or []):
            if m and m.get("id") and m["id"] not in ani_pool:
                ani_pool[m["id"]] = m

    if not ani_pool:
        return None

    # 對每個 anilist 候選評分
    entry_season = _extract_season(title)
    best_score = 0
    best_pair = None
    for aid, m in ani_pool.items():
        t = m.get("title") or {}
        cand_titles = [t.get("english"), t.get("romaji"), t.get("native"),
                       t.get("english") or "", t.get("romaji") or ""]

        # CJK char ratio
        cjk_target = to_simp(_cjk_only(title))
        cjk_native = to_simp(_cjk_only(t.get("native") or ""))
        score = 0

        # 簡體中文 vs Bangumi name_cn
        for h in bgm_candidates[:6]:
            zh = h.get("name_cn") or h.get("name") or ""
            r1 = char_ratio(title, zh)
            r2 = char_ratio(cleaned, zh)
            score = max(score, max(r1, r2))

        # vs anilist 各標題
        for ct in cand_titles:
            if not ct: continue
            r = max(
                fuzz.ratio(to_simp(cleaned), to_simp(ct)),
                fuzz.token_set_ratio(cleaned, ct),
            )
            score = max(score, r)
        if cjk_target and cjk_native:
            score = max(score, fuzz.ratio(cjk_target, cjk_native))

        # 季別不符 → 大幅降分
        cand_season = max(_extract_season(t.get("english")),
                          _extract_season(t.get("romaji")),
                          _extract_season(t.get("native")))
        # 只在「兩邊都有明確 season marker」時才視為衝突；entry 顯式 S2+ vs cand 預設 S1 → 降分
        ct_has_explicit = any(s and any(re.search(p, s) for p in [
            r"第\s*\d+\s*[季期部]", r"Season\s+\d+", r"\b\d+(nd|rd|th|st)\s+Season\b",
            r"\bS\d+\b", r"\s+\d+$"
        ]) for s in cand_titles if s)
        if entry_season > 1 and ct_has_explicit and cand_season != entry_season:
            score *= 0.4
        elif entry_season > 1 and not ct_has_explicit:
            score *= 0.85
        elif entry_season > 1 and cand_season == entry_season:
            score = min(score + 5, 100)

        if score > best_score:
            best_score = score
            # 找匹配的 bangumi (cjk 對應)
            best_bgm = None
            for h in bgm_candidates[:6]:
                bzh = h.get("name_cn") or h.get("name") or ""
                if char_ratio(cleaned, bzh) >= 60:
                    best_bgm = h; break
            best_pair = (aid, m, best_bgm)

    THRESHOLD = 60
    if best_score >= THRESHOLD and best_pair:
        return best_pair, best_score
    return None, best_score


def download_cover(url, dest):
    if not url: return False
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
        print(f"  [cover] {e}")
        return False


def main():
    anime_db = json.load(open(ANIME_JSON, encoding="utf-8"))
    anime = anime_db["anime"]
    genre_zh = json.load(open(GENRE_ZH_MAP, encoding="utf-8"))

    stubs = [(aid, rec) for aid, rec in anime.items()
             if rec.get("enrichment", {}).get("synthetic_source") == "stub"]
    print(f"嘗試找正確 AniList id 給 {len(stubs)} 個 stub...\n")

    id_remap = {}  # old_anilist_9xxx → new_anilist_real
    resolved = 0
    failed = 0
    for old_aid, rec in stubs:
        title = rec["titles"]["primary_zh"]
        result = find_real_anilist_id(title)
        if not result or result[0] is None:
            failed += 1
            score = result[1] if result else 0
            print(f"  ✗ {old_aid}  {title}  (best score={score:.0f})")
            continue
        (real_aid, ani_media, bgm_hit), score = result
        new_aid = f"anilist:{real_aid}"

        # 若新 id 已在 anime.json (例如別人佔用)，跳過避免覆寫
        if new_aid in anime and new_aid != old_aid:
            failed += 1
            print(f"  ⚠ {old_aid}  {title}  → AniList:{real_aid} 已被其他 entry 占用，skip")
            continue

        # Build 真實 record
        bgm_data = bangumi.fetch(bgm_hit["id"]) if bgm_hit else None
        mal_data = jikan.fetch(ani_media.get("idMal")) if ani_media.get("idMal") else None
        entry = {
            "title_raw": title,
            "title_main_zh": title,
            "section_origin": rec.get("section_origin", "已完結"),
            "user_rating": (rec.get("user") or {}).get("self_rating_raw"),
            "episodes_in_doc": (rec.get("user") or {}).get("doc_episode_count"),
            "source_doc_raw": rec.get("source_doc_raw") or title,
        }
        matched = {"needs_review": False}
        now_iso = datetime.now().isoformat(timespec="seconds")
        new_rec = _build_record(entry, matched, None, ani_media, mal_data, bgm_data,
                                genre_zh, {}, now_iso)
        # 標題用我們原本的 (避免被 Bangumi 主作品名覆蓋掉「第二季」這類後綴)
        new_rec["titles"]["primary_zh"] = title

        # 下載封面
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", new_aid)
        dest = COVERS_DIR / f"{slug}.jpg"
        cover_url = (new_rec.get("cover") or {}).get("url")
        if download_cover(cover_url, dest):
            new_rec["cover"]["local"] = f"data/covers/{slug}.jpg"
            new_rec["enrichment"]["cover_at"] = now_iso

        anime[new_aid] = new_rec
        if new_aid != old_aid:
            del anime[old_aid]
            id_remap[old_aid] = new_aid

        resolved += 1
        bgm_label = f"+bgm:{bgm_hit['id']}" if bgm_hit else ""
        print(f"  ✓ {old_aid}  → AniList:{real_aid}  {bgm_label}  ({score:.0f}) {title}")

    anime_db["anime"] = anime
    anime_db["updated_at"] = datetime.now().isoformat(timespec="seconds")
    json.dump(anime_db, open(ANIME_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 同步 user_lists.json
    if id_remap:
        try:
            ul = json.load(open(USER_LISTS, encoding="utf-8"))
            new_recommend = [id_remap.get(x, x) for x in ul.get("recommend", [])]
            if new_recommend != ul.get("recommend"):
                ul["recommend"] = new_recommend
                json.dump(ul, open(USER_LISTS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print(f"\n更新 user_lists.json 內 {sum(1 for k in id_remap if k in (ul.get('recommend') or []))} 個 id")
        except Exception as e:
            print(f"  user_lists.json 更新失敗: {e}")

    # 同步 season_picks.json
    if id_remap and SEASON_PICKS.exists():
        try:
            sp = json.load(open(SEASON_PICKS, encoding="utf-8"))
            new_ids = [id_remap.get(x, x) for x in sp.get("ids", [])]
            if new_ids != sp.get("ids"):
                sp["ids"] = new_ids
                json.dump(sp, open(SEASON_PICKS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print(f"更新 season_picks.json 引用")
        except Exception as e:
            print(f"  season_picks.json 更新失敗: {e}")

    print(f"\n=== 結果 ===")
    print(f"成功 re-resolve: {resolved}")
    print(f"仍 stub: {failed}")
    print(f"總 anime records: {len(anime)}")


if __name__ == "__main__":
    main()
