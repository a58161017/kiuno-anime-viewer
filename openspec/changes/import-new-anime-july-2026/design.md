# Design — import-new-anime-july-2026

## Context

動機見 proposal.md。現況：`data/anime.json` 1018 條；`raw/anime_list.txt` 為上次匯入時的清單快照，已落後 Google Doc；`data/season_picks.json` 仍為四月（5 部，`updated_at: 2026-05-03`）。Doc 已可透過共用帳號讀取。

Doc 結構：區段標頭切類別（待追 / 正在觀看 / 看到一半 / 劇場版(完結) / 季番(完結)），各區段內「越上面越新」，`—------以上評價重新發落----------` 分隔線以上為近期新增/改評分的條目。

## Goals / Non-Goals

**Goals**
- 清單（除「待追」）與網站條目達成 1:1 涵蓋
- 季別橫幅正確呈現 2026 七月新番（owner 在看的）
- 全程用既有 pipeline / tools，不改程式碼

**Non-Goals**
- 不重算既有條目的評分 / 不處理「以上評價重新發落」的星級更新（另開 change）
- 不動「待追」3 部（謊言遊戲、女神咖啡廳、狩龍人拉格納）
- 不改 UI / CSS

## 已確認缺漏清單（精確比對 anime.json 標題後）

正在觀看（新番/連載）：
名偵探柯南（TV 本篇）、海賊王、火影忍者新世代 博人傳、國王排名 勇氣的寶箱、骸骨騎士大人異世界冒險中 第二季、小書痴的下剋上 領主的養女、才女的侍從、最強出涸皇子的暗躍帝位爭奪、被追放的轉生重騎士用遊戲知識開無雙、黃泉使者、暗黑燈火、『你們先走我斷後』，於是10年後我成為了傳說、Clevatess Ⅱ、尼古喵喵、GRAND BLUE 碧藍之海 3、地獄模式 2nd Season、幼女戰記 2、女性向遊戲世界對路人角色很不友好 第二季、盜墓王、無職轉生～到了異世界就拿出真本事～第三季、關於我轉生變成史萊姆這檔事 第四期、魔法帽的工作室、女神「異世界轉生想成為什麼」我「勇者的肋骨」、夜櫻家大作戰 第二季、成為悲劇元兇的最強異端 第二季、Re：從零開始的異世界生活 第四季、春夏秋冬代行者 春之舞、詐欺遊戲、異國日記、公主殿下，「拷問」的時間到了、我推的孩子、異度侵入／ID：INVADED、靠死亡遊戲混飯吃。、「憑妳也想討伐魔王？」被勇者小隊逐出隊伍，只好在王都自在過活、世界盡頭的聖騎士 第二季、SPY×FAMILY Season 3、Gachiakuta、王者天下 第六季、永遠的黃昏、最近的偵探真沒用、LAZARUS 拉撒路、狩火之王 第二季

看到一半：紫雲寺家的兄弟姊妹、人渣本願

季番(完結)：殺手青春、神八小妹不可怕、成為悲劇元兇的最強異端（第一季）、輝夜姬想讓人告白 邁向大人的階梯、Lycoris Recoil 莉可麗絲：友誼是時間的竊賊、在地下城尋求邂逅是否搞錯了什麼 第五季

> 注意：此清單來自頂部區塊 + 抽樣，實作時以「全文 diff」為準（見 Decisions #1），可能再多撈出少數漏網。

## Decisions

1. **同步方式：更新 raw + 增量 pipeline，而非逐一 add_specific**
   把 Doc 全文（排除待追區）整理成 `raw/anime_list.txt` 格式後覆寫，跑 `parse` → `match --only-new` → `enrich --only-new` → `download` → `graph`。
   理由：一次涵蓋所有漏網（含抽樣沒發現的）；pipeline 本身就有 cache / only-new 機制，既有 1018 條不會重打 API。放棄逐一 `tools/add_specific.py`（要先人工查 50+ 個 AniList id，易漏易錯）。

2. **季別匹配風險集中處理**
   新增條目大量帶季別後綴（第二季/第三季/3/Ⅱ/2nd Season），依 CLAUDE.md 地雷用既有 `_SEASON_PATTERNS` 走 match，match 不到或信心低的落 `unresolved.json` → 先 `tools/autoresolve.py` 收高信心，剩餘人工填 `manual_override` 重跑。真的找不到 AniList 條目的（如中國作品、冷門特別篇）用 `tools/synthesize.py` 走 Bangumi 合成或 stub（`anilist:9000000+`）。

3. **七月新番 ids 的判定：AniList season metadata，不用人工猜**
   從新 `anime.json` 篩「正在觀看」區條目中 `season == SUMMER && seasonYear == 2026` 者，依 Doc 出現順序（越上面越新）排入 `season_picks.json.ids`。春季跨季續播（如 Re:Zero S4、史萊姆第四期）不算七月新番、不入橫幅。
   `season_label` 沿用現有命名風格：`2026 七月新番 - 久野正在看`。

4. **長篇連載（柯南 TV / 海賊王 / 博人傳）正常收錄**
   AniList 都有條目，走一般 match；集數進度資訊本站本來就不存，不需特殊處理。

## Risks / Trade-offs

- [季別對錯 id：新一季誤配舊一季] → match 信心分數 + unresolved 人工審核；上線前用卡片頁抽查每一部新增條目的封面/年份；錯了用 `tools/apply_remap.py` 修
- [Bangumi 對繁體搜尋不友善 → match 命中率低] → pipeline 已內建繁簡雙 query；仍失敗者走 synthesize/stub
- [覆寫 raw/anime_list.txt 誤刪舊條目 → 站上條目反而變少] → 覆寫前 diff 舊 raw vs 新 raw，只允許「新增」不允許「消失」；enrich 前後比對 anime.json 條目數只增不減
- [「詐欺遊戲」等可能無對應 AniList 動畫條目] → 落 unresolved 時與 owner 確認是哪部作品，必要時 stub

## Migration Plan

全程本地執行；完成後照鐵則：本地 server 驗證（卡片頁、graph、ritual、橫幅）→ owner 確認 → bump 版號 + changelog → 才 commit/push。回滾 = git revert（純資料變更，無 schema 遷移）。

## Open Questions

- 「我推的孩子」Doc 記到 -36（跨三季總集數）：站上收一條還是各季分列？實作 match 時看 AniList 分季結構再與 owner 確認（不影響本設計其餘部分）
