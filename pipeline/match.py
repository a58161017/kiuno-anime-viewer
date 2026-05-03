"""Match raw entries to AniList / MAL / Bangumi ids.

Strategy (per entry):
  1. Bangumi search with the Chinese title -> get candidates with ja/en names.
  2. AniList search with the best Bangumi-derived ja/en name (or original Chinese fallback).
  3. AniList result already includes idMal (no separate MAL search needed).
  4. Score each candidate combo; auto-accept if confidence >= MATCH_AUTO_ACCEPT,
     write to entries.matched.json with `needs_review` if 0.6 <= conf < 0.85,
     drop into unresolved.json otherwise (with top-3 candidates for human pick).

Output files:
  - data/entries.matched.json     {slug: {anilist_id, mal_id, bangumi_id, confidence, needs_review, ...}}
  - data/unresolved.json          {slug: {title_raw, candidates: [...], manual_override: null}}

Re-runnable. --retry-unresolved reads unresolved.json's manual_override and applies them.
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from config import (
    DATA, ENTRIES_RAW, MATCH_AUTO_ACCEPT, MATCH_REVIEW_THRESHOLD, UNRESOLVED,
)
from services import anilist, bangumi

try:
    from opencc import OpenCC
    _t2s = OpenCC("t2s")
    def _to_simplified(s: str) -> str:
        return _t2s.convert(s) if s else s
except Exception:
    def _to_simplified(s: str) -> str:
        return s

ENTRIES_MATCHED = DATA / "entries.matched.json"

# AniList format codes for filter / scoring
FORMAT_TV = {"TV", "TV_SHORT", "ONA"}
FORMAT_MOVIE = {"MOVIE"}


def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[\s\-:：–—／/\.\(\)\[\]『』「」!！?？]", "", s)
    return s


_CJK_RE = re.compile(r"[㐀-鿿぀-ヿ]+")


def _cjk_only(s: Optional[str]) -> str:
    """Extract only CJK runs (Han + kana). Used to compare zh-mixed-with-latin titles
    against pure-CJK candidates without length-mismatch penalising the ratio."""
    if not s:
        return ""
    return "".join(_CJK_RE.findall(s))


_CN_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
# 多種季別表達:「第二季」、「Season 2」、「2nd Season」、" 2"/" 3" 結尾、「II」「III」、「S2」
_SEASON_PATTERNS = [
    re.compile(r"第\s*(\d+)\s*[季期部]"),
    re.compile(r"第\s*([一二三四五六七八九十])\s*[季期部]"),
    re.compile(r"\bSeason\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\b(\d+)(?:nd|rd|th|st)\s+Season\b", re.IGNORECASE),
    re.compile(r"\bS(\d+)\b"),
    re.compile(r"\s+(\d+)$"),                           # "Shukufuku wo! 2"
    re.compile(r"\s+(II|III|IV|V|VI|VII|VIII|IX)\b"),  # "Foo II"
]
_ROMAN = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9}


def _extract_season(s: Optional[str]) -> int:
    """Return season number (1 if no marker found)."""
    if not s:
        return 1
    for pat in _SEASON_PATTERNS:
        m = pat.search(s)
        if not m:
            continue
        v = m.group(1)
        if v in _CN_NUM:
            return _CN_NUM[v]
        if v in _ROMAN:
            return _ROMAN[v]
        try:
            n = int(v)
            if 1 <= n <= 20:  # sanity
                return n
        except ValueError:
            pass
    return 1


def _score_candidate(entry: dict, anilist_media: dict, bangumi_subject: Optional[dict]) -> float:
    """0~1 confidence score for an (entry, AniList result, optional Bangumi result).

    Chinese titles cannot fuzzy-match Japanese/English ones, so we lean heavily on:
      - Bangumi's Chinese name (when present) fuzzy-matched against the Doc title
      - Episode count exact match (Doc's trailing-(n) vs AniList episodes)
      - Format hint (movie vs tv)
    """
    titles = anilist_media.get("title") or {}
    target_full = entry.get("title_raw") or entry.get("title_main_zh") or ""
    target_main = entry.get("title_main_zh") or ""
    target_main_simp = _to_simplified(target_main)
    target_cjk = _cjk_only(target_main)
    target_cjk_simp = _to_simplified(target_cjk)

    # ----- Cross-source consistency check ----------------------------------
    # We score (anilist, bangumi) pairs, but a high Bangumi-vs-Chinese-title score
    # is meaningless if the Bangumi subject and the AniList Media are NOT the same
    # work. Verify by comparing Bangumi.name (Japanese) with AniList.title.native:
    # if they don't share enough kanji, drop Bangumi from the pairing.
    if bangumi_subject:
        b_native_cjk = _to_simplified(_cjk_only(bangumi_subject.get("name") or ""))
        # Bangumi.name is sometimes Latin only (e.g. "DEATH NOTE"); fall back to
        # name_cn's CJK chars (simplified) to compare against AniList native (kanji).
        if not b_native_cjk and bangumi_subject.get("name_cn"):
            b_native_cjk = _to_simplified(_cjk_only(bangumi_subject.get("name_cn") or ""))
        a_native_cjk = _to_simplified(_cjk_only(titles.get("native") or ""))
        # partial_ratio handles "鬼滅の刃" being a substring of "鬼滅の刃無限列車編"
        # (same franchise, different cut) without penalising the length gap, while
        # still rejecting "死亡笔记" vs "死亡游戏で飯を食う" (~67%).
        if b_native_cjk and a_native_cjk and fuzz.partial_ratio(b_native_cjk, a_native_cjk) < 70:
            bangumi_subject = None

    # ----- fuzzy: prefer Chinese-vs-Chinese match (Bangumi) -----
    fuzzy_zh = 0
    fuzzy_other = 0

    if bangumi_subject:
        for b_name in (bangumi_subject.get("name_cn"), bangumi_subject.get("name")):
            if not b_name:
                continue
            b_cjk = _cjk_only(b_name)
            b_cjk_simp = _to_simplified(b_cjk)
            # Use `ratio` (Levenshtein, length-aware). Three tiers in decreasing rigour:
            #   1. full-string simp-vs-simp
            #   2. full-string raw-vs-raw
            #   3. CJK-only-vs-CJK-only (lets "灌籃高手 The First Slam Dunk" match "灌篮高手")
            f = max(
                fuzz.ratio(target_main_simp, _to_simplified(b_name)),
                fuzz.ratio(target_main, b_name),
                fuzz.ratio(target_cjk_simp, b_cjk_simp) if (target_cjk and b_cjk) else 0,
                fuzz.ratio(target_cjk, b_cjk) if (target_cjk and b_cjk) else 0,
            )
            fuzzy_zh = max(fuzzy_zh, f)

    for c in (titles.get("romaji"), titles.get("english"), titles.get("native")):
        if not c:
            continue
        n_target = _norm(target_full)
        n_c = _norm(c)
        if n_target and n_c and n_target == n_c:
            return 1.0
        is_native = (c == titles.get("native"))
        if is_native:
            c_cjk = _cjk_only(c)
            f = max(
                fuzz.ratio(target_main, c),
                fuzz.ratio(target_main_simp, c),
                fuzz.ratio(target_cjk, c_cjk) if (target_cjk and c_cjk) else 0,
                fuzz.ratio(target_cjk_simp, _to_simplified(c_cjk)) if (target_cjk and c_cjk) else 0,
            )
        else:
            f = fuzz.token_set_ratio(target_main, c)
        fuzzy_other = max(fuzzy_other, f)

    # Use the higher of the two fuzzy buckets, but Chinese-vs-Chinese is more reliable
    base_fuzzy = max(fuzzy_zh, fuzzy_other)

    # ----- strong signal: exact episode match -----
    eps_doc = entry.get("episodes_in_doc")
    eps_a = anilist_media.get("episodes")
    eps_match = bool(eps_doc and eps_a and eps_doc == eps_a)

    # ----- format hint match -----
    fmt_hint = entry.get("format_hint")
    a_format = anilist_media.get("format")
    fmt_match = (
        (fmt_hint == "movie" and a_format in FORMAT_MOVIE)
        or (fmt_hint == "tv" and a_format in FORMAT_TV)
    )

    # ----- season number match (critical for franchises with same episode counts) -----
    entry_season = _extract_season(entry.get("title_raw") or entry.get("title_main_zh"))
    cand_season = max(
        _extract_season(titles.get("english")),
        _extract_season(titles.get("romaji")),
        _extract_season(titles.get("native")),
    )
    season_conflict = (entry_season != cand_season)

    # Combine: episode-match is the strongest discriminator (very low collision rate
    # for non-trivial counts), so it acts as a near-confirmation when paired with any
    # plausible fuzzy signal.
    score = 0.0
    if eps_match and base_fuzzy >= 30:
        # Episode count + a passable name signal -> auto-accept territory
        score = 0.92 + min(base_fuzzy / 100.0 * 0.06, 0.06)
    elif eps_match:
        score = 0.7 + (base_fuzzy / 100.0) * 0.2
    elif fuzzy_zh >= 90:
        score = 0.9
    elif fuzzy_zh >= 70:
        score = 0.75
    elif fuzzy_other >= 90:
        score = 0.85
    elif fuzzy_other >= 75:
        score = 0.7
    elif base_fuzzy >= 60:
        score = 0.5
    else:
        score = base_fuzzy / 200.0  # 0 ~ 0.5 floor

    if fmt_match:
        score += 0.03

    # Season penalty: same-franchise wrong season is the most common false positive
    # (e.g. Doc 「Konosuba 第二季」(10ep) wrongly matches AniList S1 (10ep) since
    # episode count happens to match). When we know the entry's season AND the
    # candidate's season but they disagree, slash the score.
    if season_conflict:
        score *= 0.4  # downgrade rather than zero — no-marker entries should still match
    elif entry_season > 1 and cand_season == entry_season:
        score = min(score + 0.05, 1.0)  # explicit-season match: small bonus

    return min(score, 1.0)


def _candidate_from_pair(anilist_media: dict, bangumi_subject: Optional[dict], confidence: float) -> dict:
    titles = anilist_media.get("title") or {}
    return {
        "anilist_id": anilist_media.get("id"),
        "mal_id": anilist_media.get("idMal"),
        "bangumi_id": (bangumi_subject or {}).get("id"),
        "title_romaji": titles.get("romaji"),
        "title_english": titles.get("english"),
        "title_native": titles.get("native"),
        "title_zh": (bangumi_subject or {}).get("name_cn") or (bangumi_subject or {}).get("name"),
        "year": (anilist_media.get("startDate") or {}).get("year"),
        "format": anilist_media.get("format"),
        "episodes": anilist_media.get("episodes"),
        "confidence": round(confidence, 3),
    }


def match_one(entry: dict) -> dict:
    """Return {best, candidates, confidence, needs_review} for a single entry."""
    title_zh = entry.get("title_main_zh") or entry.get("title_raw") or ""
    title_raw = entry.get("title_raw") or title_zh
    title_subtitle = entry.get("title_subtitle")
    fmt_hint = entry.get("format_hint")

    # Step 1: Bangumi search — Bangumi's search engine indexes simplified Chinese,
    # so a traditional-Chinese query like "我獨自升級" returns garbage. Send BOTH
    # the original AND a simplified version so titles like "我独自升级" hit.
    bgm_queries: list[str] = []
    def _add_query(q: str):
        if q and q not in bgm_queries:
            bgm_queries.append(q)
    if title_zh:
        _add_query(title_zh)
        _add_query(_to_simplified(title_zh))
    if title_subtitle and title_raw:
        _add_query(title_raw)
        _add_query(_to_simplified(title_raw))

    # Take top 2 from each query so that the "correct" simplified-Chinese hit isn't
    # crowded out by 4 wrong results from the traditional-Chinese query.
    bgm_hits: list[dict] = []
    seen_bgm_ids: set[int] = set()
    PER_QUERY = 2
    for q in bgm_queries:
        added_for_q = 0
        for h in bangumi.search(q):
            if added_for_q >= PER_QUERY:
                break
            bid = h.get("id")
            if bid and bid not in seen_bgm_ids:
                seen_bgm_ids.add(bid)
                bgm_hits.append(h)
                added_for_q += 1
    bgm_top = bgm_hits[:8]

    # Pull ja/en names out of Bangumi results to fuel AniList search.
    # Order matters: collect MAIN names from ALL bgm_top entries first, THEN aliases.
    # Otherwise a single Bangumi entry with many infobox 別名 (e.g. a movie spinoff
    # listed first) will crowd out the main TV title at queries[:5].
    bgm_alt_names: list[str] = []
    def _add_alt(s: str):
        if s and s not in bgm_alt_names:
            bgm_alt_names.append(s)
    for b in bgm_top:
        _add_alt(b.get("name"))
        _add_alt(b.get("name_cn"))
    for b in bgm_top:
        infobox = b.get("infobox") or []
        for box in infobox:
            if isinstance(box, dict) and box.get("key") in ("别名", "別名"):
                val = box.get("value")
                if isinstance(val, list):
                    for v in val:
                        if isinstance(v, dict) and v.get("v"):
                            _add_alt(v["v"])
                elif isinstance(val, str):
                    _add_alt(val)

    # Step 2: AniList search — try Bangumi-derived names first, then fall back to
    # the entry's title_main and the full raw title (with subtitle) so multi-season
    # entries with the same main title get differentiated candidates.
    queries: list[str] = []
    for n in bgm_alt_names:
        if n and n not in queries:
            queries.append(n)
    if title_zh and title_zh not in queries:
        queries.append(title_zh)
    if title_raw and title_raw not in queries and title_subtitle:
        queries.append(title_raw)

    # Increased from 5 to 10 — Bangumi infobox 別名 are valuable but voluminous;
    # 5 was too tight when a single entry contributed 8+ aliases.
    anilist_pool: dict[int, dict] = {}
    for q in queries[:10]:
        for m in anilist.search(q, format_hint=fmt_hint):
            if m and m.get("id") and m["id"] not in anilist_pool:
                anilist_pool[m["id"]] = m

    if not anilist_pool:
        return {
            "best": None,
            "candidates": [],
            "confidence": 0.0,
            "needs_review": False,
            "no_match": True,
        }

    # Step 3: score every (anilist, bangumi) pairing; if no bangumi, score with None
    pairs = []
    bgm_options = bgm_top or [None]
    for am in anilist_pool.values():
        for bg in bgm_options:
            conf = _score_candidate(entry, am, bg)
            pairs.append((conf, am, bg))
    pairs.sort(key=lambda x: -x[0])

    candidates = []
    seen_ids = set()
    for conf, am, bg in pairs:
        if am["id"] in seen_ids:
            continue
        seen_ids.add(am["id"])
        candidates.append(_candidate_from_pair(am, bg, conf))
        if len(candidates) >= 5:
            break

    best = candidates[0] if candidates else None
    confidence = best["confidence"] if best else 0.0
    needs_review = MATCH_REVIEW_THRESHOLD <= confidence < MATCH_AUTO_ACCEPT
    return {
        "best": best,
        "candidates": candidates,
        "confidence": confidence,
        "needs_review": needs_review,
        "no_match": False,
    }


def _load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run(retry_unresolved: bool = False, only_new: bool = False) -> None:
    raw = _load(ENTRIES_RAW, {"entries": {}})
    entries = raw.get("entries", {})
    if not entries:
        print(f"[match] no entries in {ENTRIES_RAW} — run `parse` first")
        sys.exit(2)

    matched = _load(ENTRIES_MATCHED, {"version": 1, "matched": {}}).get("matched", {})
    unresolved = _load(UNRESOLVED, {})

    # --- retry-unresolved branch: apply manual_override values ---
    if retry_unresolved:
        applied = 0
        keep: dict = {}
        for slug, item in unresolved.items():
            override = item.get("manual_override")
            if not override:
                keep[slug] = item
                continue
            anilist_id = _parse_override(override)
            if not anilist_id:
                keep[slug] = item
                continue
            media = anilist.fetch(anilist_id)
            if not media:
                print(f"[match] override AniList:{anilist_id} for {slug} returned nothing — kept as unresolved")
                keep[slug] = item
                continue
            best = _candidate_from_pair(media, None, 1.0)
            matched[slug] = {
                "best": best,
                "candidates": [best],
                "confidence": 1.0,
                "needs_review": False,
                "manual": True,
                "matched_at": datetime.now().isoformat(timespec="seconds"),
            }
            applied += 1
        _save(ENTRIES_MATCHED, {"version": 1, "matched": matched, "updated_at": datetime.now().isoformat(timespec="seconds")})
        _save(UNRESOLVED, keep)
        print(f"[match] applied {applied} manual override(s); {len(keep)} still unresolved")
        return

    # --- main branch: match each entry ---
    auto = manual_review = no_match = skipped = 0
    total = len(entries)
    for i, (slug, entry) in enumerate(entries.items(), 1):
        if only_new and slug in matched:
            skipped += 1
            continue
        if slug in matched and matched[slug].get("manual"):
            skipped += 1
            continue
        result = match_one(entry)
        if result["no_match"]:
            unresolved[slug] = {
                "title_raw": entry.get("title_raw"),
                "title_main_zh": entry.get("title_main_zh"),
                "section_origin": entry.get("section_origin"),
                "candidates": [],
                "manual_override": None,
                "reason": "no_match",
            }
            no_match += 1
        elif result["confidence"] < MATCH_REVIEW_THRESHOLD:
            unresolved[slug] = {
                "title_raw": entry.get("title_raw"),
                "title_main_zh": entry.get("title_main_zh"),
                "section_origin": entry.get("section_origin"),
                "candidates": result["candidates"][:3],
                "manual_override": None,
                "reason": "low_confidence",
            }
            no_match += 1
        else:
            matched[slug] = {
                "best": result["best"],
                "candidates": result["candidates"][:3],
                "confidence": result["confidence"],
                "needs_review": result["needs_review"],
                "matched_at": datetime.now().isoformat(timespec="seconds"),
            }
            if result["needs_review"]:
                manual_review += 1
            else:
                auto += 1

        if i % 20 == 0 or i == total:
            print(f"[match] {i}/{total} — auto={auto} review={manual_review} unresolved={no_match} skipped={skipped}")

    _save(ENTRIES_MATCHED, {"version": 1, "matched": matched, "updated_at": datetime.now().isoformat(timespec="seconds")})
    _save(UNRESOLVED, unresolved)
    print(f"[match] done. auto-accepted={auto} needs-review={manual_review} unresolved={no_match} skipped={skipped}")


def _parse_override(s: str) -> Optional[int]:
    """Accept 'anilist:1234' or '1234'."""
    if not s:
        return None
    s = s.strip()
    if s.startswith("anilist:"):
        s = s.split(":", 1)[1]
    try:
        return int(s)
    except ValueError:
        return None
