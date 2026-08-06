# data-pipeline Specification

## Purpose

本地 Python pipeline（`run.py` + `pipeline/` + `services/` + `tools/`）：從 `raw/anime_list.txt` 原文出發，向 AniList / Jikan(MAL) / Bangumi 抓 metadata，產出前端用的靜態 JSON 與封面。

## Requirements

### Requirement: Pipeline 階段

`run.py` SHALL 提供下列 commands，各階段產物明確：
- `parse`：`raw/anime_list.txt`（區段標頭切類別）→ `entries.raw.json`
- `match`：標題 → Bangumi → AniList 對應 + 信心評分 → `entries.matched.json` + `unresolved.json`
- `enrich`：抓三源 metadata 合成 → `anime.json`（`--force` 從 cache 重建不重打 API）
- `download`：下載缺的封面，resize max 600px JPEG → `data/covers/anilist-<n>.jpg`
- `graph`：從 anime.json 算邊權重 → `graph.json`
- `add`：互動式單筆增量（parse → match 選候選 → enrich → 封面 → graph，並 append 回 raw）
- `serve`：本機 server（`http://127.0.0.1:8000/kiuno-anime-viewer/`），viewer 必須經 server 開啟

#### Scenario: 增量新增
- **WHEN** 執行 `python run.py add "(4.8星)BOCCHI THE ROCK!(12)"`
- **THEN** 互動列出 top 3 候選供選擇，選定後完成 enrich、封面下載、graph 更新，並 append 到 raw/anime_list.txt

### Requirement: 匹配規則

match SHALL 處理：
- 季別感知：同系列不同季對到不同 AniList id；中文+數字/羅馬季別 marker（「南家三姊妹4」「灼眼的夏娜II」）用 `pipeline/match.py:_SEASON_PATTERNS` 特殊處理
- 繁簡雙送：Bangumi 搜尋同時送繁體與 s2t 簡體 query
- 無法自動匹配 → 進 `unresolved.json`，人工填 `manual_override: "anilist:<id>"` 後 `match --retry-unresolved`

#### Scenario: 繁體搜尋命中
- **WHEN** 條目標題為繁體（如「我獨自升級」）而 Bangumi 只收簡體
- **THEN** 簡體 query 命中，匹配成功

### Requirement: 評分合成

enrich SHALL 以 AniList 0.5 / MAL 0.3 / Bangumi 0.2 加權合成 0~5 星客觀星級；缺源時可用權重重新正規化。來源原始分保留在 `rating.sources`；使用者自評存 `user.self_rating_raw`。

#### Scenario: 調整權重
- **WHEN** 修改 `config.RATING_WEIGHTS` 後執行 `enrich --force`
- **THEN** 從 cache 重算全部星級，不重打外部 API

### Requirement: 中文與 ID 慣例

pipeline SHALL 遵守：中文一律繁體（OpenCC s2twp）；標題優先用使用者 doc 的中文標題（保留季別後綴），不被 Bangumi 主作品名覆蓋；ID 為 `anilist:<n>`，stub / 自建條目用 `anilist:9000000+`；未中譯 tag 落 `unmapped_tags.json`，補譯寫進 `genre_zh_map.json`。

#### Scenario: 簡體資料進入
- **WHEN** Bangumi 回傳簡體簡介
- **THEN** 以 s2twp 轉為台灣繁體（含詞彙轉換）後才寫入 anime.json

### Requirement: 主清單同步

網站資料庫（`data/anime.json`）SHALL 涵蓋 owner 主清單（Google Doc）上所有已觀看或觀看中的條目；`raw/anime_list.txt` SHALL 作為主清單的本地鏡像，同步時以 Doc 內容為準更新。「待追」（尚未開始看）區段的條目不在收錄範圍。

#### Scenario: 主清單新增條目後同步

- **WHEN** 主清單新增了網站上沒有的已觀看/觀看中條目，並執行一次同步
- **THEN** 該條目出現在 `data/anime.json`（含 metadata、封面、graph 連結），且 `raw/anime_list.txt` 已反映主清單內容

#### Scenario: 待追條目不納入

- **WHEN** 主清單「待追」區段含有網站上沒有的條目
- **THEN** 同步後該條目不出現在 `data/anime.json`

### Requirement: 修正工具

`tools/` SHALL 提供資料修正工具：`add_specific.py`（指定 AniList id 直接新增）、`apply_remap.py`（換錯誤 id，自動處理 swap 衝突）、`restub.py`（stub 對回真實 id）、`synthesize.py`（unresolved 用 Bangumi 合成或 stub）、`autoresolve.py`（自動接受高信心候選）。

#### Scenario: 修正錯誤匹配
- **WHEN** 發現某條目對到錯的 AniList id
- **THEN** 用 `apply_remap.py` 換 id，即使新 id 與既有條目衝突（swap）也正確處理
