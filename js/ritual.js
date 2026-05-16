// kiuno-anime-viewer · ritual.html Alpine app
// 3D 環狀卡片展示 + 手勢/鍵盤控制狀態機 (含慣性 + 1 指 swipe 切卡)

import { startGesture } from "./ritual-gesture.js?v=7";

// ===== 設定常數 =====
const MOVE_ROT_SCALE = 280;    // 揮手 dx (0..1) 換成多少度/frame
const MOVE_DEADZONE = 0.004;   // 過濾 MediaPipe 抖動
const ENTER_DEBOUNCE_MS = 280; // 比石頭要持續 ms 才進 focus
const EXIT_DEBOUNCE_MS  = 130; // 比布要持續 ms 才退出 focus
const FOCUS_SYNOPSIS_DELAY_MS = 300;
const KBD_ROT_VEL = 4.5;       // 鍵盤 ← → 每按一下加多少 velocity (degree/frame)
const FRICTION = 0.9;          // 慣性摩擦：每 RAF tick velocity *= 0.9
const MIN_VEL = 0.04;          // velocity 小於此值視為停止
const SWIPE_DX_THRESHOLD = 0.028; // 觸發 swap 的單 frame dx (越大要越快)
const SWIPE_REARM_MS = 600;       // 一次 swipe 完成後多久才能再觸發
const SWAP_ANIM_MS = 480;         // 卡片 swap 動畫長度
const ENTER_FOCUS_DISARM_MS = 400; // 剛進 focus 多久內不認 swipe (避免握拳手抖誤觸)
// 在 focus 內可以觸發 swap 的手勢：除了「布」跟「石頭」以外的識別手勢
// (石頭 ✊ 在 focus 中專用來上下捲動簡介，不再做切卡)
const SWIPE_GESTURES = new Set([
  'Pointing_Up', 'Victory',
  'Thumb_Up', 'Thumb_Down', 'ILoveYou',
]);
const FIST_SCROLL_SCALE = 800;   // dy (0..1 normalized) × scale = scrollTop 變化量 (px)
const FIST_SCROLL_DEADZONE = 0.003;
// 石頭握住起點到當前 y 的累積位移要超過 4% 畫面高才開始 scroll，避免手抖誤觸
const FIST_SCROLL_START_THRESHOLD = 0.04;
const FOCUS_FWD_MOBILE = 180;     // 手機別推太前 (面板要在下方有空間)
const FOCUS_FWD_DESKTOP = 320;
const FOCUS_SCALE_MOBILE = 1.35;  // 手機留空間給下方資訊面板
const FOCUS_SCALE_DESKTOP = 1.9;
const RING_TILT_DEG = 18;      // ring 的 rotateX 度數

// ===== 雙手 ✋ Open_Palm 手勢 (重新洗牌) =====
// v1.2.2: 從「雙手矩形」(自訂 landmark 邏輯，threshold 難調) 改回 MediaPipe 內建
// Open_Palm × 2，最穩；與「單手 ✋ 揮動旋轉」用 hands.length === 2 區分
const DUAL_PALM_STABLE_FRAMES = 3;        // 連續 N 幀都通過才開始計時
const RESHUFFLE_DEBOUNCE_MS = 800;        // 計時累積此時間才觸發

// ===== 拇指朝上手勢 (離開頁面) — MediaPipe 內建 Thumb_Up =====
// v1.2.1: 改用內建手勢取代自寫拇指朝右 (穩定度遠高於 landmark 自寫)
const THUMB_UP_DEBOUNCE_MS = 1000;        // 持續此時間才觸發離開

// ===== 洗牌動畫時長 (v1.3.0 — 6 phase 儀式感重設計) =====
const SHUFFLE_COLLECT_MS = 600;   // 400ms 動畫 + 200ms stagger buffer (10 張 × 20ms)
const SHUFFLE_TOSS_MS = 500;      // 中央那疊往右上 35° 飛走
const SHUFFLE_ENTER_MS = 500;     // 新牌堆 stack 從右邊滑進中央 (ease-spring)
const SHUFFLE_RIFFLE_MS = 1000;   // 撲克牌交叉插 2 次
const SHUFFLE_DEAL_MS = 800;      // 10 張新卡 stagger 60ms × 10 + 動畫 500ms 末尾餘量
const SHUFFLE_EXIT_MS = 400;      // 剩餘 stack 從左邊滑出

