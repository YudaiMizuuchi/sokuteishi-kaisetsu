// 演習の計算（画面と切り離した純関数。node でも試せる）
// 定数は、ここ1か所にまとめる（一問一答の定数は段階4で足す）。
export const MODES = ["exam", "review", "drill"];
export const RANK_ORDER = ["S", "A", "B", "C", "D"];

// ---- 復習の自動選択の定数（設計書 §5）
export const INTERVAL_DAYS = [1, 3, 7, 14, 30];       // 連続正解が 1〜5回以上のとき、次に出すまでの間隔（日）
export const RANK_WEIGHT = { S: 5, A: 4, B: 3, C: 2, D: 1 };
export const SESSION_SIZE = 10;                       // 1回の復習の問題数（画面で 5／10／20 を選べる）
export const MIN_NEW_IN_SESSION = 2;                  // 間違えた問題が多いときも、まだ解いていない問題を最低これだけ混ぜる
export const INCLUDE_RANK_C = true;                   // 未解答の問題に、区分 C を含めるか（既定）
export const INCLUDE_RANK_D = false;                  // 未解答の問題に、区分 D を含めるか（既定）
export const KEEP_PER_KEY = 10;                       // 同じ問題（一問一答は、同じ選択肢）の記録を、最新の何件まで残すか
export const MIN_SOLVED_FOR_WEAK = 5;                 // 「弱い章」に数える、解いた問題数の下限
export const MIN_SOLVED_FOR_WEAK_DRILL = 10;          // 〃（一問一答。選択肢の数で数える。1問が5肢なので、2問分）
export const WEAK_CHAPTERS_SHOWN = 10;
export const DRILL_RECENT_BONUS = 2;                  // 一問一答：直近の回に出た論点への加点（1回あたり）
export const DRILL_RECENT_CAP = 3;                    // 〃（数える回数の上限）
const DAY = 86400000;

/** 選んだ番号（配列）が正答か。正答が ["all"] なら、どれを選んでも正解。正答が未掲載なら null（採点しない）。 */
export function gradeAnswer(q, selected) {
  const ans = q.answer || [];
  if (!ans.length) return null;
  if (ans[0] === "all") return true;
  const a = ans.map(String).sort().join(",");
  const s = [...new Set(selected.map(String))].sort().join(",");
  return a === s;
}

/** 記録（attempt）を作る。id は端末で作り、再送・取り込みで重複しないようにする。 */
export function makeAttempt(q, selected, isCorrect, now = new Date(), uuid = () => crypto.randomUUID(), mode = "exam") {
  return {
    id: uuid(),
    question_id: q.id,
    choice_n: null,
    mode,
    selected: [...selected].map(Number).sort((x, y) => x - y).join(","),
    is_correct: !!isCorrect,
    answered_at: now.toISOString(),
  };
}

function fold(list, keyOf) {
  const map = new Map();
  for (const a of [...list].sort((x, y) => x.answered_at.localeCompare(y.answered_at))) {
    const k = keyOf(a);
    const s = map.get(k) || { n: 0, correct: 0, lastAt: null, lastOk: null, streak: 0 };
    s.n += 1;
    if (a.is_correct) { s.correct += 1; s.streak += 1; } else { s.streak = 0; }
    s.lastAt = a.answered_at;
    s.lastOk = a.is_correct;
    map.set(k, s);
  }
  return map;
}

/** 通常の問題の記録（choice_n が null）から、問題ごとの成績を求める。 */
export function statsByQuestion(attempts) {
  return fold(attempts.filter((a) => a.choice_n == null && a.mode !== "drill"), (a) => a.question_id);
}

/** 絞り込み。state: { exam, chapter, ranks:Set, scope:"all"|"unsolved"|"wrong" } */
export function matches(q, state, stats) {
  if (state.exam && q.exam !== state.exam) return false;
  if (state.chapter && !(q.chapters || []).includes(state.chapter)) return false;
  if (state.ranks && state.ranks.size && !state.ranks.has(q.rank)) return false;
  const s = stats && stats.get(q.id);
  if (state.scope === "unsolved" && s) return false;
  if (state.scope === "wrong" && !(s && s.lastOk === false)) return false;
  return true;
}

