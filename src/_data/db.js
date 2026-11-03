// data/ のYAMLを読み込み、ページ生成に使う形に整える。
// 整合性のチェックもここで行い、問題があればビルドを止める。
import katex from "katex";
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import MarkdownIt from "markdown-it";
import site from "./site.js";

const ROOT = path.join(process.cwd(), "data");
const md = new MarkdownIt({ html: true, breaks: true });
const load = (p) => yaml.load(fs.readFileSync(p, "utf8"));
// 「に**コック（活栓）**が」のように、太字の記号が括弧や句読点に接していると markdown-it が太字にしないので、先に <strong> に直す
const bold = (s) => String(s).replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>");
// $…$ の LaTeX を、ビルド時に KaTeX で HTML にする。markdown-it に壊されないよう、いったん目印に置き換えてから戻す
function withMath(s, fn) {
  const store = [];
  const t = String(s).replace(/\$([^$]+)\$/g, (m, tex) => {
    let html;
    try { html = katex.renderToString(tex.replace(/\\frac/g, "\\dfrac"), { throwOnError: true, output: "htmlAndMathml" }); }
    catch (e) { throw new Error(`LaTeX を変換できません: ${tex}（${e.message}）`); }
    store.push(html);
    return `\uE000${store.length - 1}\uE001`;
  });
  return fn(t).replace(/\uE000(\d+)\uE001/g, (m, i) => store[Number(i)]);
}
const render = (s) => (s ? withMath(bold(s), (t) => md.render(t)) : "");
const renderInline = (s) => (s ? withMath(bold(s), (t) => md.renderInline(t)) : "");
// 検索や構造化データ用の、LaTeX の記号を除いた文字列
const plainTex = (s) => String(s).replace(/\$([^$]+)\$/g, (m, t) => t.replace(/\\[a-zA-Z]+/g, "").replace(/[{}]/g, ""));
const errors = [];

const subjects = load(path.join(ROOT, "master/subjects.yaml"));
const book = load(path.join(ROOT, "master/book.yaml"));
const principleFile = path.join(ROOT, "master/principles.yaml");
const principleMaster = fs.existsSync(principleFile) ? load(principleFile).principles : [];
const subjectById = Object.fromEntries(subjects.map((s) => [s.id, s]));
const partById = Object.fromEntries(book.parts.map((p) => [p.id, p]));
const chapterById = Object.fromEntries(book.chapters.map((c) => [c.id, c]));
const trapById = Object.fromEntries(book.traps.map((t) => [t.id, t]));

// 実施年月（2025-02）→ 年度・回・表示ラベル
function examInfo(key) {
  const [y, m] = key.split("-").map(Number);
  const fy = m <= 3 ? y - 1 : y;
  const round = m <= 3 ? 2 : 1;
  // 2019年度から令和（2019年度＝令和元年度）、それより前は平成
  const era = fy >= 2019 ? "令和" : "平成";
  const n = fy >= 2019 ? fy - 2018 : fy - 1988;
  return {
    key, fy, round,
    label: `${era}${n === 1 ? "元" : n}年度 第${round}回`,
    held: `${y}年${m}月実施`,
  };
}
const chapterLabel = (c) => (c.num ? `${c.num} ${c.name}` : c.name);

// ---- 参考書の本文（book/<章ID>.md）
const BOOK_DIR = path.join(process.cwd(), "book");
function renderBook(mdText) {
  let n = 0;
  const toc = [];
  const html = md.render(mdText).replace(/<h([23])>(.*?)<\/h\1>/g, (m, lv, inner) => {
    const id = `s${++n}`;
    if (lv === "2") toc.push({ id, title: inner.replace(/<[^>]+>/g, "") });
    return `<h${lv} id="${id}">${inner}</h${lv}>`;
  });
  return { html, toc };
}

