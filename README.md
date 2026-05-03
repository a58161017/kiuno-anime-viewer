# kiuno-anime-viewer

個人動漫資料庫 + 卡片 Viewer + 知識圖。Pipeline 從個人動漫清單原文出發，向 [AniList](https://anilist.co) / [Jikan (MAL)](https://docs.api.jikan.moe/) / [Bangumi](https://bgm.tv/) 三邊抓 metadata，匯總成本地 JSON，供純前端 viewer 讀取。

部署網址（GitHub Pages）：<https://a58161017.github.io/kiuno-anime-viewer/>

---

## 主要功能

- **三來源評分匯總**：AniList 0.5 / MAL 0.3 / Bangumi 0.2 加權，永遠 0~5 星
- **季別感知比對**：能正確區分「為美好的世界獻上祝福！第一季」「第二季」「第三季」對應到不同 AniList id
- **繁體中文 UI**：Bangumi 簡體資料用 OpenCC `s2twp` 自動轉台灣繁體（包含詞彙轉換）
- **卡片視圖 (`index.html`)**：搜尋、分類/標籤過濾、星級篩選、排序；每張卡有 ★ 推薦、⇪ 分享、♥ 最愛三個 icon
- **層級式知識圖 (`graph.html`)**：分類 → 標籤 → 動畫三層，點擊或滾輪縮放都能切層
- **推薦清單可分享**：透過 `data/user_lists.json` 檔案 + GitHub Pages 部署，把網址給朋友就看到你的推薦
- **我的最愛純本機**：每個瀏覽器各自的最愛，可手動匯出 / 匯入 JSON 分享
- **增量更新**：日後看完新動畫 `python run.py add "..."` 互動加入；既有條目跳過 cache 命中

---

## 安裝

需要 **Python 3.10+**（我在 Python 3.13 測過）。

```powershell
pip install -r requirements.txt
```

依賴：`requests`、`rapidfuzz`、`Pillow`、`opencc-python-reimplemented`

---

## 第一次跑通

```powershell
# 1. 把你的動漫清單貼到 raw/anime_list.txt
#    格式範例（區段標頭一定要保留，pipeline 靠它切類別）：
#
#    --------------劇場版(完結)--------------
#    (5.0星)SPY×FAMILY 間諜家家酒 – CODE: White
#    (4.8星)名偵探柯南27 – 百萬美元的五棱星
#    --------------季番(完結)--------------
#    (4.7星)GNOSIA(21)
#    (4.8星)咒術迴戰 死滅迴游 前篇(12)
#    ...

# 2. 跑 pipeline
python run.py parse        # raw 文字 -> entries.raw.json
python run.py match        # 標題對應到 AniList/MAL/Bangumi id；產出 unresolved.json
# 視需要：編輯 data/unresolved.json 把 manual_override 設成 "anilist:<id>" 後跑：
python run.py match --retry-unresolved

python run.py enrich       # 抓 metadata 寫入 anime.json
python run.py download     # 下載並 resize 封面到 data/covers/
python run.py graph        # 從 anime.json 算邊權重產 graph.json

# 3. 起本機 server 看
python run.py serve
# 瀏覽器：
#   http://127.0.0.1:8000/kiuno-anime-viewer/             ← 卡片視圖
#   http://127.0.0.1:8000/kiuno-anime-viewer/graph.html   ← 知識圖
```

`python run.py stats` 隨時查看各階段完成數。

---

## 增量新增動畫

**互動式單筆**（最常用）：
```powershell
python run.py add "(4.8星)BOCCHI THE ROCK!(12)"
# parse → match (列出 top 3 候選讓你選) → enrich → 下載封面 → 更新 graph.json
# 同時 append 到 raw/anime_list.txt
```

**批次**：直接編輯 `raw/anime_list.txt`，再：
```powershell
python run.py parse --append
python run.py match --only-new
python run.py enrich --only-new
python run.py download
python run.py graph
```

---

## 評分 / 標籤

**評分**
- 客觀星級：AniList(0.5) + MAL(0.3) + Bangumi(0.2)，缺源就把可用權重重新正規化，永遠 0~5 ★
- 來源原始分留在 `rating.sources`，可隨時改 `config.RATING_WEIGHTS` 再 `python run.py enrich --force` 重算（cache 命中不重打 API）
- 使用者自評（Doc 裡的 `(5.0星)`）放在 `user.self_rating_raw`，UI 與客觀星分開顯示

**分類 / 標籤**
- `categories`：AniList genres 中譯（動作 / 喜劇 / 戀愛 / 運動…）
- `tags`：AniList strong tags（rank ≥ 60）+ 衍生 tag（`年份-2023` / `星級-4.5` / `studio-MAPPA` / `劇場版` / `season-1` …）
- 未中譯的 tag 會落 `data/unmapped_tags.json`，補譯後寫進 `data/genre_zh_map.json` 即可

---

## 知識圖

層級式視覺化（Cytoscape.js + fcose 力導向布局）：

| 層級 | 節點 | 邊 |
|---|---|---|
| **0 – 分類** | 動作、喜劇、戀愛… | 共有動畫 ≥ 5 部的分類連邊 |
| **1 – 標籤**（點分類進入）| 該分類內 top 50 tags | 共現於 ≥ N 部的 tag 對連邊 |
| **2 – 動畫**（點標籤進入）| 該分類+標籤的所有動畫 | 來自 `graph.json` 的 franchise / same_studio / shared_tag |

切層方式：點節點 / 麵包屑 / 滾輪縮放越過閾值。

`graph.json` 邊類型：

| 類型 | 條件 | 預設權重 |
|---|---|---|
| `franchise` | AniList relations (前傳/續作/外傳) | 1.0（永遠顯示） |
| `same_studio` | 主要 studio 交集 ≥ 1 | 0.3 |
| `shared_genre` | category 交集 ≥ 2 | 0.2 × 交集數（level 2 不顯示，避免雜訊） |
| `shared_tag` | distinctive tag 交集 ≥ 1 | 0.15 × 交集數 |
| `same_year` | 年份相同 | 0.1（level 2 不顯示） |

---

## 季別新番推薦

卡片頁最頂端的 `🌸 ...` 橫幅由 `data/season_picks.json` 驅動，由 owner 手動策劃當季新番。換季時直接覆寫此檔：

```jsonc
{
  "season_label": "🌸 2026 七月新番推薦",   // 自由文字，含 emoji 都行
  "ids": ["anilist:127230", "anilist:151807", "..."],   // 順序由你決定，不會被洗牌
  "updated_at": "2026-07-01"
}
```

- `ids` 為空 → 整個橫幅隱藏
- 對不上 `data/anime.json` 的 id 會被 skip 不顯示
- 改完 `git commit + push` 即可

---

## 推薦清單、我的最愛、單部分享

每張卡片右上區三個 icon：**★ 推薦** / **⇪ 分享** / **♥ 最愛**。

| 項目 | 儲存位置 | 分享方式 |
|---|---|---|
| **推薦清單 (★)** | `data/user_lists.json`（可分享）+ localStorage 備援 | 整份 JSON / GitHub Pages 網址 |
| **我的最愛 (♥)** | **純本機 localStorage**（每個瀏覽器各自一份） | toolbar 「⇪ 分享」匯出 JSON，朋友按「⇩ 匯入」吃進去 |
| **單部動畫 (⇪)** | — | 卡片右上 ⇪ 產生 `index.html?id=anilist:<n>` 連結 |

### 推薦清單

`data/user_lists.json` 結構：
```jsonc
{
  "version": 1,
  "recommend": ["anilist:127230", ...]    // 按點擊順序（最新在前）
}
```

- viewer 開啟時讀此檔；點 ★ 變動會即時 POST 寫回（透過 `/api/user_lists` 端點）
- 朋友開到的 viewer 會看到「👀 你目前在看分享的推薦清單」
- 朋友自己點 ★ → 自動切「本機模式」，他的編輯只存他瀏覽器，不影響你的清單

### 我的最愛

- 永遠存使用者自己 `localStorage` —— 朋友開你的網頁**不會**看到你的最愛
- 想分享：toolbar **⇪ 分享** → 下載 `my_favorites_YYYY-MM-DD.json`
- 朋友收到 → toolbar **⇩ 匯入** → 「合併」(保留 + 加上) 或「取代」

### 單部動畫分享

卡片右上 **⇪** → 依環境降級：
1. 支援 `navigator.share`（手機 / Edge / Chrome）→ 跳系統分享
2. 否則 → 複製到剪貼簿（標題 + 評分 + 簡介前 200 字 + 連結）
3. clipboard 也不行 → 跳 prompt 讓你自己 copy

連結格式：`<viewer URL>?id=anilist:<n>`，對方打開直接彈出那部的詳情面板。

---

## 訪客推薦留言（Firebase Firestore）

`recommends.html` 提供「**任何人都能留言推薦動漫**」的功能。後端用 Firebase Firestore（免費額度足夠：50K 讀/天、20K 寫/天）。

### 留言內容
- **公開顯示**：暱稱 / 推薦動畫 / 說明 / 時間
- **後台隱藏**（給 owner 防濫用追查用）：IP、瀏覽器 user-agent、平台、語言、螢幕/視窗大小、時區、來源頁面

### 反濫用機制
- **Honeypot 欄位**：表單藏一個正常人看不到的 `website` input，bot 會填它，後端 rules 用 `keys().hasOnly([...])` 直接擋掉多餘欄位
- **Client rate limit**：localStorage 記錄上次提交時間，60 秒內不能再交
- **欄位長度**：暱稱 ≤ 20、動畫名 ≤ 100、說明 5–500、UA ≤ 500（rules + UI 雙保險）
- **不可改不可刪**：rules 禁止 update/delete，owner 從 Firebase Console 手動管理

### Firebase 設定步驟（一次性）

1. 開 https://console.firebase.google.com
2. 建專案（建議名稱 `kiuno-anime-viewer`）
3. Build → **Firestore Database** → Create database → 選 Start in **test mode**（之後會用我們的 rules 取代）
4. 專案設定 → 一般 → 你的應用程式 → **加 Web App** → 取得 `firebaseConfig` 物件
5. 把 config 物件貼到 `firebase-config.js`（取代 `REPLACE_ME` 那些值）
6. Firestore → **Rules** 頁面 → 把整份 `firestore.rules` 內容貼進去 → **Publish**

### 端對端驗收

```bash
# 1. 完成 Firebase 設定 + 貼好 config
git add firebase-config.js
git commit -m "Configure Firebase for visitor recommends"
git push
# 等 Pages build 1-3 分鐘
```

打開 https://你.github.io/kiuno-anime-viewer/recommends.html 測試：
- 自己留言 → 應立刻顯示
- 換 device / 無痕 → 應看到同一筆
- 試 dev tools 改 hidden honeypot 後送出 → 應 silent reject
- 連續送兩次 → 第二次應提示「請稍候 60 秒」
- 試送 4 字說明 → rule 擋
- 點留言裡動畫名 → 跳到 `index.html?id=...`
- Firebase Console → Firestore → recommends → 任一筆 doc 看 `audit` 物件，應有 IP/UA/platform 等欄位

### 想刪除違規留言

到 Firebase Console → Firestore → `recommends` → 點該筆 doc → Delete document。

---

## 部署到 GitHub Pages

1. `.gitignore` 已配好（排除 cache、entries.matched 等可重生的中間檔）
2. push 上 GitHub 後：repo Settings → Pages → Source = `main` 分支 / `/ (root)`
3. 等部署。網址 = `https://<你的帳號>.github.io/kiuno-anime-viewer/`
4. 把網址傳給朋友

**朋友的體驗**
- 自動載入你的 `data/user_lists.json` → 看到你的推薦清單
- 自己點 ★/♥ → 切到「本機模式」，編輯存在他自己瀏覽器，不會影響你的 repo
- 想重新看你最新版 → 上方按「重新讀取分享清單」

> GitHub Pages 是純靜態，朋友的編輯不會 push 回你的 repo（POST 自動 fail-safe 到 localStorage）。
> 規模：`anime.json` ~3 MB、封面 ~50 MB、`graph.json` ~4 MB，都在 Pages 1 GB 限制內。

---

## 資料夾結構

```
kiuno-anime-viewer/
├── run.py                    # CLI dispatcher（serve/parse/match/...）
├── config.py                 # 路徑、限速、評分權重、圖權重
├── pipeline/                 # parse / match / enrich / download / graph / add
├── services/                 # http / anilist / jikan / bangumi / rating
├── data/
│   ├── anime.json            # 主資料庫 (dict-by-id, id="anilist:<n>")
│   ├── graph.json            # 給 graph.html
│   ├── user_lists.json       # 推薦清單（可分享）
│   ├── manual_overrides.json # 你想覆蓋的 categories/tags
│   ├── genre_zh_map.json     # AniList genre/tag → 中文映射
│   ├── unmapped_tags.json    # 未對應的 tag（補譯後寫進 genre_zh_map.json）
│   ├── covers/               # 封面圖（resize max 600px）
│   ├── entries.raw.json      # parse 階段產物（gitignored）
│   ├── entries.matched.json  # match 階段產物（gitignored）
│   ├── unresolved.json       # 待人工修正（gitignored）
│   └── cache/                # API 回應 cache（gitignored）
├── raw/anime_list.txt        # 從 Doc 貼來的原文（真理之源；個人資料，gitignored 視情況）
├── index.html                # 卡片 viewer（入口）
├── graph.html                # Cytoscape 知識圖
└── styles.css
```

---

## 常見問題

- **match 命中率偏低**：開 `data/unresolved.json` 看 top 3 候選，選一個填 `manual_override: "anilist:<id>"` 然後 `python run.py match --retry-unresolved`
- **想換評分權重**：改 `config.RATING_WEIGHTS`，跑 `python run.py enrich --force`（cache 命中不重打 API）
- **想覆蓋某部動畫的 tags**：在 `data/manual_overrides.json` 寫 `{"anilist:<id>": {"tags": ["+額外標籤", "-不要的標籤"]}}`，下次 enrich 自動 merge
- **viewer 開不出來**：必須用 `python run.py serve`（不能直接雙擊 .html，瀏覽器擋本地 fetch）
- **POST 失敗看到「本機模式」**：在 GitHub Pages 上正常（純靜態無後端）；本機跑時表示 server 沒起或 port 被占

---

## 資料來源

- [AniList](https://anilist.co) GraphQL API — 主來源（metadata、relations、cover、評分）
- [Jikan](https://docs.api.jikan.moe/) (MyAnimeList 非官方 REST) — MAL 評分
- [Bangumi](https://bgm.tv/) v0 REST API — 中文標題、簡介、評分

---

## License

MIT
