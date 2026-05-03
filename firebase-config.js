// Firebase Web SDK config — 真實值由 GitHub Actions 從 secrets 注入 (見 .github/workflows/deploy.yml)
// 本地端開發要測 Firebase 留言功能：手動把實值填進去（不要 commit）。
// Pages 部署版會用 Actions 生成的版本，這個檔案的 placeholder 不會出現在線上。
//
// 如何設定 GitHub Secrets：
// 1. https://github.com/<你>/kiuno-anime-viewer/settings/secrets/actions
// 2. 點 "New repository secret" 加 6 個 secrets：
//    - FIREBASE_API_KEY
//    - FIREBASE_AUTH_DOMAIN
//    - FIREBASE_PROJECT_ID
//    - FIREBASE_STORAGE_BUCKET
//    - FIREBASE_MESSAGING_SENDER_ID
//    - FIREBASE_APP_ID
// 3. Settings → Pages → Source 改成 "GitHub Actions"

export const firebaseConfig = {
  apiKey: "REPLACE_ME",
  authDomain: "REPLACE_ME.firebaseapp.com",
  projectId: "REPLACE_ME",
  storageBucket: "REPLACE_ME.firebasestorage.app",
  messagingSenderId: "REPLACE_ME",
  appId: "REPLACE_ME",
};

export const isConfigured = !Object.values(firebaseConfig).some(
  (v) => !v || v === "REPLACE_ME" || (typeof v === "string" && v.startsWith("REPLACE_ME"))
);
