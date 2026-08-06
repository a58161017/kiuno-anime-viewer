# card-viewer Specification

## Purpose

`index.html` 是全站入口：以卡片形式呈現 `data/anime.json` 的個人動漫資料庫，提供搜尋、過濾、排序、詳情面板、季別新番橫幅，以及推薦（★）/ 分享（⇪）/ 最愛（♥）三種卡片互動。

## Requirements

### Requirement: 卡片清單與資料載入

系統 SHALL 從 `data/anime.json` 載入全部條目並以卡片呈現，fetch 時必須帶 `cache: 'no-cache'` 以避免瀏覽器用舊版資料過濾掉新條目。

#### Scenario: 正常載入
- **WHEN** 使用者開啟 `index.html`
- **THEN** 顯示全部動畫卡片，每張含封面、中文標題、加權星級（0~5 ★）、分類

### Requirement: 搜尋、過濾與排序

系統 SHALL 提供標題搜尋、分類/標籤過濾、星級門檻篩選與排序（依評分、年份等），且所有條件可組合。

#### Scenario: 組合過濾
- **WHEN** 使用者同時設定分類「動作」與星級 ≥ 4.5
- **THEN** 只顯示同時滿足兩條件的卡片

### Requirement: 三來源加權評分顯示

系統 SHALL 顯示 AniList(0.5) / MAL(0.3) / Bangumi(0.2) 加權後的客觀星級；缺源時權重重新正規化。使用者自評（`user.self_rating_raw`）與客觀星級分開顯示。

#### Scenario: 缺少部分評分來源
- **WHEN** 某條目只有 AniList 與 Bangumi 分數
- **THEN** 以 0.5/0.2 重新正規化計算，仍顯示 0~5 星

### Requirement: 詳情面板與單部深連結

系統 SHALL 支援 `index.html?id=anilist:<n>` 深連結：開啟時直接彈出該動畫的詳情面板。卡片 ⇪ 分享按鈕 SHALL 依環境降級：`navigator.share` → 剪貼簿 → prompt。

#### Scenario: 開啟分享連結
- **WHEN** 訪客開啟 `index.html?id=anilist:127230`
- **THEN** 頁面載入後自動彈出該動畫詳情面板

### Requirement: 季別新番橫幅

系統 SHALL 依 `data/season_picks.json` 在頁面頂端顯示 owner 手動策劃的當季新番橫幅；`ids` 為空時整個橫幅隱藏，對不上 `anime.json` 的 id 直接 skip。

#### Scenario: 空清單
- **WHEN** `season_picks.json` 的 `ids` 為空陣列
- **THEN** 橫幅完全不顯示

### Requirement: 推薦清單（★）共享與本機模式

系統 SHALL 開啟時讀取 `data/user_lists.json` 作為共享推薦清單；owner 本地點 ★ 透過 `/api/user_lists` 即時寫回。在純靜態環境（GitHub Pages）POST 失敗時 SHALL fail-safe 切換為本機模式（localStorage），並提示「你目前在看分享的推薦清單」→ 本機編輯不影響 repo 檔案。

#### Scenario: 訪客點 ★
- **WHEN** 訪客在 GitHub Pages 上點某卡片的 ★
- **THEN** 自動切換本機模式，變更只存訪客自己的 localStorage

### Requirement: 我的最愛（♥）純本機

系統 SHALL 將最愛清單只存在使用者自己的 localStorage，並提供 toolbar 匯出（下載 JSON）與匯入（合併 / 取代兩種模式）。

#### Scenario: 匯入朋友的最愛
- **WHEN** 使用者透過 toolbar ⇩ 匯入朋友分享的 JSON 並選「合併」
- **THEN** 保留原有最愛並加上檔案內的新條目
