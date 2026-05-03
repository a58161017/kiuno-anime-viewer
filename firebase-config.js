// Firebase Web SDK config — 公開 keys，commit 進 repo OK。
// 安全靠 Firestore Security Rules (見 firestore.rules)。
//
// 使用者要做的事：
// 1. 開 https://console.firebase.google.com → 建專案 (e.g. "kiuno-anime-viewer")
// 2. 啟用 Build → Firestore Database (Start in test mode)
// 3. Project Settings → General → 你的應用程式 → 加 Web App，複製 firebaseConfig 物件
// 4. 把下面的 placeholder 換成真實的 config
// 5. 把 firestore.rules 貼到 Firestore → Rules → Publish

export const firebaseConfig = {
  apiKey: "AIzaSyBeHoWrKArMVgKqnuymczLfRrczZ1VY76E",
  authDomain: "kiuno-anime-viewer.firebaseapp.com",
  projectId: "kiuno-anime-viewer",
  storageBucket: "kiuno-anime-viewer.firebasestorage.app",
  messagingSenderId: "111626651255",
  appId: "1:111626651255:web:02e88d68e9b54a88ba2872",
};

// 簡單 sanity check：未填 config 時 viewer 會顯示提示而不是直接 crash
export const isConfigured = !Object.values(firebaseConfig).some(v => v === "REPLACE_ME" || v.startsWith("REPLACE_ME"));
