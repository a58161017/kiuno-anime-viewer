"""把指定的舊 anilist id 換成正確的 AniList id (含完整 metadata + 封面)。
處理 swap 情況：先全部刪舊、再全部寫新，避免 id 衝突。
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

from config import ANIME_JSON, COVERS_DIR, COVER_MAX_PX, GENRE_ZH_MAP, USER_AGENT, REQUEST_TIMEOUT, USER_LISTS
from pipeline.enrich import _build_record
from services import anilist, jikan, bangumi

# 舊 anilist id (字串) → 新 anilist id (數字)
# user 提供的修正：
REMAPS = {
    "anilist:110458": 20812,    # 白箱 → SHIROBAKO TV
    "anilist:9000091": 124341,  # 地下城與勇士 → Arad: Gyakuten no Wa
    "anilist:21711": 177709,    # 坂本日常 → SAKAMOTO DAYS
    "anilist:170130": 183275,   # 完美聖女 → The Too-Perfect Saint
    "anilist:8769": 16405,      # 我的妹妹是大阪大媽 → Boku no Imouto wa Osaka Okan (8769 之前是 Oreimo)
    "anilist:100382": 8769,     # 我的妹妹哪有這麼可愛 → Oreimo S1 (8769)
    "anilist:98596": 173693,    # 孤單一人的異世界攻略 → Loner Life
    "anilist:209670": 187264,   # 泛而不精 → S1 (Jack-of-All-Trades 187264)；209670 是 S2
    "anilist:2285": 11179,      # 要聽爸爸的話 → Listen to Me, Girls 11179
    "anilist:165790": 17875,    # 要聽爸爸的話OVA → Papa OVA 17875
    "anilist:136668": 9201,     # 飛輪少年OVA → AIR GEAR Kuro no Hane 9201
    "anilist:185875": 21509,    # 槍彈辯駁3 未來篇 → Future Arc 21509
    "anilist:20668": 21825,     # 槍彈辯駁3 絕望篇 → Despair Arc 21825
    "anilist:11245": 14045,     # 漫畫少女 → Mangirl!
    "anilist:509": 16169,       # 漫研部 → Ai-Mai-Mi
    "anilist:120209": 139587,   # 轉生就是劍 → Reincarnated as a Sword
    "anilist:4262": 132405,     # 戀上換裝娃娃 → My Dress-Up Darling
    "anilist:21126": 4975,      # CHAOS;HEAD → ChäoS;HEAd
    "anilist:620": 16910,       # 人魚又上鉤 → Muromi-san
    "anilist:99539": 21104,     # 七大罪OVA → Seven Deadly Sins OVA
}

# 純刪除 (使用者表示是重複條目)：
DELETIONS = [
    "anilist:967",   # 肯普法 (重複；保留別的)
]


def download_cover(url, dest):
    if not url: return False
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        if max(w, h) > COVER_MAX_PX:
            s = COVER_MAX_PX / max(w, h)
            img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=85, optimize=True)
        return True
    except Exception as e:
        print(f"  [cover] {e}")
        return False


def main():
    db = json.load(open(ANIME_JSON, encoding="utf-8"))
    anime = db["anime"]
    genre_zh = json.load(open(GENRE_ZH_MAP, encoding="utf-8"))
    now_iso = datetime.now().isoformat(timespec="seconds")

    # ===== Phase 0: 收集計畫並儲存舊 record metadata =====
    plan = []  # (old_id, real_aid, old_rec)
    for old_id, real_aid in REMAPS.items():
        if old_id not in anime:
            print(f"  ✗ {old_id} 不在 anime.json")
            continue
        plan.append((old_id, real_aid, anime[old_id]))

    deletions = [d for d in DELETIONS if d in anime]
    print(f"\n計畫：remap {len(plan)} 條, delete {len(deletions)} 條\n")

    # ===== Phase 1: 全部刪除舊 records =====
    old_ids_to_delete = {old for old, _, _ in plan} | set(deletions)
    for oid in old_ids_to_delete:
        if oid in anime:
            del anime[oid]

    # ===== Phase 2: 寫入新 records =====
    id_remap = {}
    applied = 0
    for old_id, real_aid, old_rec in plan:
        new_id = f"anilist:{real_aid}"
        title = old_rec["titles"]["primary_zh"]
        if new_id in anime:
            print(f"  ⚠ {old_id} → {new_id} 已存在 (合併到既有) — 略過寫入新 record")
            id_remap[old_id] = new_id  # 還是要更新引用
            continue

        ani_media = anilist.fetch(real_aid)
        if not ani_media:
            print(f"  ✗ AniList:{real_aid} fetch 失敗 → restore old {old_id}")
            anime[old_id] = old_rec
            continue

        native = (ani_media.get("title") or {}).get("native") or ""
        bgm_data = None
        for q in (native, title):
            if not q: continue
            for h in (bangumi.search(q) or [])[:1]:
                bid = h.get("id")
                if bid:
                    bgm_data = bangumi.fetch(bid)
                    break
            if bgm_data: break
        mal_data = jikan.fetch(ani_media.get("idMal")) if ani_media.get("idMal") else None

        entry = {
            "title_raw": title,
            "title_main_zh": title,
            "section_origin": old_rec.get("section_origin", "已完結"),
            "user_rating": (old_rec.get("user") or {}).get("self_rating_raw"),
            "episodes_in_doc": (old_rec.get("user") or {}).get("doc_episode_count"),
            "source_doc_raw": old_rec.get("source_doc_raw") or title,
        }
        new_rec = _build_record(entry, {"needs_review": False}, None,
                                ani_media, mal_data, bgm_data, genre_zh, {}, now_iso)
        new_rec["titles"]["primary_zh"] = title

        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", new_id)
        dest = COVERS_DIR / f"{slug}.jpg"
        if download_cover((new_rec.get("cover") or {}).get("url"), dest):
            new_rec["cover"]["local"] = f"data/covers/{slug}.jpg"
            new_rec["enrichment"]["cover_at"] = now_iso

        anime[new_id] = new_rec
        id_remap[old_id] = new_id
        applied += 1
        rom = (ani_media.get("title") or {}).get("english") or (ani_media.get("title") or {}).get("romaji")
        print(f"  ✓ {old_id} → {new_id}  ({title})  ← {rom}")

    for d in deletions:
        print(f"  🗑  deleted {d}")

    db["anime"] = anime
    db["updated_at"] = now_iso
    json.dump(db, open(ANIME_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 同步 user_lists.json
    if id_remap or deletions:
        try:
            ul = json.load(open(USER_LISTS, encoding="utf-8"))
            old_recommend = ul.get("recommend", [])
            new_recommend = []
            for x in old_recommend:
                if x in deletions: continue
                new_recommend.append(id_remap.get(x, x))
            if new_recommend != old_recommend:
                ul["recommend"] = new_recommend
                json.dump(ul, open(USER_LISTS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print(f"  user_lists.json 更新")
        except Exception as e:
            print(f"  user_lists 更新失敗: {e}")

    sp_path = ANIME_JSON.parent / "season_picks.json"
    if (id_remap or deletions) and sp_path.exists():
        try:
            sp = json.load(open(sp_path, encoding="utf-8"))
            old_ids = sp.get("ids", [])
            new_ids = []
            for x in old_ids:
                if x in deletions: continue
                new_ids.append(id_remap.get(x, x))
            if new_ids != old_ids:
                sp["ids"] = new_ids
                json.dump(sp, open(sp_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print(f"  season_picks.json 更新")
        except Exception as e:
            print(f"  season_picks 更新失敗: {e}")

    print(f"\n=== 結果 ===\n套用 {applied} 個 remap, 刪 {len(deletions)} 條")
    print(f"總 anime records: {len(anime)}")


if __name__ == "__main__":
    main()
