"""Parse the user's raw anime list into structured entries.

Section header format (from the Google Doc):
    --------------劇場版(完結)--------------
    --------------季番(完結)--------------
    --------------已完結--------------

Per-line entry format examples:
    (5.0星)SPY×FAMILY 間諜家家酒 – CODE: White
    (4.7星)GNOSIA(21)
    (4.8星)咒術迴戰 死滅迴游 前篇(12)(59)
    (4.6星)葬送的芙莉蓮 第二季(38)(10)
    航海王：紅髮歌姬                    # rating may be absent

Output: data/entries.raw.json with dict-by-slug structure.
SHA-deduped on `source_doc_raw` so --append never duplicates lines.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import ENTRIES_RAW, RAW_LIST

# Section markers. Tolerant: any line padded with 4+ dashes (ASCII or em-dash variants).
SECTION_RE = re.compile(r"^[-—–─]{4,}\s*(?P<name>[^-—–─]+?)\s*[-—–─]{4,}$")
SECTION_ALIAS = {
    "劇場版(完結)": ("劇場版", "movie"),
    "劇場版（完結）": ("劇場版", "movie"),
    "季番(完結)": ("季番", "tv"),
    "季番（完結）": ("季番", "tv"),
    "已完結": ("已完結", "tv"),
}
# Section names whose dashes are present but should be treated as in-list noise (skip the line),
# not as new sections nor as anime entries.
SECTION_NOISE_NAMES = {
    "以上評價重新發落",
}

RATING_RE = re.compile(r"\((\d(?:\.\d)?)\s*星\)")
TRAILING_PAREN_RE = re.compile(r"\((\d{1,3})\)\s*$")
# Inline "// 註解" (with surrounding whitespace) — strip before parsing
INLINE_COMMENT_RE = re.compile(r"\s*//.*$")
# In-paren附註 like "(全集 159)" — these are the user's running totals, not standalone (n)
EXTRA_PAREN_NOTE_RE = re.compile(r"\s*[(（]全集[\s\d]+[)）]\s*$")
# 「(完結)」 trailing tag means the entry belongs in the 「已完結」 (older completed) section.
# Right paren may be missing (typos in the source doc) — accept that gracefully.
COMPLETED_TAIL_RE = re.compile(r"\s*[(（]完結[)）]?\s*$")
# Some entries also use bracketed notes like "Z 番外篇" — leave those for SUBTITLE_SPLIT_RE
SUBTITLE_SPLIT_RE = re.compile(r"\s*[–\-:：／]\s*")  # 主標 / 副標 切分


def _slug(title: str) -> str:
    norm = re.sub(r"[\s/／:：–\-—\.　\(\)\[\]『』「」]", "", title.lower())
    if not norm:
        norm = hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
    return f"slug:{norm}"


def _line_hash(line: str) -> str:
    return hashlib.sha1(line.strip().encode("utf-8")).hexdigest()


def _extract_episodes(remainder: str) -> tuple[str, list[int]]:
    """Strip trailing (n) groups; return (cleaned_text, [eps...]) — order: outermost first."""
    eps: list[int] = []
    while True:
        m = TRAILING_PAREN_RE.search(remainder)
        if not m:
            break
        eps.append(int(m.group(1)))
        remainder = remainder[:m.start()].rstrip()
    return remainder, list(reversed(eps))


def parse_line(line: str, section_name: str, format_hint: str) -> Optional[dict]:
    line = line.strip()
    if not line or SECTION_RE.match(line):
        return None
    # Skip in-list noise lines like "—-----以上評價重新發落-----"
    noise_match = re.match(r"^[-—–─]{2,}\s*(.+?)\s*[-—–─]{2,}$", line)
    if noise_match and noise_match.group(1) in SECTION_NOISE_NAMES:
        return None

    # Strip inline "// 註解" before any other parsing
    line_no_comment = INLINE_COMMENT_RE.sub("", line).strip()
    # Strip "(全集 159)" type running-total notes from the tail
    line_no_comment = EXTRA_PAREN_NOTE_RE.sub("", line_no_comment).strip()
    # Strip "(完結)" tail — and override section to "已完結" if present (this is the
    # signal in the user's doc for older completed entries, since there is no
    # explicit "已完結" header line)
    if COMPLETED_TAIL_RE.search(line_no_comment):
        section_name = "已完結"
        format_hint = "tv"
        line_no_comment = COMPLETED_TAIL_RE.sub("", line_no_comment).strip()
    if not line_no_comment:
        return None

    # Strip rating
    rating: Optional[float] = None
    m = RATING_RE.search(line_no_comment)
    rest = line_no_comment
    if m:
        rating = float(m.group(1))
        rest = line_no_comment[:m.start()] + line_no_comment[m.end():]
    rest = rest.strip()

    # Strip trailing episode groups
    rest, eps = _extract_episodes(rest)

    title_full = rest.strip()
    if not title_full:
        return None

    # Split main / subtitle on the first separator. Don't split if the prospective
    # main is too short (e.g. "Re：從零開始..." → don't split into ["Re", ...]).
    parts = SUBTITLE_SPLIT_RE.split(title_full, maxsplit=1)
    title_main_candidate = parts[0].strip()
    if len(parts) > 1 and (len(title_main_candidate) < 3):
        # Too short to be a real main title — keep whole string as title_main
        title_main = title_full
        subtitle = None
    else:
        title_main = title_main_candidate
        subtitle = parts[1].strip() if len(parts) > 1 else None

    return {
        "slug": _slug(title_full),
        "section_origin": section_name,
        "format_hint": format_hint,
        "title_raw": title_full,
        "title_main_zh": title_main,
        "title_subtitle": subtitle,
        "user_rating": rating,
        "episodes_in_doc": eps[0] if eps else None,
        "episode_groups": eps,           # all trailing (n) values, outer-first
        "source_doc_raw": line,
        "source_hash": _line_hash(line),
    }


def parse_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    out: list[dict] = []
    current_section_name = "未分類"
    current_format_hint = "tv"
    in_target_section = False  # only collect after first known section header

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        m = SECTION_RE.match(stripped)
        if m:
            name = m.group("name").strip()
            if name in SECTION_ALIAS:
                current_section_name, current_format_hint = SECTION_ALIAS[name]
                in_target_section = True
                continue
            if name in SECTION_NOISE_NAMES:
                # In-list noise like "以上評價重新發落" — keep current section state
                continue
            # Truly unknown header: stop collecting until next known header
            in_target_section = False
            continue
        if not in_target_section:
            continue
        entry = parse_line(line, current_section_name, current_format_hint)
        if entry:
            out.append(entry)
    return out


def run(input_path: Optional[str] = None, append: bool = False) -> None:
    src = Path(input_path) if input_path else RAW_LIST
    if not src.exists():
        print(f"[parse] input not found: {src}", file=sys.stderr)
        print("        (paste the doc content from 「劇場版(完結)」 section onwards into this file)")
        sys.exit(2)

    new_entries = parse_file(src)
    print(f"[parse] {len(new_entries)} lines parsed from {src}")

    existing = {"version": 1, "updated_at": "", "entries": {}}
    if append and ENTRIES_RAW.exists():
        try:
            existing = json.loads(ENTRIES_RAW.read_text(encoding="utf-8"))
        except Exception:
            pass

    entries: dict = existing.get("entries", {}) if append else {}
    seen_hashes = {e.get("source_hash") for e in entries.values()}

    added = 0
    by_section: dict[str, int] = {}
    for ent in new_entries:
        h = ent["source_hash"]
        if append and h in seen_hashes:
            continue
        # Avoid slug collisions in append mode by salting with hash suffix
        slug = ent["slug"]
        if slug in entries and entries[slug].get("source_hash") != h:
            slug = f"{slug}-{h[:6]}"
            ent["slug"] = slug
        entries[slug] = ent
        seen_hashes.add(h)
        added += 1
        by_section[ent["section_origin"]] = by_section.get(ent["section_origin"], 0) + 1

    out = {
        "version": 1,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "entries": entries,
    }
    ENTRIES_RAW.parent.mkdir(parents=True, exist_ok=True)
    ENTRIES_RAW.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[parse] wrote {len(entries)} entries to {ENTRIES_RAW} (+{added} new)")
    for sec, n in sorted(by_section.items(), key=lambda x: -x[1]):
        print(f"        {sec}: {n}")
