// kiuno-anime-viewer · 共用 utility module
// recommends.html / index.html 都會 import 這個檔
//
// - collectAudit()  : 收集訪客 IP / UA / 螢幕 / 時區 / referrer 給 audit metadata
// - showToast()     : 全站 toast 元件 (#globalToast)
// - formatTime()    : Firestore Timestamp → 「剛剛 / N 分鐘前 / yyyy/MM/dd」

export async function collectAudit() {
  let ip = null;
  try {
    const r = await fetch("https://api.ipify.org/?format=json");
    if (r.ok) {
      const d = await r.json();
      ip = d.ip || null;
    }
  } catch (e) { /* fail-soft */ }
  return {
    ip,
    user_agent: (navigator.userAgent || "").slice(0, 500),
    platform: navigator.platform || "",
    languages: (navigator.languages || []).slice(0, 5),
    screen: `${screen.width}x${screen.height}`,
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
    referrer: (document.referrer || "").slice(0, 500),
  };
}

let _toastTimer = null;
export function showToast(msg, ms = 1800) {
  const el = document.getElementById("globalToast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

export function formatTime(ts) {
  if (!ts) return "";
  try {
    const d = ts.toDate ? ts.toDate() : new Date(ts);
    const now = new Date();
    const diffSec = Math.floor((now - d) / 1000);
    if (diffSec < 60) return "剛剛";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分鐘前`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小時前`;
    if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)} 天前`;
    return d.toLocaleDateString("zh-Hant", { year: "numeric", month: "2-digit", day: "2-digit" });
  } catch (e) { return ""; }
}
