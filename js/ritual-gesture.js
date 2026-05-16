// kiuno-anime-viewer · ritual.html 手勢偵測
// - 嘗試啟動 MediaPipe Tasks Vision GestureRecognizer
// - 失敗（拒絕授權 / 無攝影機 / 模型載入錯誤）→ 回傳 mode: 'keyboard'，呼叫端用鍵盤事件
// - 成功 → 每偵測 frame 呼叫 onFrame({ gesture, score, x, y, hands })
//   既有 (backward compat，取第一隻手):
//   - gesture: 'Closed_Fist' | 'Open_Palm' | 'Pointing_Up' | ... | null
//   - score: 該手勢信心 0..1
//   - x: 0..1，手中央 (landmark[9]) 的 normalized x (已反轉成「使用者視角」)
//   - y: 0..1，手中央的 normalized y (0=上 1=下，未反轉，用來做石頭手勢的簡介 scroll)
//   新增 (雙手手勢用):
//   - hands: [{gesture, score, landmarks, handedness}, ...] 最多 2 隻手
//     - landmarks: MediaPipe 21 個 landmark，每個 {x, y, z}；x 已反轉成「使用者視角」
//     - handedness: 'Left' | 'Right' (MediaPipe 從相機角度判定，注意與使用者視角相反)

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
      numHands: 2,
    });
  } catch (err) {
    // GPU delegate 偶爾失敗，再用 CPU 試一次
    try {
      const vision = await FilesetResolver.forVisionTasks(MP_WASM_ROOT);
      rec = await GestureRecognizer.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MP_MODEL_URL, delegate: "CPU" },
        runningMode: "VIDEO",
        numHands: 2,
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

        // 視訊是 mirrored (CSS scaleX(-1))，把 landmark.x 做 1-x 反轉成「使用者視角」
        // 注意 z 不反轉
        const flipLandmarks = (lms) => lms.map(p => ({ x: 1 - p.x, y: p.y, z: p.z }));

        // 組 hands array (最多 2 隻)
        const hands = (result.landmarks || []).map((lms, i) => {
          const cat = result.gestures?.[i]?.[0];
          const hd  = result.handednesses?.[i]?.[0];
          return {
            gesture: cat?.categoryName || null,
            score:   cat?.score || 0,
            landmarks: flipLandmarks(lms),
            handedness: hd?.categoryName || null,
          };
        });

        // backward compat：取第一隻手的 gesture / x / y
        const h0 = hands[0];
        const palm = h0?.landmarks?.[9];  // middle finger MCP (掌心)

        onFrame({
          gesture: h0?.gesture || null,
          score:   h0?.score || 0,
          x: palm ? palm.x : null,
          y: palm ? palm.y : null,
          hands,
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
