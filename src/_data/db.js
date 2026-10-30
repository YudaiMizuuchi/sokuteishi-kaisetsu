// data/ のYAMLを読み込み、ページ生成に使う形に整える。
// 整合性のチェックもここで行い、問題があればビルドを止める。
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import MarkdownIt from "markdown-it";
import site from "./site.js";

const ROOT = path.join(process.cwd(), "data");
const md = new MarkdownIt({ html: true, breaks: true });
const load = (p) => yaml.load(fs.readFileSync(p, "utf8"));
const render = (s) => (s ? md.render(String(s)) : "");
const renderInline = (s) => (s ? md.renderInline(String(s)) : "");
const errors = [];

const subjects = load(path.join(ROOT, "master/subjects.yaml"));
const book = load(path.join(ROOT, "master/book.yaml"));
const subjectById = Object.fromEntries(subjects.map((s) => [s.id, s]));
const partById = Object.fromEntries(book.parts.map((p) => [p.id, p]));
const chapterById = Object.fromEntries(book.chapters.map((c) => [c.id, c]));
const trapById = Object.fromEntries(book.traps.map((t) => [t.id, t]));

// 実施年月（2025-02）→ 年度・回・表示ラベル
function examInfo(key) {
  const [y, m] = key.split("-").map(Number);
  const fy = m <= 3 ? y - 1 : y;
  const round = m <= 3 ? 2 : 1;
  const reiwa = fy - 2018;
  return {
    key, fy, round,
    label: `令和${reiwa === 1 ? "元" : reiwa}年度 第${round}回`,
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

// ---- 章・罠の型
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
  if (!chapterById[t.chapter]) errors.push(`罠の型 ${t.id}: 章 ${t.chapter} がない`);
  if (t.foundation && !chapterById[t.foundation]) errors.push(`罠の型 ${t.id}: 章 ${t.foundation} がない`);
  return {
    ...t,
    // 「その他（単発）」は寄せ集めなので、独立したページを作らない
    misc: t.name.includes("その他"),
    // 「その他（単発）」と、非公開にした（hidden: true）罠の型はページを作らない
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
const RANK_ORDER = { A: 0, B: 1, C: 2 };
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
      for (const t of q.traps || []) if (!trapById[t]) errors.push(`${where} 問${q.num}: 罠の型 ${t} がない`);
      const answers = q.answer == null ? [] : Array.isArray(q.answer) ? q.answer : [q.answer];
      if (q.choices?.length)
        for (const a of answers)
          if (a !== "all" && !(a >= 1 && a <= q.choices.length)) errors.push(`${where} 問${q.num}: 正答 ${a} が選択肢の範囲外`);
      if (q.status === "published") {
        if (!q.explanation) errors.push(`${where} 問${q.num}: published なのに解説がない`);
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
      const rank = q.rank || qTraps.map((t) => t.rank).sort((a, b) => RANK_ORDER[a] - RANK_ORDER[b])[0] || null;
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
        chapters: (q.chapters || []).map((c) => ({ id: c, label: chapterLabel(chapterById[c]), url: `/chapter/${c}/` })),
        // 参考書のページがある章（主な章が先）
        books: (q.chapters || []).filter((c) => fs.existsSync(path.join(BOOK_DIR, `${c}.md`)))
          .map((c) => ({ label: chapterLabel(chapterById[c]), url: `/book/${c}/` })),
        traps: qTraps.map((t) => trapOut[t.id]),
        summary: q.summary || null,
        stemHtml: site.showStem ? render(q.stem) : "",
        stemPlain: site.showStem ? String(q.stem || "").replace(/\s+/g, " ").trim() : "",
        choices: site.showStem ? (q.choices || []).map(renderInline) : [],
        choicesPlain: site.showStem ? (q.choices || []).map((c) => String(c)) : [],
        // 組合せ問題：見出し（Ⓐ Ⓑ など）と、選択肢を列ごとに分けたもの
        columns: site.showStem && q.columns ? q.columns : null,
        choiceCells: site.showStem && q.columns
          ? (q.choices || []).map((c) => String(c).split(/\s*／\s*/).map(renderInline)) : null,
        answer: answers,
        choiceNotes: site.showStem ? (q.choice_notes || []).map((n, i) => ({ html: renderInline(n), isAnswer: answers.includes(i + 1) })) : [],
        source: `${site.sourceName}（${examInfo(exam).label}・${examInfo(exam).held}）`,
        explanationHtml: render(q.explanation),
        // figures: [{file: "2024-08-design-07.png", alt: "…"}]（src/assets/figures/ に置く）
        figures: (q.figures || []).map((f) => (typeof f === "string" ? { file: f, alt: "" } : f))
          .map((f) => ({ src: `/assets/figures/${f.file}`, alt: f.alt || "" })),
        lawNote: q.law_note || null,
        examNote: q.exam_note || null, // 協会による正答の注記（複数正答など）
        reviewNote: q.review_note || null, // 管理者が確認中の点（確認が済んだら消す）
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
  subject: q.subject, subjectName: q.subjectName, num: q.num, rank: q.rank,
  chapters: q.chapters.map((c) => c.id), chapterLabels: q.chapters.map((c) => c.label),
  traps: q.traps.filter((t) => !t.misc && !t.hidden).map((t) => ({ name: t.name, url: t.url, understandingHtml: t.understandingHtml, reasonHtml: t.reasonHtml })),
  books: q.books,
  summary: q.summary, stemHtml: q.stemHtml, choices: q.choices, columns: q.columns, choiceCells: q.choiceCells, choiceNotes: q.choiceNotes, answer: q.answer,
  explanationHtml: q.explanationHtml, lawNote: q.lawNote, examNote: q.examNote, reviewNote: q.reviewNote, sourcePdf: q.sourcePdf, source: q.source,
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

// 確認中の解説の一覧（/review/ ページ用）
const reviewQuestions = questions.filter((q) => q.reviewNote);

export default {
  reviewQuestions,
  bookChapters,
  bookParts,
  subjects,
  subjectsWithData,
  exams,
  parts,
  chapters: usedChapters,
  traps: traps.filter((t) => t.questions.length && t.url),
  questions,
};
