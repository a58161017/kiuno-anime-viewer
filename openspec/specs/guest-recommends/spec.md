# guest-recommends Specification

## Purpose

`recommends.html` 讓任何訪客留言推薦動漫，後端用 Firebase Firestore。公開顯示暱稱/動畫/說明/時間，後台另存 audit metadata 供 owner 防濫用追查。

## Requirements

### Requirement: 留言提交與顯示

系統 SHALL 提供表單（暱稱 ≤ 20 字、動畫名 ≤ 100 字、說明 5–500 字）寫入 Firestore `recommends` collection，並即時顯示於留言清單。留言中的動畫名 SHALL 連結到 `index.html?id=...`。

#### Scenario: 正常留言
- **WHEN** 訪客填妥合法欄位並送出
- **THEN** 留言寫入 Firestore 且立刻出現在清單；其他裝置也看得到同一筆

### Requirement: Audit metadata（不可移除）

每筆留言 SHALL 隨附 `audit` 物件存後台（不公開顯示）：IP（`https://api.ipify.org/?format=json`，fail-soft）、userAgent、platform、languages、螢幕與視窗尺寸、時區、referrer。此收集邏輯不得移除。

#### Scenario: IP 服務失效
- **WHEN** ipify 查詢失敗
- **THEN** 留言仍正常送出，audit 內 IP 欄位缺省（fail-soft）

### Requirement: 反濫用機制

系統 SHALL 同時具備：
- Honeypot：隱藏 `website` 欄位，rules 用 `keys().hasOnly([...])` 擋掉多餘欄位
- Client rate limit：localStorage 記錄上次提交時間，60 秒內拒絕再送
- 欄位長度限制：UI 與 firestore.rules 雙保險
- 不可改不可刪：rules 禁止 update/delete，owner 從 Firebase Console 管理

#### Scenario: Bot 填了 honeypot
- **WHEN** 提交內容包含 `website` 欄位
- **THEN** Firestore rules 拒絕寫入（silent reject）

#### Scenario: 連續提交
- **WHEN** 同一瀏覽器 60 秒內第二次送出
- **THEN** UI 提示「請稍候 60 秒」且不送出

### Requirement: 隱私聲明（目前停用，有條件恢復）

目前僅公開給親友使用，表單下方的隱私聲明已於 2026-05-16 移除（`.privacy-note` CSS 規則保留）。若日後專案要完全公開給陌生流量（大規模宣傳 / 商業推廣 / SEO 引流），SHALL 把隱私聲明加回 `recommends.html` 表單底部，以符合個資法 / GDPR 告知義務。

#### Scenario: 轉為完全公開
- **WHEN** owner 決定把專案公開給網路上所有人
- **THEN** 恢復 `.privacy-note` 隱私聲明後才對外宣傳
