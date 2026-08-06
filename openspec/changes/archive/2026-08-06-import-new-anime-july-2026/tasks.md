# Tasks — import-new-anime-july-2026

## 1. 準備主清單鏡像

- [x] 1.1 從 Google Doc 抓最新全文，轉成 `raw/anime_list.txt` 既有格式（實作調整：不整份覆寫，改 append 缺漏行進對應區段——parser 只認 劇場版/季番/已完結 區段；觀看中條目的 `-NN` 進度後綴清掉、`(續看)` 去除；排除「待追」區）
- [x] 1.2 Diff 新舊 `raw/anime_list.txt`：確認只有「新增行」沒有「消失行」（append-only 策略 + 腳本 assert 驗證；舊 1050 行 → 新 1136 行，+86 條）

## 2. 跑增量 pipeline

- [x] 2.1 `python run.py parse` 重切條目，確認新條目數量與 design.md 缺漏清單量級相符（1127 條 parsed，+86 新行，含「看到一半」區 ~30 條，量級相符）
- [x] 2.2 `python run.py match --only-new`，檢視 `data/unresolved.json`（auto=55、review=13、new-unresolved=17；另有 96 條歷史遺留 unresolved 為既有債務，不屬本次範圍）
- [x] 2.3 autoresolve 收 2 條；其餘逐筆用 AniList/Bangumi API 查證：15 條填 manual_override、5 條錯配（海賊王/東京喰種:re/史萊姆第四/炎炎S1/巨人Final）直接修 matched.json、1 組 swap（炎炎貳之章讓出 105310 給 S1、自身改 114236）
- [x] 2.4 無需 synthesize/stub：全部找到真實 AniList 條目（「詐欺遊戲」= 2026 年 LIAR GAME 動畫 anilist:197754）
- [x] 2.5 `python run.py enrich --only-new` → 79 enriched / 0 failed，1018 → 1096 條只增不減；標題含季別後綴（另補修 Re:Zero S4 既有卡標題）。注意：Jikan/MAL 當時 API 全面 504，新條目暫缺 MAL 分數（fail-soft 正規化），日後 `enrich --force` 可補
- [x] 2.6 `python run.py download` → 76 張新封面全數成功；46 張失敗全為歷史 stub（本來就無封面，非本次範圍）
- [x] 2.7 `python run.py graph` 重建完成（franchise 236 / same_studio 855 / shared_tag 312）

## 3. 七月新番橫幅

- [x] 3.1 依 AniList season=Summer/year=2026 篩出 13 部，依 Doc 出現順序排列
- [x] 3.2 `season_picks.json` 更新：label「2026 七月新番 - 久野正在看」、13 ids、updated_at 2026-08-06
- [x] 3.3 春季跨季續播（Re:Zero S4、史萊姆第四期、SPY×FAMILY S3 等）已確認排除

## 4. 驗證與收尾（不含 push）

- [x] 4.1 我推的孩子分季：owner 決定拆三季 → S1 anilist:150672 / S2 anilist:166531 / S3 anilist:182587，三卡皆有封面（總條目 1099）
- [x] 4.2 本地 server 煙霧測試：5 頁全 200；anime.json 1096 條；橫幅 13 ids 全存在且全有封面；graph.json 正常
- [x] 4.3 手機寬度（375px）檢查橫幅與新卡片版面無破版（純資料變更未動 CSS；owner 驗收後確認推上）
- [x] 4.4 version 1.3.0 → 1.3.1；changelog 插入 80 條 added（自動從 git diff 生成 + 我推的孩子 S2/S3）+ fixed/ui/infra
- [x] 4.5 owner 已確認（「第 1 點做好之後就可以推上去了」）→ commit + push