// ---- 章・ひっかけパターン
const chapters = book.chapters.map((c) => ({
  ...c,
  label: chapterLabel(c),
  partName: partById[c.part]?.name,
  partNum: partById[c.part]?.num,
  descriptionHtml: render(c.description),
  url: `/chapter/${c.id}/`,
  traps: [],
  questions: [],
  ...(() => {
    const f = path.join(BOOK_DIR, `${c.id}.md`);
    if (!fs.existsSync(f)) return { bookUrl: null };
    const { html, toc } = renderBook(fs.readFileSync(f, "utf8"));
    return { bookUrl: `/book/${c.id}/`, bookHtml: html, bookToc: toc };
  })(),
}));
const chapterOut = Object.fromEntries(chapters.map((c) => [c.id, c]));

const traps = book.traps.map((t) => {
  if (!chapterById[t.chapter]) errors.push(`ひっかけパターン ${t.id}: 章 ${t.chapter} がない`);
  if (t.foundation && !chapterById[t.foundation]) errors.push(`ひっかけパターン ${t.id}: 章 ${t.foundation} がない`);
  return {
    ...t,
    // 「その他（単発）」は寄せ集めなので、独立したページを作らない
    misc: t.name.includes("その他"),
    // 「その他（単発）」と、非公開にした（hidden: true）ひっかけパターンはページを作らない
    url: t.name.includes("その他") || t.hidden ? null : `/trap/${t.id}/`,
    chapterLabel: chapterById[t.chapter] ? chapterLabel(chapterById[t.chapter]) : "",
    chapterUrl: `/chapter/${t.chapter}/`,
    subjectName: subjectById[t.subject]?.name,
    understandingHtml: render(t.understanding),
    reasonHtml: render(t.reason),
    questions: [],
  };
});
const trapOut = Object.fromEntries(traps.map((t) => [t.id, t]));

// ---- 問題
const RANK_ORDER = { S: 0, A: 1, B: 2, C: 3 };

