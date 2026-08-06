# changelog-versioning Specification

## Purpose

版號與更新紀錄管理：`data/version.json`（目前版號）、`data/changelog.json`（歷次變更）、`changelog.html`（timeline 呈現頁）。

## Requirements

### Requirement: 每次 push 必 bump 版號

每次 push 上 GitHub 前 SHALL：
1. `data/version.json` 的 `current` patch +1、更新 `updated_at`
2. 在 `data/changelog.json` 的 `versions` 陣列**最前面**插入新條目

#### Scenario: 推送功能變更
- **WHEN** 一次功能變更要 push
- **THEN** version.json 與 changelog.json 都已對應更新，且新條目在陣列最前面

### Requirement: Changelog 條目格式

每個條目 SHALL 含 `version`、`date`（YYYY-MM-DD）、`summary`（一句話重點）、`changes` 物件，`changes` 依性質分類為 `added` / `fixed` / `removed` / `ui` / `infra` 陣列。新增/修改/刪除任何動畫 SHALL 列在對應分類，格式為「中文標題 (anilist:<id>)」。

#### Scenario: 新增動畫條目
- **WHEN** 本次 push 新增了一部動畫
- **THEN** changelog 條目的 `changes.added` 含「該動畫中文標題 (anilist:<id>)」

### Requirement: Changelog 頁面

`changelog.html` SHALL 以 timeline 形式呈現 `data/changelog.json` 全部版本，含分類標籤（sleek labels）。

#### Scenario: 瀏覽更新紀錄
- **WHEN** 使用者開啟 `changelog.html`
- **THEN** 依時間倒序看到各版本的 summary 與分類變更明細
