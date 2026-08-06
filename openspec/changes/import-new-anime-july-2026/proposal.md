# import-new-anime-july-2026

## Why

Owner 的主清單（Google Doc）自上次匯入後持續更新，經比對至少有 **~50 部**清單上有、網站沒有的動畫（多為 2026 春/夏季新番與近期補看的舊作，抽樣也發現舊區段有漏網如「在地下城尋求邂逅是否搞錯了什麼 第五季」）。同時首頁季別橫幅仍停在「2026 四月新番」（`updated_at: 2026-05-03`），現已 8 月，需換成七月新番。

## What Changes

- **補齊缺漏動畫條目**：以 Google Doc 全文更新 `raw/anime_list.txt`，跑增量 pipeline（parse → match → enrich → download → graph）把清單上有、站上沒有的條目全部補進 `data/anime.json` + 封面 + `graph.json`。已確認缺漏的代表性條目（完整清單見 design.md）：
  - 進行中新番：骸骨騎士大人異世界冒險中 第二季、才女的侍從、GRAND BLUE 碧藍之海 3、無職轉生 第三季、Re：從零開始的異世界生活 第四季、Gachiakuta、SPY×FAMILY Season 3、王者天下 第六季、夜櫻家大作戰 第二季、幼女戰記 2、Clevatess Ⅱ、尼古喵喵、暗黑燈火、黃泉使者⋯
  - 補看舊作：我推的孩子、異度侵入／ID：INVADED、人渣本願、公主殿下，「拷問」的時間到了⋯
  - 長篇連載：名偵探柯南（TV）、海賊王、火影忍者新世代 博人傳、國王排名 勇氣的寶箱
- **季別橫幅換季**：`data/season_picks.json` 的 `season_label` 從「2026 四月新番 - 久野正在看」改為「**2026 七月新番 - 久野正在看**」，`ids` 換成清單「正在觀看」區且 AniList 季別為 2026 年夏季（SUMMER 2026）的條目
- **版號 + changelog**：patch +1，changelog 條目把所有新增動畫列入 `changes.added`（含中文標題 + anilist id）
- **假設（可在 review 時推翻）**：Doc「待追」區的 3 部（謊言遊戲、女神咖啡廳、狩龍人拉格納）**不納入**——尚未開始看，與站上「看過/在看才收錄」的慣例不符

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `data-pipeline`: 新增「主清單同步」需求——網站資料庫必須涵蓋 owner 主清單（Google Doc）上所有已觀看/觀看中的條目；`raw/anime_list.txt` 為主清單的本地鏡像

## Impact

- 資料檔：`data/anime.json`、`data/graph.json`、`data/season_picks.json`、`data/covers/*`（新增 ~50 張）、`raw/anime_list.txt`、`data/version.json`、`data/changelog.json`
- 程式碼：**不改任何前端 / pipeline 程式碼**，純資料變更（跑既有 pipeline 與工具）
- 外部 API：AniList / Jikan / Bangumi（增量抓取，cache 命中不重打）
- 風險：季別條目匹配錯誤（同系列不同季對錯 id）→ 靠 unresolved.json 人工確認 + `tools/apply_remap.py` 修正
