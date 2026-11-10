import { createLocalStore, createStore } from "./store.js";
import { SUPABASE } from "./config.js";
import { gradeAnswer, makeAttempt, statsByQuestion, matches, orderQuestions, summarize } from "./logic.js";
import { esc, withBase, renderQuestion, renderResult, isMulti } from "./render.js";

const cfg = window.PRACTICE_CONFIG;
const $ = (s) => document.querySelector(s);
const store = createStore(createLocalStore());
let authClient = null, authUser = null;
const cache = {};
let meta = null;
let attempts = [];
let queue = [], pos = 0, results = [], checked = false;
const state = { subjects: new Set(), exam: "", chapter: "", ranks: new Set(), scope: "all", order: "new" };

async function getJson(path, bust) {
  const url = withBase(cfg.base, path) + (bust ? `?v=${encodeURIComponent(bust)}` : "");
  const r = await fetch(url, bust ? undefined : { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} を読み込めませんでした（${r.status}）`);
  return r.json();
}
const loadSubject = (id) => (cache[id] ||= getJson(`/data/${id}.json`, meta.generated).catch((e) => { delete cache[id]; throw e; }));

// ---- 絞り込みの部品
function buildFilters() {
  $("#p-subjects").innerHTML = ["共通", "選択"].map((kind) => `<div class="sub-kind">${kind === "共通" ? "共通科目" : "選択科目"}</div><div class="chips">${
    meta.subjects.filter((s) => s.kind === kind).map((s) => `<label class="chip"><input type="checkbox" name="subject" value="${s.id}"><span>${esc(s.name)}</span></label>`).join("")}</div>`).join("");
  $("#f-exam").innerHTML = `<option value="">すべての年度・回</option>` + meta.exams.map((e) => `<option value="${e.key}">${esc(e.label)}（${esc(e.held)}）</option>`).join("");
  $("#p-ranks").innerHTML = [["S", "得点必須S"], ["A", "得点必須A"], ["B", "何とか得点B"], ["C", "余裕があれば得点C"], ["D", "失点やむなしD"]]
    .map(([r, l]) => `<label class="chip"><input type="checkbox" name="rank" value="${r}"><span>${l}</span></label>`).join("");
  fillChapters();
}
function fillChapters() {
  const subs = meta.subjects.filter((s) => !state.subjects.size || state.subjects.has(s.id));
  $("#f-chapter").innerHTML = `<option value="">すべての章</option>` + subs.map((s) => {
    const cs = meta.chapters.filter((c) => c.subject === s.id);
    return cs.length ? `<optgroup label="${esc(s.name)}">${cs.map((c) => `<option value="${c.id}">${esc(c.label)}</option>`).join("")}</optgroup>` : "";
  }).join("");
  if (![...$("#f-chapter").options].some((o) => o.value === state.chapter)) state.chapter = "";
  $("#f-chapter").value = state.chapter;
}

// ---- URL のハッシュに条件を残す（共有・ブックマーク用）
function writeHash() {
  const p = new URLSearchParams();
  if (state.subjects.size) p.set("subject", [...state.subjects].join(","));
  if (state.exam) p.set("exam", state.exam);
  if (state.chapter) p.set("chapter", state.chapter);
  if (state.ranks.size) p.set("rank", [...state.ranks].join(","));
  if (state.scope !== "all") p.set("scope", state.scope);
  if (state.order !== "new") p.set("order", state.order);
  history.replaceState(null, "", p.toString() ? "#" + p : location.pathname);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  const split = (k) => (p.get(k) || "").split(",").filter(Boolean);
  const ids = meta.subjects.map((s) => s.id);
  state.subjects = new Set(split("subject").filter((s) => ids.includes(s)));
  state.ranks = new Set(split("rank").filter((r) => meta.ranks.includes(r)));
  state.exam = meta.exams.some((e) => e.key === p.get("exam")) ? p.get("exam") : "";
  state.chapter = p.get("chapter") || "";
  state.scope = ["unsolved", "wrong"].includes(p.get("scope")) ? p.get("scope") : "all";
  state.order = ["old", "random"].includes(p.get("order")) ? p.get("order") : "new";
  document.querySelectorAll('input[name="subject"]').forEach((i) => (i.checked = state.subjects.has(i.value)));
  document.querySelectorAll('input[name="rank"]').forEach((i) => (i.checked = state.ranks.has(i.value)));
  $("#f-exam").value = state.exam;
  fillChapters();
  $("#f-scope").value = state.scope;
  $("#f-order").value = state.order;
}

// ---- 出題
const say = (html) => { $("#p-status").innerHTML = html; };

async function start() {
  if (!state.subjects.size) { say(`<span class="warn">科目を1つ以上、選んでください。</span>`); return; }
  say("読み込み中…");
  $("#p-start").disabled = true;
  let items;
  try {
    items = (await Promise.all([...state.subjects].map(loadSubject))).flat();
  } catch (e) {
    say(`<span class="warn">${esc(e.message)}。ページを再読み込みしてください。</span>`);
    $("#p-start").disabled = false;
    return;
  }
  $("#p-start").disabled = false;
  const stats = statsByQuestion(attempts);
  const subjectOrder = meta.subjects.map((s) => s.id);
  queue = orderQuestions(items.filter((q) => matches(q, state, stats)), state.order, subjectOrder);
  pos = 0; results = [];
  if (!queue.length) {
    $("#p-stage").innerHTML = `<div class="empty">条件に合う問題がありません。条件をゆるめてください。</div>`;
    say("");
    return;
  }
  say(`<strong>${queue.length}</strong> 問から始めます。`);
  show();
}

function show() {
  const q = queue[pos];
  checked = false;
  $("#p-stage").innerHTML = renderQuestion(q, { base: cfg.base, index: pos + 1, total: queue.length });
  const chk = $("#p-check");
  const onChange = () => {
    const any = document.querySelector('#p-stage input[name="choice"]:checked');
    chk.disabled = !any;
    $("#p-hint").textContent = any ? "" : "選択肢を選んでください（数字キーでも選べます）";
  };
  document.querySelectorAll('#p-stage input[name="choice"]').forEach((i) => i.addEventListener("change", onChange));
  chk.addEventListener("click", check);
  if (!q.stemHtml) { // 問題文が載せられない問題は、採点せず、次へ進める
    chk.textContent = "次の問題へ"; chk.disabled = false; chk.onclick = next; $("#p-hint").textContent = "";
  }
  $("#p-stage").scrollIntoView({ block: "start", behavior: "smooth" });
}

async function check() {
  if (checked) return next();
  const q = queue[pos];
  const sel = [...document.querySelectorAll('#p-stage input[name="choice"]:checked')].map((i) => i.value);
  if (!sel.length) return;
  checked = true;
  const ok = gradeAnswer(q, sel);
  document.querySelectorAll('#p-stage input[name="choice"]').forEach((i) => (i.disabled = true));
  const ans = q.answer[0] === "all" ? [] : q.answer.map(String);
  document.querySelectorAll("#p-stage [data-n]").forEach((el) => {
    const n = el.dataset.n, picked = sel.includes(n), right = ans.includes(n);
    if (right) { el.classList.add("p-correct"); el.querySelector("label")?.insertAdjacentHTML("beforeend", `<span class="p-mark">✓ 正答</span>`); }
    else if (picked) { el.classList.add("p-wrong"); el.querySelector("label")?.insertAdjacentHTML("beforeend", `<span class="p-mark">✗ あなたの選択</span>`); }
  });
  $("#p-result").innerHTML = renderResult(q, { base: cfg.base, ok });
  results.push({ id: q.id, ok });
  const last = pos + 1 >= queue.length;
  $("#p-check").textContent = last ? "結果を見る" : "次の問題へ";
  $("#p-hint").textContent = "";
  if (ok !== null) {
    const a = makeAttempt(q, sel, ok);
    try {
      const where = await store.add(a);
      attempts.push(a);
      await updateRecord();
      if (where === "pending") $("#p-hint").textContent = "クラウドに送れなかったので、この端末に一時的に保存しました。つながったときに、自動で送ります。";
    } catch { $("#p-hint").textContent = "この回答は、記録できませんでした（保存領域がいっぱいか、使えません）。"; }
  }
  $("#p-result").querySelector(".pverdict")?.setAttribute("tabindex", "-1");
  $("#p-result").querySelector(".pverdict")?.focus({ preventScroll: false });
}

function next() {
  pos += 1;
  if (pos >= queue.length) return finish();
  show();
}

function finish() {
  const s = summarize(results);
  $("#p-stage").innerHTML = `<div class="q pq"><h2 class="qtitle">おつかれさまでした</h2>
    <p>${s.answered} 問を解きました。${s.graded ? `正解は <strong>${s.correct}</strong> 問（${Math.round((s.correct / s.graded) * 100)}%）でした。` : ""}</p>
    <p><button type="button" class="reveal-like" id="p-again">同じ条件でもう一度</button></p>
    <p class="hint">条件（左の欄）を変えて、「この条件で始める」を押すと、別の問題を解けます。「まだ解いていない問題」「間違えた問題」だけに絞ることもできます。</p></div>`;
  $("#p-again").addEventListener("click", start);
  say("");
}

async function updateRecord() {
  const n = attempts.length;
  if (store.signedIn) {
    const pend = await store.pendingCount();
    $("#p-record").textContent = `ログイン中：${n} 件の解答を、クラウドに保存しています（別の端末でも続きから解けます）。`
      + (pend ? ` うち ${pend} 件は、まだ送れていません（この端末に保存済み。つながったときに送ります）。` : "");
  } else {
    $("#p-record").textContent = store.persistent
      ? `この端末に、${n} 件の解答を記録しています。` : `この端末では、記録を保存できません（このページを開いている間だけ覚えます）。現在 ${n} 件。`;
  }
}

// ---- ログイン（Google。Supabase Auth）。使えないときも、ログインなしで演習は続けられる。
const authMsg = (html, warn = false) => { const el = $("#p-auth-msg"); if (el) { el.innerHTML = html; el.classList.toggle("warn", warn); } };

function renderAuth() {
  const box = $("#p-auth-box");
  if (!box) return;
  if (!authClient) { box.innerHTML = ""; return; }
  if (authUser) {
    const md = authUser.user_metadata || {};
    const name = md.name || md.full_name || authUser.email || "ログイン中";
    box.innerHTML = `<span class="pauth-name">${esc(name)} でログイン中</span><button type="button" class="reset" id="p-logout">ログアウト</button>`;
    $("#p-logout").addEventListener("click", logout);
  } else {
    box.innerHTML = `<button type="button" class="reveal-like" id="p-login">Google でログイン</button>`;
    $("#p-login").addEventListener("click", login);
  }
}

async function login() {
  authMsg("Google のログイン画面に移動します…");
  const { error } = await authClient.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: location.origin + location.pathname },
  });
  if (error) authMsg(`ログインを始められませんでした（${esc(error.message)}）。ログインなしで、続けられます。`, true);
}

async function logout() {
  await authClient.auth.signOut();   // SIGNED_OUT で applySession(null) が呼ばれる
  authMsg("ログアウトしました。この端末には記録が残っていません（クラウドには残っています）。");
}

async function applySession(session) {
  const user = session?.user || null;
  if (user && authUser && user.id === authUser.id) { authUser = user; renderAuth(); return; }
  authUser = user;
  if (!user) {
    store.clearUser();
  } else {
    store.setUser(authClient, user.id);
    authMsg("記録をクラウドと照らし合わせています…");
    const r = await store.syncAfterLogin();
    if (r.error) authMsg(`クラウドに送れない記録があります（${esc(r.error.message || "通信エラー")}）。この端末に残してあります。あとで自動でやり直します。`, true);
    else authMsg(r.imported ? `この端末の ${r.imported} 件の記録を、クラウドに保存しました。` : "");
  }
  renderAuth();
  try { attempts = await store.load(); }
  catch (e) { attempts = e.fallback || []; authMsg("クラウドの記録を読み込めませんでした。この端末の分だけで続けます（つながったら、再読み込みしてください）。", true); }
  await updateRecord();
}

async function initAuth() {
  if (!SUPABASE.url || !SUPABASE.key) return;
  try {
    const { createClient } = await import("./vendor/supabase.js");
    authClient = createClient(SUPABASE.url, SUPABASE.key, { auth: { flowType: "pkce", detectSessionInUrl: true, persistSession: true, autoRefreshToken: true } });
  } catch {
    authMsg("ログイン機能を読み込めませんでした。ログインなしで、続けられます。", true);
    return;
  }
  const q = new URLSearchParams(location.search);
  if (q.get("error_description")) authMsg(`ログインできませんでした（${esc(q.get("error_description"))}）。もう一度お試しください。`, true);
  try {
    const { data } = await authClient.auth.getSession();   // 戻ってきたときの ?code= の処理も、ここで終わる
    if (q.has("code") || q.has("error")) history.replaceState(null, "", location.pathname + location.hash);
    await applySession(data.session);
  } catch (e) {
    authMsg("ログインの状態を確認できませんでした。ログインなしで、続けられます。", true);
  }
  // コールバックの中で、Supabase の関数を直接 await しない（待ち合わせの不具合を避けるため、次の周期に回す）
  authClient.auth.onAuthStateChange((event, session) => {
    if (event === "SIGNED_IN" || event === "SIGNED_OUT") setTimeout(() => applySession(session), 0);
  });
  renderAuth();
}

// ---- キーボード：数字キーで選択、Enter で答え合わせ／次へ
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const t = e.target;
  if (t.closest && t.closest("select, textarea, input[type=text]")) return;
  const stage = $("#p-stage");
  if (!stage || !stage.querySelector("#p-check")) return;
  if (/^[1-9]$/.test(e.key) && !checked) {
    const q = queue[pos]; const el = document.getElementById(`c-${e.key}`);
    if (!el || !q) return;
    el.checked = isMulti(q) ? !el.checked : true;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    e.preventDefault();
  } else if (e.key === "Enter" && t.tagName !== "BUTTON" && t.tagName !== "A") {
    const b = $("#p-check"); if (b && !b.disabled) { e.preventDefault(); b.click(); }
  }
});

// ---- 起動
(async function init() {
  try {
    meta = await getJson("/data/meta.json");
  } catch (e) {
    $("#p-stage").innerHTML = `<div class="empty">${esc(e.message)}。ページを再読み込みしてください。</div>`;
    return;
  }
  buildFilters();
  readHash();
  attempts = await store.load();
  await updateRecord();
  document.querySelectorAll('input[name="subject"], input[name="rank"]').forEach((i) => i.addEventListener("change", () => {
    const set = i.name === "subject" ? state.subjects : state.ranks;
    i.checked ? set.add(i.value) : set.delete(i.value);
    if (i.name === "subject") fillChapters();
    writeHash();
  }));
  $("#f-exam").addEventListener("change", (e) => { state.exam = e.target.value; writeHash(); });
  $("#f-chapter").addEventListener("change", (e) => { state.chapter = e.target.value; writeHash(); });
  $("#f-scope").addEventListener("change", (e) => { state.scope = e.target.value; writeHash(); });
  $("#f-order").addEventListener("change", (e) => { state.order = e.target.value; writeHash(); });
  $("#p-start").addEventListener("click", start);
  $("#p-wipe").addEventListener("click", async () => {
    const where = store.signedIn ? "クラウドに保存した" : "この端末に保存した";
    if (!confirm(`${where}解答の記録を、すべて消します。元に戻せません。よろしいですか？`)) return;
    try { await store.removeAll(); attempts = []; await updateRecord(); say("解答の記録を消しました。"); }
    catch { say(`<span class="warn">記録を消せませんでした。通信を確かめて、もう一度お試しください。</span>`); }
  });
  $("#reset").addEventListener("click", () => { history.replaceState(null, "", location.pathname); readHash(); say(""); });
  window.addEventListener("hashchange", readHash);
  $("#p-stage").innerHTML = `<div class="empty">左の欄で科目などを選んで、「この条件で始める」を押してください。</div>`;
  initAuth();   // ログインの準備は、演習の表示をじゃましないよう、あとから行う
})();