// 出題頻度（tools/compute_freq.py の結果）を、表示用の文に直す
const LEVELS = {
  S: { code: "S", label: "得点必須S", head: "この問題は、試験本番では得点しなければならない問題です（学習の優先度：最高）。" },
  A: { code: "A", label: "得点必須A", head: "この問題は、試験本番では得点しなければならない問題です（学習の優先度：高）。" },
  B: { code: "B", label: "何とか得点B", head: "この問題は、何とか得点したい問題です（学習の優先度：中）。" },
  C: { code: "C", label: "余裕があれば得点C", head: "この問題は、余裕があれば得点したい問題です（学習の優先度：低。過去に1回だけ出題）。" },
  D: { code: "D", label: "失点やむなしD", head: "この問題は、失点しても仕方がない問題です（初見）。" },
};
const WHY = {
  ans_hi: "下記の通り、ひっかけパターンである選択肢（正答）から、容易に正答を割り出すことができるからです。",
  ans_b: "下記の通り、正答の選択肢が、過去に複数回出題されており、押さえておけば、正答を割り出せるからです。",
  elim_all: "下記の通り、頻出のおとりパターンである選択肢をすべて除外して、正答を割り出すことができるからです。",
  elim_two: "下記の通り、頻出のおとりパターンである選択肢を除外して、残り2つまで絞り込めるからです。2択になるので、2回に1回は得点できます。",
  trend_S: "下記の通り、正答の選択肢の論点は、直近の回に集中して出題されています（トレンド）。通算の回数以上に、次も出やすいので、最優先で押さえるべきだからです。",
  trend_A: "下記の通り、正答の選択肢の論点は、通算の回数は少なめですが、直近の回に集中して出題されています（トレンド）。押さえておけば、得点できるからです。",
  seen: "正答の選択肢の論点は、過去に1回だけ出題されています。頻出ではありませんが、既出なので、余裕があれば押さえておくと得点できるからです。",
  subst: "",
  near: "正答の選択肢と似た記述が、別の回に出題されており、その記述は正しい内容でした（数値や範囲などを変えたものが、おとりになっています）。その正しい内容を覚えていれば、おとりと見分けられるので、余裕があれば押さえておくと得点できるからです。",
    none: "いずれも初見の選択肢であり、問題のテーマとしても頻出テーマではないからです。",
};
const TAGS = { ans_subst: "正答（物質の表で解ける）", ans_seen: "正答（過去に1回出題）", ans_near: "正答（似た記述が既出）", ans_trend: "正答（直近のトレンド）", ans_pr: "正答（原理から解ける）", ans_pat: "正答（ひっかけパターンに該当）", ans_hi: "正答（出題頻度が高い）", ans_b: "正答（過去に複数回出題）", ans_new: "正答（初見）", odo: "頻出のおとり", new: "初見", "": "" };
function freqOut(f, answers = []) {
  if (!f || !f.denom) return null;
  const pct = (m) => Math.round((m / f.denom) * 100);
  const text = (m) => `全${f.denom}回中${m}回出題（出題確率${pct(m)}％）`;
  const lv = LEVELS[f.level] || null;
  let reason = "";
  const pt = f.pat ? trapById[f.pat] : null;
  const ai = Number.isInteger(answers[0]) ? answers[0] - 1 : -1;
  const ptName = ai >= 0 && f.pnames ? f.pnames[ai] : "";
  const ptCount = ai >= 0 && f.pcounts ? f.pcounts[ai] : 0;
  const prName = ai >= 0 && f.prnames ? f.prnames[ai] : "";
  const prCount = ai >= 0 && f.prcounts ? f.prcounts[ai] : 0;
  const prId = ai >= 0 && f.principles ? f.principles[ai] : "";
  if (f.why === "subst") reason = `下記の通り、物質別の暗記リスト（ガイドブックの物質別各論の表）の物質「${f.subst_name}」から、解けるからです。過去の出題が少なくても、表を押さえておけば、得点できます。`;
  else if (prName && /^pr_[SAB]$/.test(f.why || "")) reason = ptCount >= 2
    ? `下記の通り、原理「${prName}」（過去${f.denom}回中${prCount}回出題）を理解していれば、論点そのものを暗記していなくても、解けるからです。`
    : `初見の選択肢ですが、原理「${prName}」（過去${f.denom}回中${prCount}回出題）を理解していれば、解けます。`;
  else if (ptName && (f.why === "pt_S" || f.why === "pt_A")) reason = `下記の通り、論点「${ptName}」（過去${f.denom}回中${ptCount}回出題）に当てはまる選択肢から、容易に正答を割り出すことができるからです。`;
  else if (ptName && f.why === "pt_B") reason = `下記の通り、論点「${ptName}」（過去${f.denom}回中${ptCount}回出題）に当てはまる選択肢であり、押さえておけば、何とか正答を割り出せるからです。`;
  else if (pt && (f.why === "pat_S" || f.why === "pat_A")) reason = `下記の通り、ひっかけパターン「${pt.name}」（過去${f.denom}回中${pt.count}回出題）に当てはまる選択肢から、容易に正答を割り出すことができるからです。`;
  else if (pt && f.why === "pat_B") reason = `下記の通り、ひっかけパターン「${pt.name}」（過去${f.denom}回中${pt.count}回出題）に当てはまる選択肢であり、押さえておけば、何とか正答を割り出せるからです。`;
  else if (f.kind === "choice") reason = WHY[f.why] || "";
  else if (f.why === "q_hi") reason = `この形式の問題（${f.form}）は、全${f.denom}回中${f.count}回出題されており、解き方を押さえれば、確実に得点できるからです。`;
  else if (f.why === "q_b") reason = `この形式の問題（${f.form}）は、全${f.denom}回中${f.count}回出題されており、解き方を押さえれば、何とか得点できるからです。`;
  else reason = f.why === "q_seen" ? `この形式の問題（${f.form}）は、過去に1回出題されています。余裕があれば、解き方を押さえておくと得点できるからです。` : `この形式の問題（${f.form}）は、過去の出題がなく、初見です。`;
  const METHOD = (w) => /^pr_/.test(w) ? "原理で解く" : /^elim_/.test(w) ? "消去法で解く" : /^trend_/.test(w) ? "トレンド" : (w === "subst") ? "物質の表で解く" : (w === "near") ? "似た記述で解く" : (w === "none" || w === "q_new") ? "初見" : "暗記で解く";
  const level = lv ? { code: lv.code, label: lv.label, head: lv.head, reason, method: METHOD(f.why || "") } : null;
  if (f.kind === "choice") {
    // 頻度は、論点の出題回数（論点がない選択肢は、同じ記述の回数）。「同じ記述」の回数は、参考として添える
    const eff = (i) => (f.pcounts && f.pcounts[i]) || f.counts[i];
    return { kind: "choice", denom: f.denom, level, subst: f.subst_id ? { id: f.subst_id, name: f.subst_name, url: `/substance/${f.subst_id}/` } : null, principle: prId ? { id: prId, name: prName, count: prCount, url: `/principle/${prId}/` } : null, recentLabel: (f.recent_exams && f.recent_exams.length) ? `直近${f.recent_exams.length}回（${examInfo(f.recent_exams[0]).label.replace(" ", "")}〜${examInfo(f.recent_exams[f.recent_exams.length - 1]).label.replace(" ", "")}）` : "", items: f.counts.map((same, i) => ({
      truth: f.truths[i] === "正" ? "正しい記述" : "誤った記述", m: eff(i), pct: pct(eff(i)), text: text(eff(i)), hi: pct(eff(i)) >= 30,
      tag: TAGS[(f.tags || [])[i] || ""] || "", tagCode: (f.tags || [])[i] || "",
      recentText: (f.trend && f.recent_exams) ? `直近${f.recent_exams.length}回中${f.trend[i]}回` : "",
      trending: !!(f.trend && f.recent_exams && eff(i) >= 2 && f.trend[i] * 2 >= eff(i)),
      prText: (f.prnames && f.prnames[i]) ? `原理「${f.prnames[i]}」：全${f.denom}回中${f.prcounts[i]}回出題` : "", prUrl: (f.principles && f.principles[i]) ? `/principle/${f.principles[i]}/` : "",
      simText: (f.pcounts && f.pcounts[i] && same !== f.pcounts[i]) ? `同じ記述の出題：${same}回` : "" })) };
  }
  return { kind: "question", denom: f.denom, level, subst: f.subst_id ? { id: f.subst_id, name: f.subst_name, url: `/substance/${f.subst_id}/` } : null, items: [{ truth: `この形式の問題（${f.form}）`, m: f.count, pct: pct(f.count), text: text(f.count), hi: pct(f.count) >= 30, tag: "", tagCode: "", simText: "" }] };
}

