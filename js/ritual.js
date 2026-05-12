// kiuno-anime-viewer · ritual.html Alpine app
// 3D 環狀卡片展示 + 手勢/鍵盤控制狀態機 (含慣性 + 1 指 swipe 切卡)

import { startGesture } from "./ritual-gesture.js?v=3";

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
// 在 focus 內可以觸發 swap 的手勢：除了「布」以外的識別手勢
const SWIPE_GESTURES = new Set([
  'Closed_Fist', 'Pointing_Up', 'Victory',
  'Thumb_Up', 'Thumb_Down', 'ILoveYou',
]);
const FOCUS_FWD_MOBILE = 240;
const FOCUS_FWD_DESKTOP = 320;
const FOCUS_SCALE_MOBILE = 1.6;
const FOCUS_SCALE_DESKTOP = 1.9;
const RING_TILT_DEG = 18;      // ring 的 rotateX 度數

export function ritualData() {
  return {
    // ===== 資料 =====
    cards: [],
    sourceLabel: "",
    loadError: "",
    loading: true,

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
      this.sourceLabel = ({
        season: '本季新番',
        recommend: '我的推薦',
        all: '全部動畫',
      })[src] || '';

      const ids = idsStr.split(',').map(s => s.trim()).filter(Boolean);
      if (ids.length === 0) {
        this.loadError = "沒帶 ids 參數，無法召喚";
        this.loading = false;
        return;
      }

      try {
        const resp = await fetch("data/anime.json", { cache: "no-cache" });
        if (!resp.ok) throw new Error(resp.status + " " + resp.statusText);
        const db = await resp.json();
        const byId = db.anime || {};
        this.cards = ids.map(id => byId[id]).filter(Boolean);
        if (this.cards.length === 0) {
          this.loadError = "找不到帶入的動漫資料";
          this.loading = false;
          return;
        }
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

    _onGestureFrame({ gesture, score, x }) {
      const now = performance.now();
      const rawG = (gesture && score > 0.6) ? gesture : null;
      this.lastGesture = rawG;

      // ---- 算 dx (不管手勢，都追蹤) ----
      let dx = 0;
      if (typeof x === 'number') {
        if (this._lastHandX != null) dx = x - this._lastHandX;
        this._lastHandX = x;
      } else {
        this._lastHandX = null;
      }

      // ---- 布 + 揮動：給 rotationVelocity (慣性接手) ----
      if (this.state === 'ring' && rawG === 'Open_Palm' && Math.abs(dx) > MOVE_DEADZONE) {
        this.rotationVelocity = dx * MOVE_ROT_SCALE;
      }

      // ---- 快速撥動：swap 卡片 (focus 內，除了「布」以外的手勢都算) ----
      if (this.state === 'focus' && SWIPE_GESTURES.has(rawG)
          && this._swipeArmed && Math.abs(dx) > SWIPE_DX_THRESHOLD) {
        // dx > 0 = 手往右 → 右撇 → delta = -1 (前一張 / 視覺上左邊的卡進中央)
        this._tryStartSwap(dx > 0 ? -1 : +1);
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
                  : 130;
      const r = (cardW * N) / (2 * Math.PI);
      return Math.max(160, r);
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
      // 展開卡片 base transform（抵消 ring 的 rotateX 跟 rotateY → 正面對相機，不俯視）
      const focusBase = `rotateY(${counter}deg) rotateX(${RING_TILT_DEG}deg) translateZ(${fwd}px) scale(${scl})`;

      // ---- Swap 中 ----
      if (this.swapping) {
        if (i === this._swapOldIdx) {
          if (this._swapPhase === 'init') return focusBase;
          // animate: 滑出去 (delta=-1 右撇 → 往右滑、delta=+1 左撇 → 往左滑)
          const dir = this._swapDelta === -1 ? exitDist : -exitDist;
          return `rotateY(${counter}deg) rotateX(${RING_TILT_DEG}deg) translateX(${dir}px) translateZ(${fwd}px) scale(${scl})`;
        }
        if (i === this._swapNewIdx) {
          if (this._swapPhase === 'init') {
            // 起點：對側邊緣
            const dir = this._swapDelta === -1 ? -exitDist : exitDist;
            return `rotateY(${counter}deg) rotateX(${RING_TILT_DEG}deg) translateX(${dir}px) translateZ(${fwd}px) scale(${scl})`;
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
      location.href = 'index.html';
    },

    toggleCam() { this.showCam = !this.showCam; },
  };
}