export function ritualData() {
  return {
    // ===== 資料 =====
    cards: [],
    sourceLabel: "",
    sourceKey: "",        // 'season' | 'recommend' | 'all'
    loadError: "",
    loading: true,
    _animeById: {},        // anime.json 全部 (for 抽新牌)
    _initialPool: [],      // 此 session 可抽的全部 ids (從 sessionStorage 或 URL)
    _usedIds: null,        // Set<id>: 已展示過的 (含當前 cards)

    // ===== 洗牌動畫狀態 =====
    shuffling: false,
    shufflePhase: null,    // 'fly-out' | 'shuffling' | 'deal' | null
    shuffleError: "",      // 「已抽完」等提示

    // ===== 狀態 =====
    state: 'ring',            // 'ring' | 'focus'
    globalRotation: 0,
    rotationVelocity: 0,      // 慣性：每 frame 加到 globalRotation 上
    focusIdx: null,
    synopsisShown: false,

    // ===== Swap 動畫狀態 (focus 內 1 指撥動切卡) =====
    swapping: false,
    _swapOldIdx: null,
    _swapNewIdx: null,
    _swapDelta: 0,            // -1 = 切到前一張 (右撇)、+1 = 切到下一張 (左撇)
    _swapPhase: null,         // null | 'init' | 'animate'
    _swipeArmed: true,        // false 時忽略 swipe，防連觸發
    _swipeArmTimer: null,

    // ===== 手勢/輸入 =====
    mode: 'keyboard',
    gestureStatus: 'idle',
    modeError: "",
    lastGesture: null,
    showCam: true,
    _gStable: null,
    _gStableStart: 0,
    _lastHandX: null,
    _lastHandY: null,
    _fistAnchorY: null,        // 石頭手勢起點 y (用來算累積位移、判定 scroll 啟動門檻)
    _fistScrollActive: false,  // 累積位移過門檻後才開啟 scroll
    _palmStableFrames: 0,      // 雙手 ✋ 連續通過幀數
    _palmStableSince: 0,       // 達 STABLE_FRAMES 後的計時起點
    _thumbUpStableSince: 0,    // 拇指朝上計時起點
    _palmProgress: 0,          // 雙手 ✋ 觸發進度 0..1 (debug UI 用)
    _thumbUpProgress: 0,       // 拇指朝上觸發進度 0..1 (debug UI 用)
    _synopsisEl: null,    // 快取 .ritual__panel-synopsis 避免每 frame 查 DOM
    _gestureHandle: null,
    _synopsisTimer: null,
    _focusIdxClearTimer: null,
    _kbdHandler: null,
    _resizeHandler: null,
    _rafId: null,

    viewportW: window.innerWidth,

    // ===== 生命週期 =====
    async init() {
      this._setupResize();
      this._setupKeyboard();
      this._startRAF();   // 慣性 / 平滑旋轉的 RAF loop

      // URL
      const params = new URLSearchParams(location.search);
      const idsStr = params.get('ids') || '';
      const src = params.get('src') || '';
      this.sourceKey = src;
      this.sourceLabel = ({
        season: '本季新番',
        recommend: '我的推薦',
        all: '全部動畫',
      })[src] || '';

      let ids = idsStr.split(',').map(s => s.trim()).filter(Boolean);

      // Fallback: 沒帶 ids 但 src=all (從 nav link 跳來) → 先 fetch anime.json 再 random 抽 10
      const noIdsButCanFallback = ids.length === 0 && src === 'all';

      if (ids.length === 0 && !noIdsButCanFallback) {
        this.loadError = "沒帶 ids 參數，無法召喚";
        this.loading = false;
        return;
      }

      // sessionStorage 帶整個 pool (給洗牌「不重複抽」用)，fallback 為 URL ids
      let poolFromStorage = null;
      try {
        const raw = sessionStorage.getItem('ritualPool');
        if (raw) {
          const obj = JSON.parse(raw);
          if (obj && Array.isArray(obj.pool) && obj.source === src) {
            poolFromStorage = obj.pool;
          }
        }
      } catch (e) {}

      try {
        const resp = await fetch("data/anime.json", { cache: "no-cache" });
        if (!resp.ok) throw new Error(resp.status + " " + resp.statusText);
        const db = await resp.json();
        const byId = db.anime || {};
        this._animeById = byId;

        // Fallback: 沒帶 ids 時從 anime.json 全部隨機抽 10
        if (noIdsButCanFallback) {
          const allIds = Object.keys(byId);
          for (let i = allIds.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [allIds[i], allIds[j]] = [allIds[j], allIds[i]];
          }
          ids = allIds.slice(0, 10);
        }

        this.cards = ids.map(id => byId[id]).filter(Boolean);
        if (this.cards.length === 0) {
          this.loadError = "找不到帶入的動漫資料";
          this.loading = false;
          return;
        }

        // Pool 維護：initialPool 從 sessionStorage 或 fallback 為 URL ids
        // 對於 fallback 從 anime.json 全抽的情境，pool 就是全部 anime
        const basePool = poolFromStorage ||
                         (noIdsButCanFallback ? Object.keys(byId) : ids);
        this._initialPool = basePool.filter(id => byId[id]);
        this._usedIds = new Set(this.cards.map(c => c.id));  // 當前展示算「已用」
      } catch (e) {
        console.error(e);
        this.loadError = "載入 anime.json 失敗：" + (e.message || e);
        this.loading = false;
        return;
      }

      this.loading = false;
      this._startGestureBackground();
    },

    destroy() {
      try { this._gestureHandle?.stop?.(); } catch (e) {}
      if (this._kbdHandler) {
        window.removeEventListener('keydown', this._kbdHandler, true);
        document.removeEventListener('keydown', this._kbdHandler, true);
      }
      if (this._resizeHandler) window.removeEventListener('resize', this._resizeHandler);
      if (this._synopsisTimer) clearTimeout(this._synopsisTimer);
      if (this._swipeArmTimer) clearTimeout(this._swipeArmTimer);
      if (this._focusIdxClearTimer) clearTimeout(this._focusIdxClearTimer);
      if (this._rafId) cancelAnimationFrame(this._rafId);
    },

    // ===== 慣性 RAF loop =====
    _startRAF() {
      const tick = () => {
        // 慣性旋轉只在 ring 狀態套用 (focus / swap 中不轉)
        if (this.state === 'ring' && !this.swapping) {
          if (Math.abs(this.rotationVelocity) > MIN_VEL) {
            this.globalRotation += this.rotationVelocity;
            this.rotationVelocity *= FRICTION;
          } else if (this.rotationVelocity !== 0) {
            this.rotationVelocity = 0;
          }
        }
        this._rafId = requestAnimationFrame(tick);
      };
      this._rafId = requestAnimationFrame(tick);
    },

    _setupResize() {
      this._resizeHandler = () => { this.viewportW = window.innerWidth; };
      window.addEventListener('resize', this._resizeHandler);
    },

    // ===== 鍵盤 =====
    _setupKeyboard() {
      const self = this;
      const handler = function (ev) {
        const tag = ev.target?.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;

        const isSpace = ev.code === 'Space' || ev.key === ' ' || ev.keyCode === 32 || ev.which === 32;

        if (isSpace) {
          ev.preventDefault();
          ev.stopPropagation();
          if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
          try { document.activeElement?.blur?.(); } catch (e) {}
          if (self.loading || self.loadError) return;
          if (self.state === 'ring') self._enterFocus();
          else if (self.state === 'focus' && !self.swapping) self._exitFocus();
          return;
        }
        if (ev.key === 'ArrowLeft') {
          ev.preventDefault();
          if (self.state === 'ring') self.rotationVelocity -= KBD_ROT_VEL;
          else if (self.state === 'focus') self._tryStartSwap(-1);
          return;
        }
        if (ev.key === 'ArrowRight') {
          ev.preventDefault();
          if (self.state === 'ring') self.rotationVelocity += KBD_ROT_VEL;
          else if (self.state === 'focus') self._tryStartSwap(+1);
          return;
        }
        if (ev.key === 'Escape') {
          ev.preventDefault();
          self.exit();
          return;
        }
        if (ev.key === 'r' || ev.key === 'R') {
          ev.preventDefault();
          if (!self.shuffling) self._reshuffle();
          return;
        }
      };
      this._kbdHandler = handler;
      // 雙重防禦：window + document，capture phase 確保 button focus 時也攔得到
      window.addEventListener('keydown', handler, true);
      document.addEventListener('keydown', handler, true);
    },

    // ===== 手勢 =====
    async _startGestureBackground() {
      if (this.gestureStatus !== 'idle') return;
      this.gestureStatus = 'loading';
      const video = this.$refs.cam;
      let handle;
      try {
        handle = await startGesture({
          video,
          onFrame: (payload) => this._onGestureFrame(payload),
        });
      } catch (e) {
        this.gestureStatus = 'failed';
        this.modeError = String(e?.message || e || '').slice(0, 200);
        return;
      }
      if (this.gestureStatus === 'skipped') {
        try { handle?.stop?.(); } catch (e) {}
        return;
      }
      this._gestureHandle = handle;
      if (handle.mode === 'camera') {
        this.mode = 'camera';
        this.gestureStatus = 'ready';
      } else {
        this.gestureStatus = 'failed';
        this.modeError = String(handle.error?.message || handle.error || '').slice(0, 200);
      }
    },

    skipGesture() {
      this.gestureStatus = 'skipped';
      this.mode = 'keyboard';
      try { this._gestureHandle?.stop?.(); } catch (e) {}
      this._gestureHandle = null;
    },

    _onGestureFrame({ gesture, score, x, y, hands }) {
      const now = performance.now();
      const rawG = (gesture && score > 0.6) ? gesture : null;
      this.lastGesture = rawG;

      // 動畫期間 (洗牌中) 完全跳過手勢處理，避免狀態混亂
      if (this.shuffling) {
        this._resetStableCounters();
        return;
      }

      // ---- 雙手 ✋ Open_Palm → 重新洗牌 ----
      // 兩隻手都被偵測到且都辨識為 Open_Palm。跟單手 ✋ 揮動旋轉用 hands.length 區分
      const dualPalmOK = this._detectDualPalm(hands);
      if (dualPalmOK) {
        this._palmStableFrames++;
        if (this._palmStableFrames === DUAL_PALM_STABLE_FRAMES) {
          this._palmStableSince = now;
        }
        if (this._palmStableFrames >= DUAL_PALM_STABLE_FRAMES) {
          const elapsed = now - this._palmStableSince;
          this._palmProgress = Math.min(1, elapsed / RESHUFFLE_DEBOUNCE_MS);
          if (elapsed >= RESHUFFLE_DEBOUNCE_MS) {
            this._palmStableFrames = 0;
            this._palmStableSince = 0;
            this._palmProgress = 0;
            this._reshuffle();
            return;
          }
        } else {
          // 連幀累積階段顯示前 30% 進度
          this._palmProgress = (this._palmStableFrames / DUAL_PALM_STABLE_FRAMES) * 0.3;
        }
      } else {
        this._palmStableFrames = 0;
        this._palmStableSince = 0;
        this._palmProgress = 0;
      }

      // ---- 拇指朝上 (任一手是 Thumb_Up) → 離開頁面 ----
      // 任一手手勢被偵測為 Thumb_Up (score > 0.6 已在外層判定，但需要遍歷 hands array)
      const thumbUpOK = (hands || []).some(h => h && h.gesture === 'Thumb_Up' && h.score > 0.6);
      if (thumbUpOK) {
        if (this._thumbUpStableSince === 0) {
          this._thumbUpStableSince = now;
        }
        const elapsed = now - this._thumbUpStableSince;
        this._thumbUpProgress = Math.min(1, elapsed / THUMB_UP_DEBOUNCE_MS);
        if (elapsed >= THUMB_UP_DEBOUNCE_MS) {
          this._thumbUpStableSince = 0;
          this._thumbUpProgress = 0;
          this.exit();
          return;
        }
      } else {
        this._thumbUpStableSince = 0;
        this._thumbUpProgress = 0;
      }

      // ---- 算 dx / dy (不管手勢，都追蹤) ----
      let dx = 0, dy = 0;
      if (typeof x === 'number') {
        if (this._lastHandX != null) dx = x - this._lastHandX;
        this._lastHandX = x;
      } else {
        this._lastHandX = null;
      }
      if (typeof y === 'number') {
        if (this._lastHandY != null) dy = y - this._lastHandY;
        this._lastHandY = y;
      } else {
        this._lastHandY = null;
      }

      // ---- 布 + 揮動：給 rotationVelocity (慣性接手) ----
      // 但雙手 ✋ 時 (洗牌觸發中) 不算單手旋轉，避免衝突
      if (!dualPalmOK && this.state === 'ring' && rawG === 'Open_Palm' && Math.abs(dx) > MOVE_DEADZONE) {
        this.rotationVelocity = dx * MOVE_ROT_SCALE;
      }

      // ---- 快速撥動：swap 卡片 (focus 內，除了「布 / 石頭」以外的手勢) ----
      if (this.state === 'focus' && SWIPE_GESTURES.has(rawG)
          && this._swipeArmed && Math.abs(dx) > SWIPE_DX_THRESHOLD) {
        // dx > 0 = 手往右 → 右撇 → delta = -1 (前一張 / 視覺上左邊的卡進中央)
        this._tryStartSwap(dx > 0 ? -1 : +1);
      }

      // ---- 石頭 + 上下移動：滾動簡介 (focus 中、非 swap 中、簡介已淡入) ----
      // 流程：握石頭瞬間記 anchor y → 累積位移過 START_THRESHOLD 才「啟動」scroll
      // → 啟動後用 dy 持續滾。手勢一變或離開 focus 就重設 anchor。
      const fistScrollEligible = this.state === 'focus' && !this.swapping
                              && this.synopsisShown && rawG === 'Closed_Fist'
                              && typeof y === 'number';
      if (fistScrollEligible) {
        if (this._fistAnchorY === null) {
          this._fistAnchorY = y;
          this._fistScrollActive = false;
        } else if (!this._fistScrollActive
                   && Math.abs(y - this._fistAnchorY) > FIST_SCROLL_START_THRESHOLD) {
          this._fistScrollActive = true;
        }
        if (this._fistScrollActive && Math.abs(dy) > FIST_SCROLL_DEADZONE) {
          this._scrollSynopsis(dy * FIST_SCROLL_SCALE);
        }
      } else {
        // 換手勢 / 離開 focus / swap 中：清除 anchor，下次重新握石頭重新計算
        this._fistAnchorY = null;
        this._fistScrollActive = false;
      }

      // ---- 時間式手勢防抖 (進 / 出 focus) ----
      if (rawG !== this._gStable) {
        this._gStable = rawG;
        this._gStableStart = now;
      }
      const stableMs = now - this._gStableStart;

      if (this.state === 'ring' && rawG === 'Closed_Fist' && stableMs >= ENTER_DEBOUNCE_MS) {
        this._enterFocus();
      } else if (this.state === 'focus' && !this.swapping
                 && rawG === 'Open_Palm' && stableMs >= EXIT_DEBOUNCE_MS) {
        this._exitFocus();
      }
    },

    // ===== State transitions =====
    _enterFocus() {
      if (this.cards.length === 0) return;
      this.focusIdx = this._computeFocusIdx();
      this.state = 'focus';
      this.synopsisShown = false;
      this.rotationVelocity = 0;   // focus 中停止旋轉
      // 剛進 focus 短暫鎖 swipe，避免握拳那瞬間手抖誤觸切卡
      this._swipeArmed = false;
      if (this._swipeArmTimer) clearTimeout(this._swipeArmTimer);
      this._swipeArmTimer = setTimeout(() => { this._swipeArmed = true; }, ENTER_FOCUS_DISARM_MS);
      if (this._synopsisTimer) clearTimeout(this._synopsisTimer);
      this._synopsisTimer = setTimeout(() => {
        if (this.state === 'focus') this.synopsisShown = true;
      }, FOCUS_SYNOPSIS_DELAY_MS);
    },

    _exitFocus() {
      this.state = 'ring';
      this.synopsisShown = false;
      if (this._synopsisTimer) clearTimeout(this._synopsisTimer);
      if (this._focusIdxClearTimer) clearTimeout(this._focusIdxClearTimer);
      this._focusIdxClearTimer = setTimeout(() => {
        if (this.state === 'ring') this.focusIdx = null;
      }, 600);
      this._synopsisEl = null;   // 下次 focus 重新拿 DOM ref (簡介容器可能被 Alpine 重渲染)
    },

    _scrollSynopsis(deltaPx) {
      // 找 .ritual__panel-synopsis (Alpine x-show 切換時 DOM 還在，所以可以快取)
      if (!this._synopsisEl || !this._synopsisEl.isConnected) {
        this._synopsisEl = document.querySelector('.ritual__panel-synopsis');
      }
      if (!this._synopsisEl) return;
      const max = this._synopsisEl.scrollHeight - this._synopsisEl.clientHeight;
      if (max <= 0) return;  // 內容不需要滾
      this._synopsisEl.scrollTop = Math.max(0, Math.min(max, this._synopsisEl.scrollTop + deltaPx));
    },

    _resetStableCounters() {
      this._palmStableFrames = 0;
      this._palmStableSince = 0;
      this._palmProgress = 0;
      this._thumbUpStableSince = 0;
      this._thumbUpProgress = 0;
    },

    // ===== 雙手 ✋ 判定 (重新洗牌觸發) =====
    // 條件：兩隻手都被偵測到 + 兩手都辨識為 Open_Palm + score 都 > 0.6
    // 跟單手 ✋ 揮動旋轉用 hands.length === 2 區分；MediaPipe 內建模型，
    // 比自寫 landmark 邏輯 (雙手矩形) 穩定許多
    _detectDualPalm(hands) {
      if (!Array.isArray(hands) || hands.length < 2) return false;
      return hands.every(h => h && h.gesture === 'Open_Palm' && h.score > 0.6);
    },

    get _remainingPool() {
      if (!this._initialPool || !this._usedIds) return [];
      return this._initialPool.filter(id => !this._usedIds.has(id));
    },

    canReshuffle() {
      return !this.shuffling && this._remainingPool.length > 0;
    },

    async _reshuffle() {
      if (this.shuffling) return;
      const remaining = this._remainingPool;
      if (remaining.length === 0) {
        this.shuffleError = "已抽完未看過的卡片，離開頁面重進可重置";
        setTimeout(() => { this.shuffleError = ""; }, 3000);
        return;
      }

      // 若在 focus 狀態先 exit 縮回環，等動畫
      if (this.state === 'focus') {
        this._exitFocus();
        await new Promise(r => setTimeout(r, 600));
      }

      const sleep = (ms) => new Promise(r => setTimeout(r, ms));

      this.shuffling = true;
      this._resetStableCounters();

      // Phase 1a: collect — 環上 10 張卡 stagger 20ms 收到中央 + 略放大
      this.shufflePhase = 'collect';
      await sleep(SHUFFLE_COLLECT_MS);

      // Phase 1b: toss — 中央那疊整體往右上 35° 飛出 + opacity 0
      this.shufflePhase = 'toss';
      await sleep(SHUFFLE_TOSS_MS);

      // toss 動畫結束 → 必須立即清空舊 cards。
      // 否則 .tossing class 在下一 phase 被 Alpine 移除後，CSS animation 的
      // forwards fill-mode 失效，舊 10 張卡會「彈回」ring 位置 (opacity 1)，
      // 視覺上會跟 enter 階段的新卡背 stack 同時出現
      this.cards = [];

      // Phase 2: enter — 新卡背 stack 從右邊滑進中央 (ease-spring)
      this.shufflePhase = 'enter';
      await sleep(SHUFFLE_ENTER_MS);

      // Phase 3: riffle — 5 張卡背上下兩半交叉插 (撲克牌 riffle shuffle) 2 次
      this.shufflePhase = 'riffle';
      await sleep(SHUFFLE_RIFFLE_MS);

      // Phase 4: deal — 從 remaining pool 抽 N 張新卡 (最多 10) 替換 cards array
      //          新卡 stagger 60ms 從中央 scale 0.4 滑進環位置
      const pool = remaining.slice();
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
      }
      const newIds = pool.slice(0, 10);
      newIds.forEach(id => this._usedIds.add(id));
      this.cards = newIds.map(id => this._animeById[id]).filter(Boolean);
      this.globalRotation = 0;
      this.rotationVelocity = 0;
      this.focusIdx = null;
      this.shufflePhase = 'deal';
      // 發牌時長依實際發出張數調整 (stagger 60ms × N + 動畫 500ms)
      const dealMs = this.cards.length * 60 + 500;
      await sleep(Math.min(dealMs, SHUFFLE_DEAL_MS));

      // Phase 5: exit — 剩餘卡背 stack 從左邊滑出 + opacity 0
      this.shufflePhase = 'exit';
      await sleep(SHUFFLE_EXIT_MS);

      this.shuffling = false;
      this.shufflePhase = null;
    },

    _computeFocusIdx() {
      const N = this.cards.length;
      if (N === 0) return null;
      let best = 0, bestDist = 9999;
      for (let i = 0; i < N; i++) {
        const a = (360 / N) * i + this.globalRotation;
        const norm = ((a % 360) + 360) % 360;
        const dist = Math.min(norm, 360 - norm);
        if (dist < bestDist) { bestDist = dist; best = i; }
      }
      return best;
    },

    // ===== Swap (1 指撥動切卡) =====
    _tryStartSwap(delta) {
      if (this.swapping || this.state !== 'focus' || this.cards.length < 2) return;
      if (this.focusIdx == null) return;
      const N = this.cards.length;
      const oldIdx = this.focusIdx;
      const newIdx = (oldIdx + delta + N) % N;

      this.swapping = true;
      this._swapOldIdx = oldIdx;
      this._swapNewIdx = newIdx;
      this._swapDelta = delta;
      this._swapPhase = 'init';
      this.synopsisShown = false;
      // 切卡時把簡介捲回頂端，下一張內容才從頭顯示
      if (this._synopsisEl && this._synopsisEl.isConnected) this._synopsisEl.scrollTop = 0;
      if (this._synopsisTimer) clearTimeout(this._synopsisTimer);

      this._swipeArmed = false;
      if (this._swipeArmTimer) clearTimeout(this._swipeArmTimer);
      this._swipeArmTimer = setTimeout(() => { this._swipeArmed = true; }, SWIPE_REARM_MS);

      // 兩次 RAF 確保瀏覽器 commit init 狀態 (起始位置在邊緣) 再切到 animate (中央)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          this._swapPhase = 'animate';
          this.focusIdx = newIdx;
          // animate 結束後重置 synopsis timer
          this._synopsisTimer = setTimeout(() => {
            if (this.state === 'focus') this.synopsisShown = true;
          }, FOCUS_SYNOPSIS_DELAY_MS);
          setTimeout(() => {
            this.swapping = false;
            this._swapOldIdx = null;
            this._swapNewIdx = null;
            this._swapDelta = 0;
            this._swapPhase = null;
          }, SWAP_ANIM_MS);
        });
      });
    },

    // ===== 派生值 =====
    get ringRadius() {
      const N = this.cards.length;
      if (N <= 1) return 0;
      const cardW = this.viewportW >= 900 ? 200
                  : this.viewportW >= 600 ? 170
                  : 110;                              // 手機卡片間距收緊 (130→110)
      const r = (cardW * N) / (2 * Math.PI);
      const cap = this.viewportW * 0.42;              // 半徑 ≤ 視口寬 42%，避免 ring 兩側超出
      return Math.max(130, Math.min(r, cap));
    },

    get ringTransform() {
      return `translate(-50%, -50%) rotateX(-${RING_TILT_DEG}deg) rotateY(${this.globalRotation}deg)`;
    },

    get modeLabel() {
      if (this.mode === 'camera') return '📷 攝影機模式';
      if (this.gestureStatus === 'loading') return '⌨️ 鍵盤 (📷 載入中…)';
      if (this.gestureStatus === 'failed')  return '⌨️ 鍵盤 (📷 失敗)';
      return '⌨️ 鍵盤模式';
    },

    get focusCard() {
      return (this.focusIdx != null) ? this.cards[this.focusIdx] : null;
    },

    cardTransform(i) {
      const N = this.cards.length;
      if (N === 0) return '';
      const angle = (360 / N) * i;
      const R = this.ringRadius;
      const counter = -this.globalRotation;
      const fwd = this.viewportW >= 600 ? FOCUS_FWD_DESKTOP : FOCUS_FWD_MOBILE;
      const scl = this.viewportW >= 600 ? FOCUS_SCALE_DESKTOP : FOCUS_SCALE_MOBILE;
      const exitDist = this.viewportW >= 600 ? 700 : 480;
      const yOff = this.viewportW >= 600 ? -20 : -60;  // focus 時往上挪，讓出底部給資訊面板
      // 展開卡片 base transform（抵消 ring 的 rotateX 跟 rotateY → 正面對相機，不俯視）
      const focusBase = `rotateY(${counter}deg) rotateX(${RING_TILT_DEG}deg) translateY(${yOff}px) translateZ(${fwd}px) scale(${scl})`;

      // ---- Swap 中 ----
      if (this.swapping) {
        if (i === this._swapOldIdx) {
          if (this._swapPhase === 'init') return focusBase;
          // animate: 滑出去 (delta=-1 右撇 → 往右滑、delta=+1 左撇 → 往左滑)
          const dir = this._swapDelta === -1 ? exitDist : -exitDist;
          return `rotateY(${counter}deg) rotateX(${RING_TILT_DEG}deg) translateY(${yOff}px) translateX(${dir}px) translateZ(${fwd}px) scale(${scl})`;
        }
        if (i === this._swapNewIdx) {
          if (this._swapPhase === 'init') {
            // 起點：對側邊緣
            const dir = this._swapDelta === -1 ? -exitDist : exitDist;
            return `rotateY(${counter}deg) rotateX(${RING_TILT_DEG}deg) translateY(${yOff}px) translateX(${dir}px) translateZ(${fwd}px) scale(${scl})`;
          }
          return focusBase;
        }
        // 其他卡片留在環位置 (反正 hidden)
        return `rotateY(${angle}deg) translateZ(${R}px)`;
      }

      // ---- Focus ----
      if (this.state === 'focus' && i === this.focusIdx) return focusBase;

      // ---- Ring ----
      return `rotateY(${angle}deg) translateZ(${R}px)`;
    },

    isCardHidden(i) {
      if (this.swapping) {
        return i !== this._swapOldIdx && i !== this._swapNewIdx;
      }
      return this.state === 'focus' && this.focusIdx !== i;
    },

    isCardFocused(i) {
      if (this.swapping) return i === this._swapNewIdx;
      return this.state === 'focus' && i === this.focusIdx;
    },

    // ===== Helpers =====
    coverFor(rec) {
      const c = rec?.cover || {};
      return c.local || c.url || "";
    },

    renderStars(score) {
      if (score == null) return "—";
      return (Math.round(score * 2) / 2).toFixed(1) + "★";
    },

    cardTitle(rec) {
      return rec?.titles?.primary_zh || rec?.titles?.ja_romaji || rec?.titles?.ja || rec?.id || '';
    },

    clickCard(i) {
      if (this.state === 'ring') {
        this.focusIdx = i;
        this.state = 'focus';
        this.synopsisShown = false;
        this.rotationVelocity = 0;
        if (this._synopsisTimer) clearTimeout(this._synopsisTimer);
        this._synopsisTimer = setTimeout(() => {
          if (this.state === 'focus') this.synopsisShown = true;
        }, FOCUS_SYNOPSIS_DELAY_MS);
      } else if (this.state === 'focus' && !this.swapping) {
        this._exitFocus();
      }
    },

    exit() {
      // 清掉 ritualPool 確保下次重進 pool 重置
      try { sessionStorage.removeItem('ritualPool'); } catch (e) {}
      location.href = 'index.html';
    },

    toggleCam() { this.showCam = !this.showCam; },
  };
}