const questions = [];
const examsDir = path.join(ROOT, "exams");
for (const exam of fs.readdirSync(examsDir).sort()) {
  for (const file of fs.readdirSync(path.join(examsDir, exam)).filter((f) => f.endsWith(".yaml"))) {
    const where = `exams/${exam}/${file}`;
    const doc = load(path.join(examsDir, exam, file));
    if (doc.exam !== exam) errors.push(`${where}: exam が ${doc.exam}（フォルダ名と不一致）`);
    if (!subjectById[doc.subject]) errors.push(`${where}: 科目 ${doc.subject} がない`);
    const seen = new Set();
    for (const q of doc.questions) {
      if (seen.has(q.num)) errors.push(`${where}: 問${q.num} が重複`);
      seen.add(q.num);
      for (const c of q.chapters || []) if (!chapterById[c]) errors.push(`${where} 問${q.num}: 章 ${c} がない`);
      for (const t of q.traps || []) if (!trapById[t]) errors.push(`${where} 問${q.num}: ひっかけパターン ${t} がない`);
      const answers = q.answer == null ? [] : Array.isArray(q.answer) ? q.answer : [q.answer];
      if (q.choices?.length)
        for (const a of answers)
          if (a !== "all" && !(a >= 1 && a <= q.choices.length)) errors.push(`${where} 問${q.num}: 正答 ${a} が選択肢の範囲外`);
      if (q.status === "published") {
        // 解説がなくても、問題と正答だけで公開してよい（解説欄には、解説のかわりに出題頻度などだけが出る）
        if (site.showStem && (!q.stem || !(q.choices || []).length || !answers.length))
          errors.push(`${where} 問${q.num}: published なのに問題文・選択肢・正答のどれかがない`);
      }
      if (q.columns && (q.choices || []).some((c) => String(c).split(/\s*／\s*/).length !== q.columns.length))
        errors.push(`${where} 問${q.num}: 組合せの列の数が見出し（${q.columns.join(" ")}）と合わない選択肢がある`);
      if ((q.choice_notes || []).length && q.choices?.length && q.choice_notes.length !== q.choices.length)
        errors.push(`${where} 問${q.num}: choice_notes の数が選択肢の数と違う`);

      const published = q.status === "published";
      if (!published && !site.showDrafts) continue;

      const qTraps = (q.traps || []).map((id) => trapById[id]).filter(Boolean);
      const freqInfo = freqOut(q.freq, answers);
      const rank = freqInfo?.level?.code || null;   // 問題のランク＝出題頻度から決めた区分（S：得点必須／B：何とか得点／C：失点やむなし）
      const id = `${exam}-${doc.subject}-${String(q.num).padStart(2, "0")}`;
      questions.push({
        id,
        url: `/q/${id}/`,
        exam: examInfo(exam),
        subject: doc.subject,
        subjectName: subjectById[doc.subject]?.name,
        num: q.num,
        published,
        rank,
        rankLabel: freqInfo?.level?.label || null,
        method: freqInfo?.level?.method || null,
        chapters: (q.chapters || []).map((c) => ({ id: c, label: chapterLabel(chapterById[c]), url: `/chapter/${c}/` })),
        // 参考書のページがある章（主な章が先）
        books: (q.chapters || []).filter((c) => fs.existsSync(path.join(BOOK_DIR, `${c}.md`)))
          .map((c) => ({ label: chapterLabel(chapterById[c]), url: `/book/${c}/` })),
        traps: qTraps.map((t) => trapOut[t.id]),
        summary: q.summary || null,
        _text: [q.stem, ...(q.choices || [])].join(" "),   // 物質などの照合用（サイトには出さない）
        stemHtml: site.showStem ? render(q.stem) : "",
        stemPlain: site.showStem ? plainTex(q.stem || "").replace(/\s+/g, " ").trim() : "",
        choices: site.showStem ? (q.choices || []).map(renderInline) : [],
        choicesPlain: site.showStem ? (q.choices || []).map((c) => plainTex(c)) : [],
        // 組合せ問題：見出し（Ⓐ Ⓑ など）と、選択肢を列ごとに分けたもの
        columns: site.showStem && q.columns ? q.columns : null,
        choiceCells: site.showStem && q.columns
          ? (q.choices || []).map((c) => String(c).split(/\s*／\s*/).map(renderInline)) : null,
        answer: answers,
        choiceNotes: site.showStem ? (q.choice_notes || []).map((n, i) => ({ html: renderInline(n), isAnswer: answers.includes(i + 1) })) : [],
        source: `${site.sourceName}（${examInfo(exam).label}・${examInfo(exam).held}）`,
        explanationHtml: render(q.explanation),
        hasExplanation: !!(q.explanation && String(q.explanation).trim()),
        // figures: [{file: "2024-08-design-07.png", alt: "…"}]（src/assets/figures/ に置く）
        figures: (q.figures || []).map((f) => (typeof f === "string" ? { file: f, alt: "" } : f))
          .map((f) => ({ src: `/assets/figures/${f.file}`, alt: f.alt || "" })),
        lawNote: q.law_note || null,
        examNote: q.exam_note || null, // 協会による正答の注記（複数正答など）
        textNote: q.text_note || null, // 原本の印字（誤植など）をそのまま掲載している箇所の注記
        reviewNote: q.review_note || null, // 管理者が確認中の点（確認が済んだら消す）
        freq: freqInfo,
        minorNote: q.minor_note || null, // 細かい論点（試験対策としては深追い不要。根拠の確認は後回し）
        sourcePdf: doc.source_pdf || site.officialIndex,
      });
    }
  }
}