/** 並べ替え。order: "new"（新しい回から）| "old" | "random" */
export function orderQuestions(list, order, subjectOrder = [], rng = Math.random) {
  const out = [...list];
  const sIdx = (q) => { const i = subjectOrder.indexOf(q.subject); return i < 0 ? 99 : i; };
  if (order === "random") {
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }
  const sign = order === "old" ? -1 : 1;
  return out.sort((a, b) => sign * b.exam.localeCompare(a.exam) || sIdx(a) - sIdx(b) || a.num - b.num);
}

/** この回のまとめ（解いた数・正解数） */
export function summarize(results) {
  const graded = results.filter((r) => r.ok !== null);
  return { answered: results.length, graded: graded.length, correct: graded.filter((r) => r.ok).length };
}


// =====================================================================
// 復習の自動選択（設計書 §5）
// =====================================================================
const rw = (q) => RANK_WEIGHT[q.rank] ?? 0;

/** 問題の分類と優先度。bucket: 1＝直近で間違えた／2＝正解したが間隔が空いた／3＝まだ解いていない／0＝いまは出さない */
export function classify(q, s, now = new Date(), opts = {}) {
  const includeC = opts.includeC ?? INCLUDE_RANK_C, includeD = opts.includeD ?? INCLUDE_RANK_D;
  if (!s) {
    if (q.rank === "D" && !includeD) return { bucket: 0, score: 0 };
    if (q.rank === "C" && !includeC) return { bucket: 0, score: 0 };
    return { bucket: 3, score: rw(q) * 10 };
  }
  return classifySeen(q, s, now);
}

/** 解いたことがある問題（選択肢）の分類：1＝直近で間違えた／2＝正解したが間隔が空いた／0＝いまは出さない */
function classifySeen(q, s, now) {
  if (s.lastOk === false) return { bucket: 1, score: 1000 + rw(q) * 10 + (1 - s.correct / s.n) * 20 };
  const iv = INTERVAL_DAYS[Math.min(Math.max(s.streak, 1), INTERVAL_DAYS.length) - 1];
  const elapsed = (now.getTime() - Date.parse(s.lastAt)) / DAY;
  if (elapsed < iv) return { bucket: 0, score: 0 };
  return { bucket: 2, score: 500 + Math.min(elapsed / iv, 5) * 20 + rw(q) };
}

/**
 * 復習する問題を選ぶ。items は絞り込み済みの問題。
 * 戻り値：{ picked, counts:{wrong, due, unsolved}（選べる問題の総数）}
 */
export function selectReview(items, stats, { now = new Date(), size = SESSION_SIZE, includeC, includeD } = {}) {
  const b = { 1: [], 2: [], 3: [] };
  for (const q of items) {
    const s = stats.get(q.id);
    const c = classify(q, s, now, { includeC, includeD });
    if (c.bucket) b[c.bucket].push({ q, score: c.score, lastAt: s ? s.lastAt : "" });
  }
  const bySc = (x, y) => y.score - x.score || x.lastAt.localeCompare(y.lastAt) || y.q.exam.localeCompare(x.q.exam) || x.q.num - y.q.num;
  for (const k of [1, 2, 3]) b[k].sort(bySc);
  let picked;
  if (b[1].length >= size && b[3].length) {
    const newN = Math.min(MIN_NEW_IN_SESSION, b[3].length, size);
    picked = [...b[1].slice(0, size - newN), ...b[3].slice(0, newN)];
  } else picked = [...b[1], ...b[2], ...b[3]].slice(0, size);
  return { picked: picked.map((x) => x.q), counts: { wrong: b[1].length, due: b[2].length, unsolved: b[3].length } };
}

// =====================================================================
// 成績（設計書 §7）
// =====================================================================
/** 問題IDから科目IDを取り出す（2024-02-hourei-01 → hourei） */
export const subjectOfId = (id) => String(id).split("-")[2] || "";

function addTo(map, key, q, s) {
  const g = map.get(key) || { key, total: 0, solved: 0, n: 0, correct: 0, lastCorrect: 0 };
  g.total += 1;
  if (s) { g.solved += 1; g.n += s.n; g.correct += s.correct; if (s.lastOk) g.lastCorrect += 1; }
  map.set(key, g);
}
const withRates = (g) => ({ ...g, acc: g.n ? g.correct / g.n : null, latestAcc: g.solved ? g.lastCorrect / g.solved : null });

