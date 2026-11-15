// 演習ページの画面の動作確認（jsdom）。Supabase・Google には、つながない（偽のクライアントを差し込む）。
//
// 使い方（jsdom は、サイトの依存に入れていない。作業用のフォルダに入れて、場所を NODE_PATH で渡す）：
//   mkdir -p /tmp/jt && cd /tmp/jt && npm init -y && npm i jsdom
//   cd <リポジトリ> && npm run build
//   NODE_PATH=/tmp/jt/node_modules node tools/practice_smoke.cjs
//
// 仕組み：ビルド結果（_site/practice/index.html と _site/data/*.json）を読み、src/assets/practice/ の ES モジュールを、
// import／export を外して1本につなげ、jsdom の中で実行する。dynamic import（supabase-js）は、偽の createClient に置き換える。
// 新しい確認を足すときは、下の scenarios に、関数を1つ足す。boot() の引数で、URL のハッシュ・端末の記録・クラウドの記録・
// ログインの有無・データの書き換え（patchData）を指定できる。
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const root = path.join(__dirname, "..");
const KEY = "sokuteishi.practice.v1";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const day = (d) => new Date(Date.now() - d * 86400000).toISOString();
const loadJson = (rel) => JSON.parse(fs.readFileSync(path.join(root, "_site", rel), "utf8"));