if (errors.length) throw new Error("データの不整合があります:\n  " + errors.join("\n  "));

// 並び順：新しい回 → 科目 → 問番号
const subjOrder = Object.fromEntries(subjects.map((s, i) => [s.id, i]));
questions.sort(
  (a, b) => b.exam.key.localeCompare(a.exam.key) || subjOrder[a.subject] - subjOrder[b.subject] || a.num - b.num
);

// 同じ回・科目の中での前後の問題
const groups = {};
for (const q of questions) (groups[`${q.exam.key}-${q.subject}`] ||= []).push(q);
for (const g of Object.values(groups)) {
  g.sort((a, b) => a.num - b.num);
  g.forEach((q, i) => {
    q.prev = g[i - 1] ? { url: g[i - 1].url, num: g[i - 1].num } : null;
    q.next = g[i + 1] ? { url: g[i + 1].url, num: g[i + 1].num } : null;
  });
}

// 問題ページの構造化データ（schema.org Quiz）
for (const q of questions) {
  const a = q.answer[0];
  if (!q.stemPlain || !q.choicesPlain.length || !Number.isInteger(a)) continue;
  q.jsonld = {
    "@context": "https://schema.org",
    "@type": "Quiz",
    name: `${q.exam.label} ${q.subjectName} 問${q.num}`,
    about: { "@type": "Thing", name: q.subjectName },
    educationalAlignment: { "@type": "AlignmentObject", alignmentType: "educationalSubject", targetName: "作業環境測定士試験" },
    hasPart: [{
      "@type": "Question",
      eduQuestionType: "Multiple choice",
      text: q.stemPlain,
      suggestedAnswer: q.choicesPlain.map((c, i) => ({ "@type": "Answer", position: i + 1, text: c })).filter((x) => x.position !== a),
      acceptedAnswer: { "@type": "Answer", position: a, text: q.choicesPlain[a - 1] },
    }],
  };
}