/** 科目別・区分別・章別（章は、先頭の章だけに数える）の、解いた数と正答率 */
export function aggregate(items, stats) {
  const bySubject = new Map(), byRank = new Map(), byChapter = new Map();
  for (const q of items) {
    const s = stats.get(q.id);
    addTo(bySubject, q.subject, q, s);
    addTo(byRank, q.rank || "-", q, s);
    if ((q.chapters || []).length) addTo(byChapter, q.chapters[0], q, s);
  }
  const out = (m) => [...m.values()].map(withRates);
  return { bySubject: out(bySubject), byRank: out(byRank), byChapter: out(byChapter) };
}

/** 弱い章：解いた問題が一定数以上の章を、通算の正答率の低い順に */
export function weakChapters(rows, { min = MIN_SOLVED_FOR_WEAK, limit = WEAK_CHAPTERS_SHOWN } = {}) {
  return rows.filter((r) => r.solved >= min && r.acc !== null)
    .sort((a, b) => a.acc - b.acc || b.n - a.n || a.key.localeCompare(b.key)).slice(0, limit);
}


// =====================================================================
// 一問一答（設計書 §6）。選択肢1つ＝1問。記録のキーは「問題ID＋選択肢番号」。
// =====================================================================
export const drillKey = (qid, n) => `${qid}#${n}`;

/** 一問一答の記録（mode が drill で、choice_n がある）から、選択肢ごとの成績を求める。 */
export function drillStats(attempts) {
  return fold(attempts.filter((a) => a.mode === "drill" && a.choice_n != null), (a) => drillKey(a.question_id, a.choice_n));
}

/** 選択肢が語句・式だけの問か（サイト側のデータ drill.phrase）。この問では、問題文を出し、「この問の正答か」を聞く。 */
export const isPhraseDrill = (q) => !!(q.drill && q.drill.phrase === true);

/**
 * 一問一答で、「はい」（1番目のボタン）が正解になるか。
 * ふつうの問：その記述が正しいか（item.truth）。語句だけの問：その選択肢が、その問の正答か（item.isAnswer）。
 * isAnswer がないデータ（古い版）では、問題の正答（q.answer）から求める。
 */
export function drillExpected(q, item) {
  if (!isPhraseDrill(q)) return item.truth;
  if (typeof item.isAnswer === "boolean") return item.isAnswer;
  const ans = q.answer || [];
  return ans[0] === "all" ? true : ans.map(String).includes(String(item.n));
}

/** 一問一答の記録を作る。judged は、利用者の判断（true＝「正しい」／「正答」、false＝「誤り」／「正答ではない」）。 */
export function makeDrillAttempt(q, item, judged, now = new Date(), uuid = () => crypto.randomUUID()) {
  return {
    id: uuid(), question_id: q.id, choice_n: item.n, mode: "drill",
    selected: judged ? "true" : "false", is_correct: judged === drillExpected(q, item), answered_at: now.toISOString(),
  };
}

/** 選択肢の分類と優先度。まだ解いていないものは、よく出る論点（count/denom）・区分・直近の出題を優先する。 */
export function classifyDrill(q, item, s, now = new Date(), opts = {}) {
  if (s) return classifySeen(q, s, now);
  const includeC = opts.includeC ?? INCLUDE_RANK_C, includeD = opts.includeD ?? INCLUDE_RANK_D;
  if (q.rank === "D" && !includeD) return { bucket: 0, score: 0 };
  if (q.rank === "C" && !includeC) return { bucket: 0, score: 0 };
  const freq = (item.count ?? 0) / ((q.drill && q.drill.denom) || 1);
  return { bucket: 3, score: 100 * freq + rw(q) * 5 + Math.min(item.recent ?? 0, DRILL_RECENT_CAP) * DRILL_RECENT_BONUS };
}

/**
 * 一問一答で出す選択肢を選ぶ。questions は絞り込み済みの問題。
 * 同じ論点（item.point）は、1回に1問まで。戻り値：{ picked:[{q,item}], counts }
 */
