// 演習の計算（画面と切り離した純関数。node でも試せる）
// 定数は、ここ1か所にまとめる（復習・一問一答の定数は段階3・4で足す）。
export const MODES = ["exam", "review", "drill"];
export const RANK_ORDER = ["S", "A", "B", "C", "D"];

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
export function makeAttempt(q, selected, isCorrect, now = new Date(), uuid = () => crypto.randomUUID()) {
  return {
    id: uuid(),
    question_id: q.id,
    choice_n: null,
    mode: "exam",
    selected: [...selected].map(Number).sort((x, y) => x - y).join(","),
    is_correct: !!isCorrect,
    answered_at: now.toISOString(),
  };
}

/** 通常の問題の記録（choice_n が null）から、問題ごとの成績を求める。 */
export function statsByQuestion(attempts) {
  const map = new Map();
  const list = attempts.filter((a) => a.choice_n == null && a.mode !== "drill")
    .sort((a, b) => a.answered_at.localeCompare(b.answered_at));
  for (const a of list) {
    const s = map.get(a.question_id) || { n: 0, correct: 0, lastAt: null, lastOk: null, streak: 0 };
    s.n += 1;
    if (a.is_correct) { s.correct += 1; s.streak += 1; } else { s.streak = 0; }
    s.lastAt = a.answered_at;
    s.lastOk = a.is_correct;
    map.set(a.question_id, s);
  }
  return map;
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