for (const q of questions) {
  for (const c of q.chapters) chapterOut[c.id].questions.push(q);
  for (const t of q.traps) trapOut[t.id].questions.push(q);
}
for (const t of traps) if (t.questions.length) chapterOut[t.chapter].traps.push(t);
for (const c of chapters) c.traps.sort((a, b) => RANK_ORDER[a.rank] - RANK_ORDER[b.rank] || b.count - a.count);

// 一覧ページ用の軽いデータ（科目ごとに /data/<科目>.json として書き出す）
const listItem = (q) => ({
  id: q.id, url: q.url, exam: q.exam.key, examLabel: q.exam.label, held: q.exam.held,
  subject: q.subject, subjectName: q.subjectName, num: q.num, rank: q.rank, rankLabel: q.rankLabel, method: q.method,
  chapters: q.chapters.map((c) => c.id), chapterLabels: q.chapters.map((c) => c.label),
  traps: q.traps.filter((t) => !t.misc && !t.hidden).map((t) => ({ name: t.name, url: t.url, understandingHtml: t.understandingHtml, reasonHtml: t.reasonHtml })),
  books: q.books,
  summary: q.summary, stemHtml: q.stemHtml, choices: q.choices, columns: q.columns, choiceCells: q.choiceCells, choiceNotes: q.choiceNotes, answer: q.answer,
  explanationHtml: q.explanationHtml, hasExplanation: q.hasExplanation, lawNote: q.lawNote, examNote: q.examNote, textNote: q.textNote, reviewNote: q.reviewNote, minorNote: q.minorNote, freq: q.freq, sourcePdf: q.sourcePdf, source: q.source,
  figures: q.figures,
});
const subjectsWithData = subjects
  .map((s) => ({ ...s, items: questions.filter((q) => q.subject === s.id).map(listItem) }))
  .filter((s) => s.items.length);

