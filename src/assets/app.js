// ---- 解説の開閉（全ページ共通）
function setOpen(article, open) {
  const btn = article.querySelector(".reveal");
  const ans = article.querySelector(".answer");
  if (!btn || !ans) return;
  btn.setAttribute("aria-expanded", String(open));
  btn.textContent = open ? "解説を閉じる" : "解説を見る";
  ans.hidden = !open;
  const answers = (btn.dataset.answer || "").split(",").filter(Boolean);
  article.querySelectorAll(".choices [data-n]").forEach((li) => {
    li.classList.toggle("correct", open && answers.includes(li.dataset.n));
  });
}
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".reveal");
  if (!btn) return;
  setOpen(btn.closest(".q"), btn.getAttribute("aria-expanded") !== "true");
});

// ---- 一覧ページ
const cfg = window.LIST_CONFIG;
if (cfg) initList(cfg);

function initList(cfg) {
  const $ = (s) => document.querySelector(s);
  const list = $("#list"), count = $("#count"), more = $("#more"), toggleAll = $("#toggle-all");
  const cache = {};
  const state = { subjects: new Set(), exam: "", chapter: "", ranks: new Set() };
  let shown = 0, current = [], allOpen = false;

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function loadSubject(id) {
    if (!cache[id]) cache[id] = fetch(u(`/data/${id}.json`)).then((r) => {
      if (!r.ok) throw new Error(`${id} のデータを読み込めませんでした（${r.status}）`);
      return r.json();
    });
    return cache[id];
  }

  // JSON内のパスは "/q/..." の形なので、公開フォルダ（/sokuteishi/）を前に付ける
  const u = (p) => cfg.base.replace(/\/$/, "") + p;

  function card(q) {
    const answer = q.answer.length
      ? `<p class="seikai">正答 <b>${q.answer[0] === "all" ? "全員正解" : q.answer.map((a) => `(${a})`).join("・")}</b></p>` : "";
    const figs = (q.figures || []).map((f) => `<figure class="fig"><img src="${u(f.src)}" alt="${esc(f.alt)}" loading="lazy"></figure>`).join("");
    const choiceList = q.columns
      ? `<div class="choice-table-wrap"><table class="choices choice-table"><thead><tr><th></th>${q.columns.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${
          q.choiceCells.map((row, i) => `<tr data-n="${i + 1}"><th scope="row" class="n">(${i + 1})</th>${row.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`
      : `<ol class="choices">${q.choices.map((c, i) => `<li data-n="${i + 1}"><span class="n">(${i + 1})</span><span>${c}</span></li>`).join("")}</ol>`;
    const body = q.stemHtml
      ? `<div class="qtext">${q.stemHtml}</div>${figs}${choiceList}`
      : `${q.summary ? `<p class="qtext">${esc(q.summary)}</p>` : ""}<p class="source">問題文と選択肢は<a href="${esc(q.sourcePdf)}" rel="noopener">公式の公表試験問題（PDF）</a>でご確認ください。</p>`;
    const notes = (q.choiceNotes || []).length
      ? `<ol class="notes">${q.choiceNotes.map((n, i) => `<li${n.isAnswer ? ' class="is-answer"' : ""}><span class="n">(${i + 1})</span><span>${n.html}</span></li>`).join("")}</ol>` : "";
    const traps = q.traps.map((t) => `<section class="trap"><h3>この問題で狙われた罠：${t.url ? `<a href="${u(t.url)}">${esc(t.name)}</a>` : esc(t.name)}</h3>${t.understandingHtml}${t.reasonHtml ? `<div class="why"><span>なぜ？</span>${t.reasonHtml}</div>` : ""}</section>`).join("");
    const books = (q.books || []).length
      ? `<div class="review">${q.books.map((b) => `<a class="book-link" href="${u(b.url)}" target="_blank" rel="noopener">参考書「${esc(b.label)}」で復習する<span class="ext" aria-label="（新しいタブで開きます）">↗</span></a>`).join("")}</div>` : "";
    return `<article class="q" id="${q.id}">
      <div class="qmeta"><span>${esc(q.examLabel)}（${esc(q.held)}）</span><span class="subj">${esc(q.subjectName)}</span>${q.rank ? `<span class="rank rank-${q.rank}">ランク${q.rank}</span>` : ""}</div>
      <h2 class="qtitle"><a href="${u(q.url)}">問${q.num}</a></h2>
      ${body}
      <div class="tags">${q.chapterLabels.map((l, i) => `<a class="tag" href="${u(`/chapter/${q.chapters[i]}/`)}">${esc(l)}</a>`).join("")}</div>
      <button type="button" class="reveal" aria-expanded="false" aria-controls="ans-${q.id}" data-answer="${q.answer.join(",")}">解説を見る</button>
      <div class="answer" id="ans-${q.id}" hidden>${answer}${q.lawNote ? `<p class="lawnote">法改正に関する注意：${esc(q.lawNote)}</p>` : ""}${q.explanationHtml}${notes}${traps}${books}</div>
      ${q.stemHtml ? `<p class="credit">出典：${esc(q.source)}</p>` : ""}
    </article>`;
  }

  function matches(q) {
    if (state.exam && q.exam !== state.exam) return false;
    if (state.chapter && !q.chapters.includes(state.chapter)) return false;
    if (state.ranks.size && !state.ranks.has(q.rank)) return false;
    return true;
  }

  function showMore() {
    const next = current.slice(shown, shown + cfg.pageSize);
    list.insertAdjacentHTML("beforeend", next.map(card).join(""));
    if (allOpen) next.forEach((q) => setOpen(document.getElementById(q.id), true));
    shown += next.length;
    more.hidden = shown >= current.length;
  }

  async function render() {
    const ids = state.subjects.size ? [...state.subjects] : cfg.subjects;
    count.textContent = "読み込み中…";
    let items;
    try {
      items = (await Promise.all(ids.map(loadSubject))).flat();
    } catch (err) {
      count.textContent = "";
      list.innerHTML = `<div class="empty">${esc(err.message)}。ページを再読み込みしてください。</div>`;
      return;
    }
    current = items.filter(matches).sort((a, b) =>
      b.exam.localeCompare(a.exam) || cfg.subjects.indexOf(a.subject) - cfg.subjects.indexOf(b.subject) || a.num - b.num);
    list.innerHTML = "";
    shown = 0;
    allOpen = false;
    toggleAll.textContent = "表示中の解説をすべて開く";
    toggleAll.hidden = !current.length;
    count.innerHTML = `<strong>${current.length}</strong> 問`;
    if (!current.length) {
      list.innerHTML = `<div class="empty">条件に合う問題がありません。章やランクの条件を外してください。</div>`;
      more.hidden = true;
      return;
    }
    showMore();
  }

  // URLに条件を保存（共有・ブックマーク用）
  function writeHash() {
    const p = new URLSearchParams();
    if (state.subjects.size) p.set("subject", [...state.subjects].join(","));
    if (state.exam) p.set("exam", state.exam);
    if (state.chapter) p.set("chapter", state.chapter);
    if (state.ranks.size) p.set("rank", [...state.ranks].join(","));
    history.replaceState(null, "", p.toString() ? "#" + p : location.pathname);
  }
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    const split = (k) => (p.get(k) || "").split(",").filter(Boolean);
    state.subjects = new Set(split("subject").filter((s) => cfg.subjects.includes(s)));
    state.ranks = new Set(split("rank"));
    state.exam = p.get("exam") || "";
    state.chapter = p.get("chapter") || "";
    document.querySelectorAll('input[name="subject"]').forEach((i) => (i.checked = state.subjects.has(i.value)));
    document.querySelectorAll('input[name="rank"]').forEach((i) => (i.checked = state.ranks.has(i.value)));
    $("#f-exam").value = [...$("#f-exam").options].some((o) => o.value === state.exam) ? state.exam : "";
    $("#f-chapter").value = [...$("#f-chapter").options].some((o) => o.value === state.chapter) ? state.chapter : "";
    state.exam = $("#f-exam").value;
    state.chapter = $("#f-chapter").value;
  }

  const update = () => { writeHash(); render(); };
  document.querySelectorAll('input[name="subject"], input[name="rank"]').forEach((i) =>
    i.addEventListener("change", () => {
      const set = i.name === "subject" ? state.subjects : state.ranks;
      i.checked ? set.add(i.value) : set.delete(i.value);
      update();
    }));
  $("#f-exam").addEventListener("change", (e) => { state.exam = e.target.value; update(); });
  $("#f-chapter").addEventListener("change", (e) => { state.chapter = e.target.value; update(); });
  $("#reset").addEventListener("click", () => { history.replaceState(null, "", location.pathname); readHash(); render(); });
  more.addEventListener("click", showMore);
  toggleAll.addEventListener("click", () => {
    allOpen = !allOpen;
    list.querySelectorAll(".q").forEach((a) => setOpen(a, allOpen));
    toggleAll.textContent = allOpen ? "表示中の解説をすべて閉じる" : "表示中の解説をすべて開く";
  });
  window.addEventListener("hashchange", () => { readHash(); render(); });

  readHash();
  render();
}
