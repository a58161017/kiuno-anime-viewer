"""自動嘗試解掉 unresolved.json：
  - low_confidence: 若 top 候選的簡體標題 vs entry 簡體相似度 >= 閾值 → 接受
  - no_match: 用清乾淨的 title 再 search 一次 (AniList + Bangumi)
不確定的就保留在 unresolved.json 等使用者手動。
"""
from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz
from opencc import OpenCC
from config import UNRESOLVED, ANILIST_GRAPHQL
from services import anilist, bangumi
from services.http import cached_request

t2s = OpenCC("t2s")
def to_simp(s):
    return t2s.convert(s) if s else ""

# 各種干擾後綴 — 比對前先去掉
NOISE_SUFFIXES = re.compile(
    r"\s*(?:OVA|OAD|OAV|SP|SE|劇場版|総集編|総集篇|總集編|總集篇|"
    r"特別篇|特別編|外傳|番外編|番外篇|"
    r"第\s*[一二三四五六七八九十\d]+\s*[季期部]|"
    r"\d+(?:nd|rd|th|st)?\s*Season|Season\s*\d+|"
    r"S\d+|"
    r"-\s*第二季|-\s*第三季|"
    r"\(\d+\)|（\d+）"
    r")\s*$",
    re.IGNORECASE,
)

def clean_title(s):
    if not s:
        return ""
    prev = None
    while prev != s:
        prev = s
        s = NOISE_SUFFIXES.sub("", s).strip()
    return s

def char_ratio(a, b):
    """嚴格的字元級 ratio (簡體 vs 簡體)"""
    if not a or not b:
        return 0
    a = to_simp(a)
    b = to_simp(b)
    return fuzz.ratio(a, b)


# 從 entry/candidate 標題抓季別（重用 match.py 的邏輯）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.match import _extract_season

def season_compatible(entry_title, *cand_titles):
    """entry 標示 S2+ 時，候選任一標題也要帶相同 season marker 才視為相容。
    entry season=1 (default) 時不限制。"""
    es = _extract_season(entry_title)
    if es <= 1:
        return True
    for ct in cand_titles:
        if not ct: continue
        cs = _extract_season(ct)
        if cs == es:
            return True
    return False

def main():
    u = json.load(open(UNRESOLVED, encoding="utf-8"))
    print(f"unresolved: {len(u)}")

    proposals = {}  # slug -> anilist_id

    # ---- pass 1: low_confidence 用嚴格比對自動接受最佳候選 ----
    auto_accepted = 0
    for slug, item in list(u.items()):
        if item.get("manual_override"):
            continue  # 已有人工填的不動
        if item.get("reason") != "low_confidence":
            continue
        cands = item.get("candidates") or []
        if not cands:
            continue
        entry_title = item.get("title_main_zh") or item.get("title_raw") or ""
        for cand in cands[:3]:
            best_zh = cand.get("title_zh") or ""
            best_native = cand.get("title_native") or ""
            best_eng = cand.get("title_english") or ""
            r1 = char_ratio(entry_title, best_zh)
            r2 = char_ratio(clean_title(entry_title), clean_title(best_zh))
            r3 = char_ratio(clean_title(entry_title), best_native)
            best_r = max(r1, r2, r3)
            if best_r >= 75 and season_compatible(entry_title, best_zh, best_native, best_eng):
                proposals[slug] = cand["anilist_id"]
                auto_accepted += 1
                print(f"  ✓ auto-accept: {entry_title}  →  {best_zh or best_native or best_eng}  (ratio={best_r:.0f}, AniList:{cand['anilist_id']})")
                break

    print(f"\n=== pass 1: low_confidence auto-accepted = {auto_accepted} ===\n")

    # ---- pass 2: no_match 用清乾淨的 title 重 search (AniList + Bangumi) ----
    new_search_hits = 0
    no_match_items = [(k, v) for k, v in u.items()
                      if v.get("reason") == "no_match" and not v.get("manual_override") and k not in proposals]
    print(f"no_match to retry: {len(no_match_items)}")
    for slug, item in no_match_items:
        title_raw = item.get("title_raw") or item.get("title_main_zh") or ""
        cleaned_t = clean_title(title_raw)
        cleaned_simp = to_simp(cleaned_t)

        candidates = []

        # Bangumi search (繁/簡)
        for q in (cleaned_t, cleaned_simp):
            if not q:
                continue
            for h in bangumi.search(q)[:3]:
                bid = h.get("id")
                if bid:
                    candidates.append({"src": "bangumi", "h": h})

        # AniList search (繁/簡/cleaned)
        for q in (cleaned_t, cleaned_simp, title_raw):
            if not q:
                continue
            for m in anilist.search(q)[:3]:
                if m and m.get("id"):
                    candidates.append({"src": "anilist", "m": m})

        # 從這些候選找一個簡體標題與 entry 相似度 >= 70 的
        best_id = None
        best_ratio = 0
        best_label = ""
        for c in candidates:
            if c["src"] == "bangumi":
                h = c["h"]
                bgm_zh = h.get("name_cn") or h.get("name") or ""
                r = char_ratio(cleaned_t, bgm_zh)
                # 從 bangumi 拿到 ja name 後再 fetch anilist 找對應 id
                if r >= 70:
                    ja = h.get("name") or h.get("name_cn")
                    for m in anilist.search(ja)[:1]:
                        if m and m.get("id"):
                            t = m.get("title") or {}
                            if not season_compatible(title_raw, bgm_zh, t.get("native"), t.get("english"), t.get("romaji")):
                                continue
                            if r > best_ratio:
                                best_ratio = r
                                best_id = m["id"]
                                best_label = bgm_zh + " → " + (t.get("romaji") or "")
                            break
            else:
                m = c["m"]
                native = m.get("title", {}).get("native") or ""
                eng = m.get("title", {}).get("english") or ""
                r = max(char_ratio(cleaned_t, native), char_ratio(cleaned_simp, native))
                if r >= 70 and season_compatible(title_raw, m.get("title", {}).get("native"), m.get("title", {}).get("english"), m.get("title", {}).get("romaji")):
                    if r > best_ratio:
                        best_ratio = r
                        best_id = m["id"]
                        best_label = native or eng

        if best_id:
            proposals[slug] = best_id
            new_search_hits += 1
            print(f"  ✓ found: {title_raw}  →  {best_label}  (AniList:{best_id}, ratio={best_ratio:.0f})")

    print(f"\n=== pass 2: no_match new search hits = {new_search_hits} ===\n")

    # ---- 寫回 unresolved.json 的 manual_override ----
    for slug, aid in proposals.items():
        u[slug]["manual_override"] = f"anilist:{aid}"

    json.dump(u, open(UNRESOLVED, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n寫入 {len(proposals)} 個 manual_override 到 unresolved.json")
    print("接下來執行：python run.py match --retry-unresolved")


if __name__ == "__main__":
    main()