const exams = [...new Set(questions.map((q) => q.exam.key))].sort().reverse().map(examInfo);
const usedChapters = chapters.filter((c) => c.questions.length);
const parts = book.parts
  .map((p) => ({ ...p, chapters: usedChapters.filter((c) => c.part === p.id) }))
  .filter((p) => p.chapters.length);

// 参考書のページがある章（目次の順）と前後のつながり
const bookChapters = chapters.filter((c) => c.bookUrl);
bookChapters.forEach((c, i) => {
  c.bookPrev = bookChapters[i - 1] ? { label: bookChapters[i - 1].label, url: bookChapters[i - 1].bookUrl } : null;
  c.bookNext = bookChapters[i + 1] ? { label: bookChapters[i + 1].label, url: bookChapters[i + 1].bookUrl } : null;
});
const bookParts = book.parts
  .map((p) => ({ ...p, chapters: chapters.filter((c) => c.part === p.id) }))
  .filter((p) => p.chapters.length);

// ---- 件数（トップページの紹介文用）
const kindOf = Object.fromEntries(subjects.map((sj) => [sj.id, sj.kind]));
const examKeys = [...new Set(questions.map((q) => q.exam.key))].sort();
const commonQs = questions.filter((q) => kindOf[q.subject] === "共通");
const stats = {
  exams: examKeys.length,
  firstLabel: examKeys.length ? examInfo(examKeys[0]).label.replace(" ", "") : "",
  lastLabel: examKeys.length ? examInfo(examKeys[examKeys.length - 1]).label.replace(" ", "") : "",
  common: commonQs.length,
  selective: questions.filter((q) => kindOf[q.subject] === "選択").length,
  explained: questions.filter((q) => q.hasExplanation).length,
  explainedCommon: commonQs.filter((q) => q.hasExplanation).length,
  // 共通科目に、解説のない問題がある回（トップページの案内用）
  pendingCommonExams: examKeys.filter((k) => commonQs.some((q) => q.exam.key === k && !q.hasExplanation)).map((k) => examInfo(k).label.replace(" ", "")),
};

