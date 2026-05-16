// kiuno-anime-viewer · ritual.html 手勢偵測
// - 嘗試啟動 MediaPipe Tasks Vision GestureRecognizer
// - 失敗（拒絕授權 / 無攝影機 / 模型載入錯誤）→ 回傳 mode: 'keyboard'，呼叫端用鍵盤事件
// - 成功 → 每偵測 frame 呼叫 onFrame({ gesture, x, y })
//   - gesture: 'Closed_Fist' | 'Open_Palm' | 'Pointing_Up' | ... | null
//   - x: 0..1，手中央 (landmark[9]) 的 normalized x (已反轉成「使用者視角」)
//   - y: 0..1，手中央的 normalized y (0=上 1=下，未反轉，用來做石頭手勢的簡介 scroll)

const MP_BUNDLE_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";
const MP_WASM_ROOT  = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MP_MODEL_URL  = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";

/**
 * @param {Object} opts
 * @param {HTMLVideoElement} opts.video
 * @param {(payload: { gesture: string|null, score: number, x: number|null, y: number|null }) => void} opts.onFrame
 * @returns {Promise<{ mode: 'camera'|'keyboard', error?: Error, stop?: () => void }>}
 */
export async function startGesture({ video, onFrame }) {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      audio: false,
    });
  } catch (err) {
    return { mode: 'keyboard', error: err };
  }

  video.srcObject = stream;
  try { await video.play(); } catch (e) { /* autoplay 偶爾報錯，可忽略 */ }

  let mod;
  try {
    mod = await import(MP_BUNDLE_URL);
  } catch (err) {
    stopStream(stream);
    return { mode: 'keyboard', error: err };
  }
  const { GestureRecognizer, FilesetResolver } = mod;

  let rec;
  try {
    const vision = await FilesetResolver.forVisionTasks(MP_WASM_ROOT);
    rec = await GestureRecognizer.createFromOptions(vision, {
      baseOptions: { modelAssetPath: MP_MODEL_URL, delegate: "GPU" },
      runningMode: "VIDEO",
      numHands: 1,
    });
  } catch (err) {
    // GPU delegate 偶爾失敗，再用 CPU 試一次
    try {
      const vision = await FilesetResolver.forVisionTasks(MP_WASM_ROOT);
      rec = await GestureRecognizer.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MP_MODEL_URL, delegate: "CPU" },
        runningMode: "VIDEO",
        numHands: 1,
      });
    } catch (err2) {
      stopStream(stream);
      return { mode: 'keyboard', error: err2 };
    }
  }

  let stopped = false;
  let rafId = 0;
  let lastVideoTime = -1;

  const loop = () => {
    if (stopped) return;
    if (video.readyState >= 2 && video.currentTime !== lastVideoTime) {
      lastVideoTime = video.currentTime;
      try {
        const result = rec.recognizeForVideo(video, performance.now());
        const gestureCat = result.gestures?.[0]?.[0];
        const landmark = result.landmarks?.[0]?.[9]; // middle finger MCP (掌心)
        // 視訊是 mirrored（CSS scaleX(-1)），所以實際手是「使用者視角」的 x。
        // landmark.x 是相機座標 (左右相對相機而言)。我們把它做 1-x 反轉，讓「手往右」推到「環往右」。
        const x = landmark ? (1 - landmark.x) : null;
        // y 不反轉：landmark.y 0=畫面上 1=畫面下 → 手往下移 = dy > 0 = 簡介往下捲
        const y = landmark ? landmark.y : null;
        onFrame({
          gesture: gestureCat?.categoryName || null,
          score: gestureCat?.score || 0,
          x,
          y,
        });
      } catch (e) { /* 偶發 frame error，忽略 */ }
    }
    rafId = requestAnimationFrame(loop);
  };
  rafId = requestAnimationFrame(loop);

  return {
    mode: 'camera',
    stop: () => {
      stopped = true;
      if (rafId) cancelAnimationFrame(rafId);
      try { rec.close(); } catch (e) {}
      stopStream(stream);
    },
  };
}

function stopStream(stream) {
  try { stream?.getTracks().forEach(t => t.stop()); } catch (e) {}
}