async function boot({ hash = "", local = [], cloud = null, signedIn = false, patchData = null, rpcFails = false } = {}) {
  const html = fs.readFileSync(path.join(root, "_site/practice/index.html"), "utf8").replace(/<script type="module"[^>]*><\/script>/, "");
  const strip = (f) => fs.readFileSync(path.join(root, "src/assets/practice", f), "utf8").replace(/^import [^;]*;\s*$/gm, "").replace(/^export /gm, "");
  const code = ["logic.js", "config.js", "cloud.js", "store.js", "render.js", "practice.js"].map(strip).join("\n")
    .replace('await import("./vendor/supabase.js")', "({createClient:window.__fakeCreate})");
  const dom = new JSDOM(html, { url: "https://aoi-s-office.jp/sokuteishi/practice/" + hash, runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window;
  w.fetch = async (u) => {
    const p = String(u).replace(/^.*\/sokuteishi/, "").split("?")[0];
    try {
      const d = JSON.parse(fs.readFileSync(path.join(root, "_site", p), "utf8"));
      if (patchData) patchData(p, d);
      return { ok: true, status: 200, json: async () => d };
    } catch { return { ok: false, status: 404 }; }
  };
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.confirm = () => true;
  if (!w.crypto.randomUUID) w.crypto.randomUUID = () => require("crypto").randomUUID();
  const rows = cloud || [];
  const log = { rpc: [], signOut: null, oauth: null };
  let listener = null, on = signedIn;
  const session = () => (on ? { user: { id: "u1", email: "x@example.com", user_metadata: { name: "テスト太郎" } } } : null);
  w.__fakeCreate = () => ({
    rpc: async (name) => { log.rpc.push(name); if (rpcFails) return { error: { message: "function not found" } }; rows.length = 0; return { error: null }; },
    auth: {
      getSession: async () => ({ data: { session: session() } }),
      onAuthStateChange: (cb) => { listener = cb; return { data: { subscription: {} } }; },
      signOut: async (o) => { log.signOut = o || {}; on = false; listener && listener("SIGNED_OUT", null); },
      signInWithOAuth: async (a) => { log.oauth = a; return { error: null }; },
    },
    from: () => ({
      select: () => ({ order() { return this; }, range: (a, b) => Promise.resolve({ data: rows.slice(a, b + 1), error: null }) }),
      upsert: (l) => { for (const r of l) if (!rows.some((x) => x.id === r.id)) rows.push(r); return Promise.resolve({ error: null }); },
      delete: () => ({
        not: () => { rows.length = 0; return Promise.resolve({ error: null }); },
        in: (c, ids) => { for (const id of ids) { const i = rows.findIndex((r) => r.id === id); if (i >= 0) rows.splice(i, 1); } return Promise.resolve({ error: null }); },
      }),
    }),
  });
  w.PRACTICE_CONFIG = { base: "/sokuteishi/", contact: "https://forms.example/x" };
  w.localStorage.setItem(KEY, JSON.stringify(local));
  w.eval(code);
  await sleep(600);
  const $ = (s) => w.document.querySelector(s);
  const $$ = (s) => [...w.document.querySelectorAll(s)];
  const text = (s) => { const e = $(s); return e ? e.textContent.replace(/\s+/g, " ").trim() : ""; };
  const change = (el) => el.dispatchEvent(new w.Event("change", { bubbles: true }));
  const key = (k) => w.document.dispatchEvent(new w.KeyboardEvent("keydown", { key: k, bubbles: true }));
  const stored = () => JSON.parse(w.localStorage.getItem(KEY) || "[]");
  return { w, $, $$, text, change, key, rows, log, stored };
}

let fail = 0;
const ok = (cond, msg) => { console.log((cond ? "  ✓ " : "  ✗ ") + msg); if (!cond) fail++; };
const A = (qid, okv, d, x = {}) => ({ id: `${qid}-${d}-${x.choice_n || 0}`, question_id: qid, choice_n: null, mode: "exam", selected: "1", is_correct: okv, answered_at: day(d), ...x });

const scenarios = {
  async "五肢択一：絞り込み→解答→記録"() {
    const exam = loadJson("data/meta.json").exams[0].key;
    const p = await boot({ hash: `#subject=hourei&exam=${exam}` });
    p.$("#p-start").click(); await sleep(500);
    ok(/問から始めます/.test(p.text("#p-status")), "始められる：" + p.text("#p-status"));
    const first = p.$('#p-stage input[name=choice]'); first.checked = true; p.change(first);
    p.$("#p-check").click(); await sleep(100);
    ok(!!p.$(".pverdict") && p.stored().length === 1 && p.stored()[0].mode === "exam", "答え合わせ→端末に1件（mode=exam）");
    ok(p.$$("#p-result a").every((a) => a.target === "_blank"), "結果のリンクは、すべて新しいタブ");
  },
  async "復習：間違えた→日がたった→未解答の順"() {
    const qs = loadJson("data/hourei.json"); const exam = qs[0].exam; const ids = qs.filter((q) => q.exam === exam).map((q) => q.id);
    const p = await boot({ hash: `#tab=review&subject=hourei&exam=${exam}`, local: [A(ids[0], false, 2), A(ids[1], true, 40), A(ids[2], true, 0.01)] });
    p.$("#f-size").value = "5"; p.$("#p-start").click(); await sleep(500);
    ok(/1 問（直近で間違えた）・1 問（日がたった）/.test(p.text("#p-status")), p.text("#p-status"));
    ok(p.$(".pq").dataset.id === ids[0], "最初に、間違えた問題が出る");
  },
  async "一問一答：ふつうの問と、語句だけの問（drill.phrase）"() {
    const qs = loadJson("data/hourei.json").filter((q) => q.drill && q.answer.length === 1);
    const normal = qs.find((q) => !q.drill.phrase), phrase = qs.find((q) => q.drill.phrase) || qs.find((q) => q.id !== normal.id && q.exam === normal.exam);
    const exam = normal.exam, target = qs.find((q) => q.exam === exam && q.id !== normal.id) || phrase;
    // target を、語句だけの問として扱わせる（データに phrase がない版でも、確かめられるように）
    const patch = (pth, d) => { if (pth.endsWith("hourei.json")) { const q = d.find((x) => x.id === target.id); q.drill.phrase = true; q.drill.items.forEach((it) => { it.isAnswer = q.answer.map(String).includes(String(it.n)); }); } };
    const ansN = Number(target.answer[0]);
    const p = await boot({ hash: `#tab=drill&subject=hourei&exam=${exam}`, patchData: patch,
      local: [A(target.id, false, 3, { choice_n: ansN, mode: "drill", selected: "false" }), A(normal.id, false, 2, { choice_n: normal.drill.items[0].n, mode: "drill", selected: "true" })] });
    p.$("#f-size").value = "5"; p.$("#p-start").click(); await sleep(500);
    for (let i = 0; i < 2; i++) {
      const art = p.$(".pdrill"), isPhrase = art.classList.contains("pdrill-phrase");
      ok(!/論点：/.test(p.text("#p-stage")), `${art.dataset.id}#${art.dataset.n}：答える前に、論点を出さない`);
      if (isPhrase) {
        ok(!!p.$(".pstem-open") && !p.$("details.pstem") && /正答（これが答え）/.test(p.text(".pjudge")), "語句の問：問題文が開いていて、ボタンは「正答／正答ではない」");
        p.key("1"); await sleep(80);
        ok(/✓ 正解です/.test(p.text(".pverdict")), "語句の問：正答の選択肢に「正答」→正解（isAnswer で判定）");
      } else {
        ok(!!p.$("details.pstem") && /正しい（1）/.test(p.text(".pjudge")), "ふつうの問：問題文は折りたたみ、ボタンは「正しい／誤り」");
        p.key("1"); await sleep(80);
        ok(!!p.$(".pverdict"), "ふつうの問：答えられる");
      }
      ok(/論点：/.test(p.text("#p-result")), "答えたあとに、論点が出る");
      p.$("#p-next").click(); await sleep(80);
    }
    ok(p.stored().slice(2).every((r) => r.mode === "drill" && Number.isInteger(r.choice_n)), "記録は mode=drill・選択肢番号つき");
  },
  async "成績：五肢択一／一問一答の切り替え"() {
    const qs = loadJson("data/hourei.json"); const dq = qs.filter((q) => q.drill).slice(0, 4);
    const local = [A(qs[0].id, true, 1), A(qs[1].id, false, 1), ...dq.flatMap((q) => q.drill.items.map((it) => A(q.id, true, 1, { choice_n: it.n, mode: "drill", selected: "true" })))];
    const p = await boot({ hash: "#tab=stats", local });
    await sleep(300);
    ok(/解いた問題 2 \//.test(p.text(".pstats")), "五肢択一：解いた問題 2");
    p.$$(".pview button").find((b) => b.dataset.view === "drill").click(); await sleep(500);
    ok(/解いた選択肢/.test(p.text(".pstats")) && /view=drill/.test(p.w.location.hash), "一問一答に切り替わる（ハッシュに残る）");
  },
  async "ログイン：取り込み・間引き・差し替え前の記録の除外・アカウント削除"() {
    const qs = loadJson("data/hourei.json"); const q0 = qs.find((q) => !q.id.startsWith("2023-02-"));
    const cloud = Array.from({ length: 10 }, (_, i) => ({ ...A(q0.id, false, 30 - i), id: "old" + i }));
    cloud.push({ ...A("2023-02-hourei-01", true, 0), id: "inv", answered_at: "2026-11-10T03:00:00+00:00" });
    const p = await boot({ hash: `#subject=hourei&exam=${q0.exam}`, signedIn: true, cloud, local: [A(qs[5].id, true, 1)] });
    ok(/でログイン中/.test(p.text("#p-auth-box")) && p.stored().length === 0, "ログイン中の表示。端末の記録は、クラウドへ取り込まれて空に");
    ok(!p.rows.some((r) => r.id === "inv") && /成績と復習から外しました/.test(p.text("#p-record")), "差し替え前（2023-02 共通科目）の記録を外して、案内を出す");
    p.$("#p-start").click(); await sleep(500);
    let guard = 0; while (p.$(".pq") && p.$(".pq").dataset.id !== q0.id && guard++ < 25) { const f = p.$('#p-stage input[name=choice]'); f.checked = true; p.change(f); p.$("#p-check").click(); await sleep(40); p.$("#p-check").click(); await sleep(40); }
    const f = p.$('#p-stage input[name=choice]'); f.checked = true; p.change(f); p.$("#p-check").click(); await sleep(150);
    ok(p.rows.filter((r) => r.question_id === q0.id).length === 10 && !p.rows.some((r) => r.id === "old0"), "同じ問題の11件目で、いちばん古い記録が消える（10件のまま）");
    p.$("#p-delacc").click(); await sleep(200);
    ok(p.log.rpc.includes("delete_my_account") && /Google でログイン/.test(p.text("#p-auth-box")), "アカウント削除：関数を呼び、ログイン前の表示に戻る");
  },
};

(async () => {
  if (!fs.existsSync(path.join(root, "_site/practice/index.html"))) { console.log("先に npm run build を実行する"); process.exit(1); }
  const only = process.argv[2];
  for (const [name, fn] of Object.entries(scenarios)) {
    if (only && !name.includes(only)) continue;
    console.log("■ " + name);
    try { await fn(); } catch (e) { console.log("  ✗ 例外：" + (e && e.stack ? e.stack.split("\n").slice(0, 3).join(" / ") : e)); fail++; }
  }
  console.log(fail ? `✗ ${fail} 件の失敗` : "✓ すべて成功");
  process.exit(fail ? 1 : 0);
})();
