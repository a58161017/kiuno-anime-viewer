# deployment Specification

## Purpose

GitHub Pages 純靜態部署（`.github/workflows/deploy.yml`）：push main 觸發，注入 Firebase secrets 後上 Pages。含「先本地驗證再 push」的流程鐵則。

## Requirements

### Requirement: Firebase config 注入

repo 內 `firebase-config.js` SHALL 只含 `REPLACE_ME` placeholder；部署 workflow SHALL 從 GitHub Secrets 生成真實 config 再上傳 Pages artifact。本地開發手動填真值且用 `git update-index --skip-worktree` 避免誤 commit。

#### Scenario: 部署時生成
- **WHEN** push 到 main 觸發 deploy workflow
- **THEN** workflow 以 secrets 覆寫 firebase-config.js（log 遮蔽實值）後部署

#### Scenario: Secrets 未設定
- **WHEN** 任一 Firebase secret 為空
- **THEN** 生成的 `isConfigured` 為 false，前端據此降級處理

### Requirement: 先本地驗證再 push

功能變更完成後 SHALL 停在本地驗證階段：確認本地 server 運作、提供測試清單、等使用者明確確認（「OK」「推上去」等）才執行 push。例外：使用者當次明確說「直接 push」「上線」「部署吧」。

#### Scenario: 標準流程
- **WHEN** 一項 UI 變更改完
- **THEN** 先提供 `http://127.0.0.1:8000/kiuno-anime-viewer/` 測試清單，等確認後才 commit + push

### Requirement: Push 附帶版號義務

每次 push SHALL 先完成 changelog-versioning spec 要求的版號 +1 與 changelog 條目（見 changelog-versioning）。

#### Scenario: 準備 push
- **WHEN** 使用者確認可以推上去
- **THEN** 先確認 version.json / changelog.json 已更新，再執行 push

### Requirement: 靜態規模限制

部署內容 SHALL 維持在 GitHub Pages 限制內（目前 anime.json ~3MB、封面 ~50MB、graph.json ~4MB，上限 1GB）；可重生的中間檔（cache、entries.matched 等）不進 repo。

#### Scenario: 中間檔不入版控
- **WHEN** pipeline 產出 cache / entries.matched.json 等中間檔
- **THEN** .gitignore 排除，不出現在 commit
