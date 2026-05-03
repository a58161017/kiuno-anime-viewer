// 更新提醒：版號跟留言有變動 → nav link 顯示紅點
//   版號：跟 localStorage.kiuno.lastSeenVersion 比，不一致就標
//   留言：跟 localStorage.kiuno.lastSeenCommentTime 比，新的多就標
//
// 用法：每頁加 <script type="module" src="indicator.js?v=1"></script>
// 目標頁加 [data-mark-seen="version"] 或 [data-mark-seen="comments"] 屬性
// 讓那個頁面在 init 時把 seen 記下。

const LS_VERSION = "kiuno.lastSeenVersion";
const LS_COMMENT = "kiuno.lastSeenCommentTime";

function showDot(selector) {
  document.querySelectorAll(selector).forEach((el) => el.classList.add("has-new"));
}

async function checkVersion() {
  try {
    const r = await fetch("data/version.json", { cache: "no-cache" });
    if (!r.ok) return;
    const v = (await r.json()).current || "";
    if (!v) return;
    const seen = localStorage.getItem(LS_VERSION);
    if (seen === null) {
      // 首次造訪 → 不提醒，記下目前版本
      localStorage.setItem(LS_VERSION, v);
      return;
    }
    if (seen !== v) {
      showDot('a.nav-link-changelog');
    }
  } catch (e) {
    // 沒 version.json 不視為錯
  }
}

async function checkLatestComment() {
  try {
    // 動態載 Firebase + config
    const cfgMod = await import("./firebase-config.js?v=1");
    if (!cfgMod.isConfigured) return;
    const [{ initializeApp, getApps }, { getFirestore, collection, query: q, orderBy, limit, getDocs }] = await Promise.all([
      import("https://www.gstatic.com/firebasejs/10.13.2/firebase-app.js"),
      import("https://www.gstatic.com/firebasejs/10.13.2/firebase-firestore.js"),
    ]);
    const apps = getApps();
    const app = apps.length ? apps[0] : initializeApp(cfgMod.firebaseConfig);
    const db = getFirestore(app);
    const snap = await getDocs(q(collection(db, "recommends"), orderBy("createdAt", "desc"), limit(1)));
    if (snap.empty) return;
    const ts = snap.docs[0].data().createdAt;
    const latest = ts && ts.toMillis ? ts.toMillis() : 0;
    if (!latest) return;

    const seen = parseInt(localStorage.getItem(LS_COMMENT) || "0", 10);
    if (!seen) {
      // 首次造訪 → 記下不提醒
      localStorage.setItem(LS_COMMENT, String(latest));
      return;
    }
    if (latest > seen) {
      showDot('a.nav-link-recommends');
    }
  } catch (e) {
    // Firebase 沒設好 / 沒網路 → 跳過
  }
}

async function markSeen() {
  // 由頁面標記 [data-mark-seen]
  const flag = document.body.dataset.markSeen;
  if (flag === "version") {
    try {
      const r = await fetch("data/version.json", { cache: "no-cache" });
      if (r.ok) {
        const v = (await r.json()).current || "";
        if (v) localStorage.setItem(LS_VERSION, v);
      }
    } catch (e) {}
  }
  // comments 由 recommends.html 自己在 onSnapshot 第一筆時呼叫 markCommentsSeen()
}

window.markCommentsSeen = function (millis) {
  if (typeof millis === "number" && millis > 0) {
    localStorage.setItem(LS_COMMENT, String(millis));
  }
};

// run
markSeen();
checkVersion();
checkLatestComment();
