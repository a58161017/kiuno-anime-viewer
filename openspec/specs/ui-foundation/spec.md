# ui-foundation Specification

## Purpose

全站共通的 UI/前端工程守則：mobile-first CSS、Alpine.js 啟動方式、設計 tokens（sleek modern 主題 + ritual 橘黃 sub-theme）。

## Requirements

### Requirement: Mobile-first CSS

所有 CSS SHALL 用 mobile-first 寫法：預設樣式針對手機（≤599px），`@media (min-width: 600px)` 才往上加平板/桌機 override。不得直接套桌機優先範本。

#### Scenario: 新增頁面樣式
- **WHEN** 為新頁面或元件寫 CSS
- **THEN** 375px 寬度先完全可用，再以 min-width 疊加大螢幕樣式

### Requirement: Alpine.js 啟動方式

使用 Alpine.js 的頁面 SHALL 用 ES module 寫法（`import Alpine from ".../module.esm.js"` + `Alpine.start()`），不得用 `defer` script 載入，以避免啟動順序問題。

#### Scenario: 新增互動頁
- **WHEN** 新頁面需要 Alpine.js
- **THEN** 以 module import + 手動 `Alpine.start()` 初始化（範例見 recommends.html）

### Requirement: 設計主題

全站 SHALL 對齊 sleek modern 設計 tokens（v1.1.0 重設計）；`ritual.html` 保留橘黃 sub-theme 但同樣對齊 tokens 體系。

#### Scenario: 新元件配色
- **WHEN** 新增 UI 元件
- **THEN** 使用既有 tokens（styles.css / css/ritual.css），不引入體系外的色票

### Requirement: 已知渲染地雷

前端實作 SHALL 避開已知地雷：手機 Safari 對 `backdrop-filter` + 半透明小元素會渲染破圖 —— icon empty state 用實心半透明背景 + 固定 `line-height` + `text-align:center`，不用 flex。

#### Scenario: 小型 icon 元素
- **WHEN** 實作小尺寸半透明 icon 元素
- **THEN** 不使用 backdrop-filter + flex 組合