export function selectDrill(questions, stats, { now = new Date(), size = SESSION_SIZE, includeC, includeD } = {}) {
  const b = { 1: [], 2: [], 3: [] };
  for (const q of questions) {
    if (!q.drill) continue;
    for (const item of q.drill.items) {
      const s = stats.get(drillKey(q.id, item.n));
      const c = classifyDrill(q, item, s, now, { includeC, includeD });
      if (c.bucket) b[c.bucket].push({ q, item, score: c.score, lastAt: s ? s.lastAt : "" });
    }
  }
  const cmp = (x, y) => y.score - x.score || x.lastAt.localeCompare(y.lastAt) || y.q.exam.localeCompare(x.q.exam) || x.q.num - y.q.num || x.item.n - y.item.n;
  for (const k of [1, 2, 3]) b[k].sort(cmp);
  const out = [], used = new Set();
  const take = (list, n) => {
    let k = 0;
    for (const x of list) {
      if (k >= n || out.length >= size) break;
      if (x.item.point && used.has(x.item.point)) continue;
      if (x.item.point) used.add(x.item.point);
      out.push(x); k += 1;
    }
  };
  if (b[1].length >= size && b[3].length) {
    const newN = Math.min(MIN_NEW_IN_SESSION, size);
    take(b[1], size - newN); take(b[3], newN);
  }
  take(b[1], size); take(b[2], size); take(b[3], size);
  return { picked: out.map((x) => ({ q: x.q, item: x.item })), counts: { wrong: b[1].length, due: b[2].length, unsolved: b[3].length } };
}

/** 一問一答の成績（解いた選択肢の数・延べ回数・正解数） */
export function drillSummary(attempts) {
  const st = drillStats(attempts);
  let n = 0, correct = 0;
  for (const s of st.values()) { n += s.n; correct += s.correct; }
  return { solved: st.size, n, correct, acc: n ? correct / n : null };
}


// =====================================================================
// 記録の間引き（容量対策）：同じ問題（一問一答は、同じ選択肢）の記録は、最新 KEEP_PER_KEY 件まで
// =====================================================================
const attemptKey = (a) => (a.mode === "drill" && a.choice_n != null ? drillKey(a.question_id, a.choice_n) : a.question_id);

/** いま追加した記録 added と同じキーの記録のうち、古くて消してよいものの id を返す。 */
export function pruneIds(attempts, added, keep = KEEP_PER_KEY) {
  const key = attemptKey(added), drill = added.mode === "drill" && added.choice_n != null;
  const same = attempts.filter((a) => (a.mode === "drill" && a.choice_n != null) === drill && attemptKey(a) === key)
    .sort((x, y) => y.answered_at.localeCompare(x.answered_at));
  return same.slice(keep).map((a) => a.id);
}


/** 一問一答の成績：科目別・区分別・章別（章は、先頭の章だけ）。数える単位は、選択肢。 */
export function aggregateDrill(items, dstats) {
  const bySubject = new Map(), byRank = new Map(), byChapter = new Map();
  for (const q of items) {
    if (!q.drill) continue;
    for (const item of q.drill.items) {
      const s = dstats.get(drillKey(q.id, item.n));
      addTo(bySubject, q.subject, q, s);
      addTo(byRank, q.rank || "-", q, s);
      if ((q.chapters || []).length) addTo(byChapter, q.chapters[0], q, s);
    }
  }
  const out = (m) => [...m.values()].map(withRates);
  return { bySubject: out(bySubject), byRank: out(byRank), byChapter: out(byChapter) };
}


// =====================================================================
// 無効にする記録：サイト側で、問題の中身が差し替わった回（問題IDは同じまま、問題文・選択肢・正答が変わった）。
// 差し替えより前の記録は、別の問題に対する記録なので、集計・復習から外し、保存先からも消す。
// 追加するときは、ここに1行足す（before は、差し替えを公開した時刻より後にする。日本時間の日付の終わりが無難）。
// =====================================================================
export const INVALIDATED = [
  // 令和4年度第2回（2023-02）の共通4科目・80問。2026年11月11日に差し替え。11月11日（日本時間）の終わりまでの記録を外す。
  { exam: "2023-02", subjects: ["ippan", "hourei", "design", "bunseki"], before: "2026-11-12T00:00:00+09:00", label: "令和4年度第2回（共通4科目）" },
];

/** その記録が、差し替え前の問題に対するものか */
export function isInvalidated(a, rules = INVALIDATED) {
  const t = Date.parse(a.answered_at);
  return rules.some((r) => r.subjects.some((s) => String(a.question_id).startsWith(`${r.exam}-${s}-`)) && !(t >= Date.parse(r.before)));
}

/** 記録を、残すもの（keep）と、外すもの（drop）に分ける */
export function splitInvalidated(attempts, rules = INVALIDATED) {
  const keep = [], drop = [];
  for (const a of attempts) (isInvalidated(a, rules) ? drop : keep).push(a);
  return { keep, drop };
}
