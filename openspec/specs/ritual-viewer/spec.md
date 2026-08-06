# ritual-viewer Specification

## Purpose

`ritual.html` 是儀式感抽卡頁：3D 環狀卡片展示（10 張），用 MediaPipe 手勢或鍵盤操作，含 6 phase 洗牌動畫。卡池來源可為季別推薦、推薦清單或全庫。

## Requirements

### Requirement: 3D 環狀展示與狀態機

系統 SHALL 以 3D 環狀（ring，帶 rotateX 傾斜）排列卡片，狀態機為 `ring`（環狀瀏覽）↔ `focus`（單卡聚焦，放大並顯示簡介）。手機與桌機 SHALL 使用不同的 focus 前推距離與縮放（手機下方保留資訊面板空間）。

#### Scenario: 進入聚焦
- **WHEN** 使用者在 ring 狀態選定一張卡（手勢比石頭 ✊ 持續超過 debounce 時間，或鍵盤確認）
- **THEN** 該卡前推放大進入 focus 狀態，延遲後顯示簡介

### Requirement: 手勢控制

系統 SHALL 用 MediaPipe 內建手勢辨識支援：
- 單手 ✋ 揮動 → ring 旋轉（含慣性與摩擦衰減）
- 石頭 ✊（debounce 280ms）→ 進 focus；focus 內石頭上下移動 → 捲動簡介
- 布 ✋（debounce 130ms）→ 退出 focus
- focus 內其他辨識手勢（Pointing_Up / Victory / Thumb 系 / ILoveYou）快速位移 → swipe 切卡
- 雙手 ✋ Open_Palm（穩定 3 幀 + 800ms）→ 重新洗牌
- Thumb_Up 持續 1000ms → 離開頁面

手勢判斷 SHALL 含防誤觸機制（deadzone、剛進 focus 的 disarm 期、swipe rearm 冷卻）。

#### Scenario: 雙手洗牌
- **WHEN** 使用者雙手張開（Open_Palm × 2）穩定持續超過 debounce 時間
- **THEN** 觸發重新洗牌，從剩餘卡池抽出新的一組卡片

### Requirement: 鍵盤替代操作

系統 SHALL 提供鍵盤等效操作（← → 旋轉加 velocity、確認/退出鍵），確保無攝影機環境也能完整使用。

#### Scenario: 無攝影機
- **WHEN** 使用者未授權攝影機
- **THEN** 仍可用鍵盤完成瀏覽、聚焦、洗牌等全部操作

### Requirement: 6 phase 洗牌動畫

洗牌 SHALL 依序播放 6 個 phase：collect（收攏）→ toss（舊疊飛走）→ enter（新牌堆滑入）→ riffle（交叉插牌 ×2）→ deal（stagger 發 10 張）→ exit（剩餘牌堆滑出）。

#### Scenario: 完整洗牌
- **WHEN** 觸發洗牌且卡池剩餘 ≥ 1 張
- **THEN** 依序播放 6 phase 動畫後呈現新一組卡片

### Requirement: 不重複抽卡

系統 SHALL 以 session 為單位記錄已展示過的卡片 id（含當前組），洗牌只從未展示過的池子抽；池子抽完時 SHALL 顯示「已抽完」提示而非重複。

#### Scenario: 卡池耗盡
- **WHEN** 全部卡池 id 都已展示過且使用者再次洗牌
- **THEN** 顯示已抽完提示，不重複發卡
