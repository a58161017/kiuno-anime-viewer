# knowledge-graph Specification

## Purpose

`graph.html` 以 Cytoscape.js + fcose 力導向布局呈現層級式知識圖：分類 → 標籤 → 動畫三層，資料來自 pipeline 產出的 `data/graph.json`。

## Requirements

### Requirement: 三層層級結構

系統 SHALL 提供三個層級的視圖：
- Level 0（分類）：節點為分類，共有動畫 ≥ 5 部的分類間連邊
- Level 1（標籤）：點分類進入，顯示該分類內 top 50 tags，共現達門檻的 tag 對連邊
- Level 2（動畫）：點標籤進入，顯示該分類+標籤的所有動畫，邊來自 `graph.json`

#### Scenario: 逐層下鑽
- **WHEN** 使用者在 Level 0 點「動作」分類，再點某個 tag
- **THEN** 依序進入 Level 1（該分類的 tags）與 Level 2（符合的動畫）

### Requirement: 切層互動

系統 SHALL 支援三種切層方式：點擊節點、麵包屑導航、滾輪縮放越過閾值。

#### Scenario: 滾輪切層
- **WHEN** 使用者在 Level 0 持續放大越過縮放閾值
- **THEN** 自動進入下一層級

### Requirement: 邊類型與權重

Level 2 的邊 SHALL 依 `graph.json` 的類型顯示：`franchise`（1.0，永遠顯示）、`same_studio`（0.3）、`shared_tag`（0.15 × 交集數）。`shared_genre` 與 `same_year` 在 Level 2 不顯示以避免雜訊。

#### Scenario: 系列作連線
- **WHEN** 兩部動畫在 AniList relations 中為前傳/續作關係
- **THEN** 以 `franchise` 邊相連且永遠顯示
