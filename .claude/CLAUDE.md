# kiuno-anime-viewer 專案規則

這份文件給 Claude (或其他 AI 助手) 在改這個專案時參考。讀過再動手。

## 專案簡介

個人動漫資料庫 + Viewer + 知識圖。GitHub Pages 純靜態部署，附 Firebase Firestore 後端做訪客留言。Pipeline 在本地用 Python 跑，產出靜態 JSON + 封面，前端用 Alpine.js + 純 HTML/CSS。

主要 URL 結構（本地 + Pages 一致）：
- `/` 卡片 viewer (index.html)
- `/graph.html` 知識圖 (Cytoscape.js)
- `/recommends.html` 訪客留言 (Firebase Firestore)
- `/changelog.html` 更新紀錄
- `/data/*.json` 資料檔
- `/data/covers/*.jpg` 封面

## 鐵則 (RULES — 不要違反)

### 1. Mobile-first

所有 CSS **必須**用 mobile-first 寫法：預設樣式針對手機 (≤599px)，`@media (min-width: 600px)` 才往上加平板/桌機 override。

不能直接套桌機優先範本。先確保手機完全可用再說。範例參考 `styles.css` 既有結構（`.cards` / `.drawer` / `.header__row2` 都是 mobile-first）。

### 2. 改完不要立即 push，先讓使用者本地驗證

對 GitHub Pages 部署型專案做完功能變更後，**不要立即 commit + push**：

1. 改完檔案
2. 確認本地 server 還在跑 (`http://127.0.0.1:8000/kiuno-anime-viewer/`)
3. 跟使用者說「請在本地測試」並提供測試清單
4. **等使用者明確確認**（「OK」「沒問題」「推上去」）才執行 `git push`

例外：明確使用者說「直接 push」「上線」「部署吧」當下這次就可以 push。

### 3. 訪客提交內容要存 audit metadata

任何讓陌生訪客提交內容的功能（留言、評論、回報、聯絡表單）都要把 audit metadata 跟內容一起存到後台（不顯示在公開頁面）：

- IP（用 `https://api.ipify.org/?format=json`，fail-soft）
- `navigator.userAgent`、`navigator.platform`、`navigator.languages`
- `screen.width × height`、`window.innerWidth × innerHeight`
- `Intl.DateTimeFormat().resolvedOptions().timeZone`
- `document.referrer`

範例見 `recommends.html` 的 `collectAudit()`。

> **隱私聲明（目前停用）**：原本表單下方有「📋 提交即同意儲存 IP / 瀏覽器資訊作為防濫用紀錄」一段，2026-05-16 已移除（僅公開給親朋好友，非商業用途）。**日後如果使用者要把這個專案完全公開給網路上的所有人使用（例如做大規模宣傳、商業推廣、SEO 引流陌生流量），請主動提醒使用者把隱私聲明加回 `recommends.html` 的 `<form>` 底部（class `.privacy-note`，CSS 規則仍保留），以符合個資法 / GDPR 對告知條款的要求。** audit metadata 收集邏輯本身不能拿掉。

### 4. 版號管理

每次 push 上 GitHub 都要：

1. **版號 patch +1**：改 `data/version.json` 的 `current`（例 1.0.3 → 1.0.4）跟 `updated_at`
2. **新增 changelog 條目**：在 `data/changelog.json` 的 `versions` **最前面**插一個物件
3. changelog 條目格式：
   ```jsonc
   {
     "version": "1.0.4",
     "date": "YYYY-MM-DD",
     "summary": "本次重點 (一句話)",
     "changes": {
       "added":   ["新增的動畫名 (anilist:<id>)", "新功能 ..."],
       "fixed":   ["修正的動畫名 (anilist:<id>)", "修的 bug ..."],
       "removed": ["刪除的動畫名 (anilist:<id>)", "拿掉的功能 ..."],
       "ui":      ["UI 變更 ..."],
       "infra":   ["底層改動 ..."]
     }
   }
   ```
4. **新增 / 修改 / 刪除任何動畫都要列在 changes 裡**（含中文標題 + AniList id）

### 5. Firebase config 不直接 push

`firebase-config.js` 只放 `REPLACE_ME` placeholder commit 進 repo。實際值用 GitHub Actions secrets 注入，部署時生成正確檔案再上 Pages。本地開發手動填值（不 commit）。

詳見 `.github/workflows/deploy.yml`。

## 命名 / 結構

- ID 格式：`anilist:<n>`（含 `n` 為數字）。Stub / 自建條目用 `anilist:9000000+`（避開真實 id）
- 標題優先使用使用者 doc 的中文標題（保留「第二季」「第三季」等季別後綴），不要被 Bangumi 的「主作品名」覆蓋
- 中文一律繁體（簡體用 OpenCC `s2twp` 轉換）
- 圖片用 max 600px JPEG，存 `data/covers/anilist-<n>.jpg`

## 常用工具 (`tools/`)

| 工具 | 用途 |
|---|---|
| `add_specific.py` | 一次新增指定 AniList id 的條目（自動抓 metadata + 封面）|
| `apply_remap.py` | 把舊 anilist id 換成新 id（修錯誤匹配；自動處理 swap 衝突）|
| `restub.py` | 自動嘗試把 stub 對到真實 AniList id |
| `synthesize.py` | unresolved 條目用 Bangumi 資料合成 record（找不到就 stub）|
| `autoresolve.py` | 自動接受 unresolved 中信心高的候選 |

## 主 pipeline

`run.py serve` 起 server (`http://127.0.0.1:8000/kiuno-anime-viewer/`)。其他 commands：

- `parse` — 從 `raw/anime_list.txt` 切出條目
- `match` — Bangumi → AniList → 信心評分 → matched.json + unresolved.json
- `enrich --force` — 從 cache 重建 anime.json
- `download` — 下載缺的封面
- `graph` — 建知識圖

## 常見地雷

- **Alpine.js + ES module** 啟動順序：用 `import Alpine from "..../module.esm.js"` + `Alpine.start()`，不要用 `defer` script。範例見 `recommends.html`
- **Bangumi 搜尋對繁體不友善**：query 同時送繁體跟簡體（`s2t` 轉換後）才能命中 e.g.「我獨自升級」
- **季別 marker**：「南家三姊妹4」「灼眼的夏娜II」等中文+數字/羅馬要特殊 regex 處理（見 `pipeline/match.py:_SEASON_PATTERNS`）
- **fetch anime.json 要加 `cache: 'no-cache'`**：否則瀏覽器會用舊版過濾掉新加的 id
- **icon empty state**：手機 Safari 對 `backdrop-filter` + 半透明小元素渲染破圖。用實心半透明背景 + 固定 `line-height` + `text-align:center`，不用 flex