// ---- 回ごと・科目ごとの一覧ページ（検索エンジンにも読める静的なリンク集）
const shortTitle = (q) => {
  const t = q.traps.find((x) => !x.misc);
  if (t) return t.name;
  const st = (q.stemPlain || q.summary || "").replace(/[「」]/g, "");
  return st.length > 40 ? st.slice(0, 40) + "…" : st;
};
const qLink = (q) => ({ num: q.num, url: q.url, title: shortTitle(q), rank: q.rank });
const examPages = [...new Set(questions.map((q) => q.exam.key))].sort().reverse().map((key) => {
  const info = examInfo(key);
  const qs = questions.filter((q) => q.exam.key === key);
  const subs = subjects
    .map((sj) => ({ id: sj.id, name: sj.name, kind: sj.kind, url: `/subject/${sj.id}/`,
      questions: qs.filter((q) => q.subject === sj.id).sort((a, b) => a.num - b.num).map(qLink) }))
    .filter((x) => x.questions.length);
  return { ...info, url: `/exam/${key}/`, subjects: subs, count: qs.length, explained: qs.filter((q) => q.hasExplanation).length };
});
// 原理：その原理に紐づく論点が出た回の数と、「この原理で解ける問題」（正答の選択肢が、その原理に紐づく問題）
const principles = principleMaster.map((pm) => {
  const qs = questions.filter((q) => q.freq && q.freq.principle && q.freq.principle.id === pm.id)
    .sort((a, b) => b.exam.key.localeCompare(a.exam.key) || a.num - b.num);
  const cnt = Math.max(0, ...questions.filter((q) => q.subject === pm.subject && q.freq && q.freq.principle && q.freq.principle.id === pm.id).map((q) => q.freq.principle.count));
  const denom = (questions.find((q) => q.subject === pm.subject && q.freq) || { freq: { denom: 0 } }).freq.denom;
  return { ...pm, subjectName: subjectById[pm.subject]?.name, url: `/principle/${pm.id}/`, count: cnt, denom,
    statementHtml: renderInline(pm.statement || ""), pointsCount: (pm.points || []).length, questions: qs };
}).filter((x) => x.questions.length);
// 物質別の暗記リスト（ガイドブック3・4の目次・本文から作成。data/master/substances/<科目>.yaml）
const escapeRe = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const verifiedFile = path.join(ROOT, "master/substances/verified.yaml");
const verifiedAll = fs.existsSync(verifiedFile) ? load(verifiedFile).verified : {};
const substances = [];
for (const key of ["tokka", "kinzoku"]) {
  const f = path.join(ROOT, `master/substances/${key}.yaml`);
  if (!fs.existsSync(f)) continue;
  const doc = load(f);
  const subjQs = questions.filter((q) => q.subject === key);
  const denom = new Set(subjQs.map((q) => q.exam.key)).size;
  for (const sb of doc.substances) {
    const pats = (sb.match || [sb.name]).map((n) => new RegExp(`(?<![ァ-ヶ])${escapeRe(n)}(?![ァ-ヶ化])`));
    const qs = subjQs.filter((q) => pats.some((re) => re.test(q._text || ""))).sort((a, b) => b.exam.key.localeCompare(a.exam.key) || a.num - b.num);
    const exams = new Set(qs.map((q) => q.exam.key));
    const ver = (verifiedAll[key] || {})[sb.code] || null;
    const methods = sb.methods.map((m) => ({ ...m, v: ver ? ver[m.no] || null : null }));
    substances.push({ ...sb, methods, verified: !!ver, id: `sb-${key}-${sb.code}`, subject: key, subjectName: subjectById[key]?.name, book: doc.book,
      url: `/substance/sb-${key}-${sb.code}/`, questions: qs, examCount: exams.size, denom });
  }
}
const substancesBySubject = (id) => substances.filter((x) => x.subject === id).sort((a, b) => b.examCount - a.examCount || a.code.localeCompare(b.code));
const principlesBySubject = (id) => principles.filter((x) => x.subject === id).sort((a, b) => b.count - a.count || b.questions.length - a.questions.length);
const subjectPages = subjects
  .map((sj) => {
    const qs = questions.filter((q) => q.subject === sj.id);
    const ex = [...new Set(qs.map((q) => q.exam.key))].sort().reverse().map((key) => ({
      ...examInfo(key), url: `/exam/${key}/`,
      questions: qs.filter((q) => q.exam.key === key).sort((a, b) => a.num - b.num).map(qLink),
    }));
    return { id: sj.id, name: sj.name, kind: sj.kind, url: `/subject/${sj.id}/`, principles: principlesBySubject(sj.id), substances: substancesBySubject(sj.id), exams: ex, count: qs.length, explained: qs.filter((q) => q.hasExplanation).length };
  })
  .filter((x) => x.count);
questions.forEach((q) => { q.examUrl = `/exam/${q.exam.key}/`; q.subjectUrl = `/subject/${q.subject}/`; });

// 確認中の解説の一覧（/review/ ページ用）
const reviewQuestions = questions.filter((q) => q.reviewNote);
const minorQuestions = questions.filter((q) => q.minorNote);

export default {
  stats,
  examPages,
  subjectPages,
  reviewQuestions,
  minorQuestions,
  bookChapters,
  bookParts,
  subjects,
  subjectsWithData,
  exams,
  parts,
  chapters: usedChapters,
  traps: traps.filter((t) => t.questions.length && t.url),
  principles,
  substances,
  questions,
};
