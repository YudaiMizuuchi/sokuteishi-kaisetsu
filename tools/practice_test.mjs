// 演習機能のテスト（node tools/practice_test.mjs）。ビルド後（_site/data があるとき）は、全問題の描画も走査する。
import fs from "node:fs";
import { gradeAnswer, makeAttempt, statsByQuestion, matches, orderQuestions, summarize, classify, selectReview, aggregate, aggregateDrill, weakChapters, subjectOfId, INTERVAL_DAYS, SESSION_SIZE, drillKey, drillStats, makeDrillAttempt, classifyDrill, selectDrill, drillSummary, pruneIds, KEEP_PER_KEY, drillExpected, isPhraseDrill } from "../src/assets/practice/logic.js";
import { renderQuestion, renderResult, fixLinks, renderDrill, renderDrillResult, esc } from "../src/assets/practice/render.js";
import { createLocalStore, createStore } from "../src/assets/practice/store.js";
import { fetchAll, insertMany, deleteAll, deleteByIds, PAGE } from "../src/assets/practice/cloud.js";

let fail = 0;
const ok = (cond, msg) => { if (!cond) { fail++; console.log("✗", msg); } };
const eq = (a, b, msg) => ok(JSON.stringify(a) === JSON.stringify(b), `${msg}：${JSON.stringify(a)} ≠ ${JSON.stringify(b)}`);

// --- 採点
eq(gradeAnswer({ answer: ["3"] }, ["3"]), true, "単一正解");
eq(gradeAnswer({ answer: [3] }, ["3"]), true, "数値の正答");
eq(gradeAnswer({ answer: ["3"] }, ["2"]), false, "単一不正解");
eq(gradeAnswer({ answer: ["1", "3"] }, ["3", "1"]), true, "複数正答（順不同）");
eq(gradeAnswer({ answer: ["1", "3"] }, ["1"]), false, "複数正答（不足）");
eq(gradeAnswer({ answer: ["all"] }, ["2"]), true, "全員正解");
eq(gradeAnswer({ answer: [] }, ["2"]), null, "正答未掲載は採点しない");

// --- 記録・成績・絞り込み・並べ替え
const mk = (id, sel, okv, t) => ({ id: id + t, question_id: id, choice_n: null, mode: "exam", selected: sel, is_correct: okv, answered_at: t });
const att = [mk("a", "1", false, "2026-11-01T00:00:00Z"), mk("a", "2", true, "2026-11-02T00:00:00Z"), mk("b", "1", false, "2026-11-03T00:00:00Z"),
  { ...mk("c", "true", true, "2026-11-03T00:00:00Z"), choice_n: 2, mode: "drill" }];
const st = statsByQuestion(att);
eq([st.get("a").n, st.get("a").correct, st.get("a").lastOk, st.get("a").streak], [2, 1, true, 1], "成績a");
eq([st.get("b").lastOk, st.get("b").streak], [false, 0], "成績b");
ok(!st.has("c"), "一問一答の記録は、通常の成績に入れない");
const qs = [
  { id: "a", exam: "2024-08", subject: "ippan", num: 1, rank: "S", chapters: ["x"] },
  { id: "b", exam: "2024-08", subject: "hourei", num: 2, rank: "A", chapters: ["y"] },
  { id: "c", exam: "2024-02", subject: "ippan", num: 3, rank: "B", chapters: ["x", "y"] },
  { id: "d", exam: "2023-08", subject: "ippan", num: 4, rank: "D", chapters: [] }];
const S = (o) => ({ exam: "", chapter: "", ranks: new Set(), scope: "all", ...o });
eq(qs.filter((q) => matches(q, S({ scope: "unsolved" }), st)).map((q) => q.id), ["c", "d"], "未解答だけ");
eq(qs.filter((q) => matches(q, S({ scope: "wrong" }), st)).map((q) => q.id), ["b"], "直近で間違えた問題だけ");
eq(qs.filter((q) => matches(q, S({ chapter: "y", ranks: new Set(["A", "B"]) }), st)).map((q) => q.id), ["b", "c"], "章＋区分");
eq(orderQuestions(qs, "new", ["ippan", "hourei"]).map((q) => q.id), ["a", "b", "c", "d"], "新しい回から");
eq(orderQuestions(qs, "old", ["ippan", "hourei"]).map((q) => q.id), ["d", "c", "a", "b"], "古い回から");
eq(orderQuestions(qs, "random", [], () => 0).length, 4, "ランダムで件数が変わらない");
eq(summarize([{ ok: true }, { ok: false }, { ok: null }]), { answered: 3, graded: 2, correct: 1 }, "まとめ");
const at = makeAttempt({ id: "q1" }, ["3", "1"], true, new Date("2026-11-10T00:00:00Z"), () => "uuid-1");
eq(at, { id: "uuid-1", question_id: "q1", choice_n: null, mode: "exam", selected: "1,3", is_correct: true, answered_at: "2026-11-10T00:00:00.000Z" }, "記録の形");


// --- 復習の自動選択
{
  const NOW = new Date("2026-11-30T00:00:00Z");
  const day = (n) => new Date(NOW.getTime() - n * 86400000).toISOString();
  const Q = (id, rank, extra = {}) => ({ id, exam: "2024-08", subject: "ippan", num: 1, rank, chapters: ["c1"], ...extra });
  const at = (id, ok, d) => ({ id: id + d, question_id: id, choice_n: null, mode: "review", selected: "1", is_correct: ok, answered_at: day(d) });
  // 間隔：連続正解 1→1日、2→3日、3→7日、4→14日、5以上→30日
  const mkStreak = (k, d) => Array.from({ length: k }, (_, i) => at("s", true, d + (k - 1 - i)));
  eq(INTERVAL_DAYS, [1, 3, 7, 14, 30], "間隔の既定値");
  const due = (k, d) => classify(Q("s", "A"), statsByQuestion(mkStreak(k, d)).get("s"), NOW).bucket;
  eq([due(1, 0.5), due(1, 1.01), due(2, 2.9), due(2, 3.1), due(3, 6.9), due(3, 7.1), due(4, 13), due(4, 14.1), due(5, 29), due(5, 30.1), due(9, 31)],
     [0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 2], "正解が続くほど、間隔が延びる");
  // 優先度：間違えた ＞ 間隔が空いた ＞ 未解答。区分の高い順。
  const items = [Q("w-S", "S"), Q("w-B", "B"), Q("d-S", "S"), Q("n-S", "S"), Q("n-A", "A"), Q("n-B", "B"), Q("n-C", "C"), Q("n-D", "D"), Q("ok", "S")];
  const att2 = [at("w-S", false, 3), at("w-B", false, 2), at("d-S", true, 40), at("ok", true, 0.1)];
  const st2 = statsByQuestion(att2);
  const r1 = selectReview(items, st2, { now: NOW });
  eq(r1.picked.map((q) => q.id), ["w-S", "w-B", "d-S", "n-S", "n-A", "n-B", "n-C"], "選ぶ順（D は既定で除く）");
  eq(r1.counts, { wrong: 2, due: 1, unsolved: 4 }, "分類の件数");
  eq(selectReview(items, st2, { now: NOW, includeD: true }).picked.map((q) => q.id).includes("n-D"), true, "D を含める切り替え");
  eq(selectReview(items, st2, { now: NOW, includeC: false }).picked.map((q) => q.id).includes("n-C"), false, "C を除く切り替え");
  eq(selectReview(items, st2, { now: NOW, size: 3 }).picked.map((q) => q.id), ["w-S", "w-B", "d-S"], "件数の上限");
  // 間違えた問題が多いときも、未解答を最低2問混ぜる
  const many = Array.from({ length: 12 }, (_, i) => Q("m" + i, "S"));
  const stMany = statsByQuestion(many.map((q, i) => at(q.id, false, 1 + i)));
  const r2 = selectReview([...many, Q("x1", "A"), Q("x2", "B"), Q("x3", "S")], stMany, { now: NOW });
  eq([r2.picked.length, r2.picked.filter((q) => q.id.startsWith("x")).length], [SESSION_SIZE, 2], "未解答を2問混ぜる");
  eq(r2.picked.filter((q) => q.id.startsWith("x")).map((q) => q.id), ["x3", "x1"], "混ぜるのは区分の高い順");
  // 間違えた中では、正答率の低いもの→古いものを先に
  const att3 = [at("p", true, 9), at("p", true, 8), at("p", false, 7), at("r", false, 5), at("r", false, 4), at("r", false, 3)];
  eq(selectReview([Q("p", "S"), Q("r", "S")], statsByQuestion(att3), { now: NOW }).picked.map((q) => q.id), ["r", "p"], "正答率の低い問題を先に");
  // 間違えたあとの1回の正解は、間隔1日から
  eq(classify(Q("z", "S"), statsByQuestion([at("z", false, 5), at("z", true, 2)]).get("z"), NOW).bucket, 2, "間違い→正解（連続1）は1日後に再出題");
  eq(classify(Q("z", "S"), statsByQuestion([at("z", false, 5), at("z", true, 0.2)]).get("z"), NOW).bucket, 0, "直後は出さない");
  eq(classify({ id: "u", rank: null, exam: "x", num: 1 }, undefined, NOW), { bucket: 3, score: 0 }, "区分なしの未解答");
}

// --- 一問一答
{
  const NOW = new Date("2026-11-30T00:00:00Z");
  const day = (n) => new Date(NOW.getTime() - n * 86400000).toISOString();
  const mkq = (id, rank, items, extra = {}) => ({ id, exam: "2024-08", subject: "ippan", num: 1, rank, drill: { denom: 23, items }, ...extra });
  const it = (n, truth, point, count, recent = 0) => ({ n, truth, point, pointName: "論点" + point, count, recent, principle: null, principleName: null });
  const da = (id, n, ok, d) => ({ id: `${id}#${n}#${d}`, question_id: id, choice_n: n, mode: "drill", selected: ok ? "true" : "false", is_correct: ok, answered_at: day(d) });
  // 記録の作り方
  const q0 = mkq("q0", "S", [it(1, true, "p1", 5), it(2, false, "p2", 3)]);
  const a1 = makeDrillAttempt(q0, q0.drill.items[1], false, new Date("2026-11-10T00:00:00Z"), () => "u1");
  eq(a1, { id: "u1", question_id: "q0", choice_n: 2, mode: "drill", selected: "false", is_correct: true, answered_at: "2026-11-10T00:00:00.000Z" }, "「誤り」と答えて、実際に誤り→正解");
  eq(makeDrillAttempt(q0, q0.drill.items[0], false, NOW, () => "u2").is_correct, false, "「正しい」記述を「誤り」と答えたら不正解");
  eq(makeDrillAttempt(q0, q0.drill.items[0], true, NOW, () => "u3").selected, "true", "selected は true／false");
  // 成績のキーは「問題ID＋選択肢番号」。通常の問題の成績とは混ざらない
  const mixed = [da("q0", 1, true, 3), da("q0", 2, false, 2), { id: "x", question_id: "q0", choice_n: null, mode: "exam", selected: "1", is_correct: true, answered_at: day(1) }];
  const ds = drillStats(mixed);
  eq([ds.size, ds.get(drillKey("q0", 1)).lastOk, ds.get(drillKey("q0", 2)).lastOk], [2, true, false], "選択肢ごとの成績");
  ok(!statsByQuestion(mixed).has("q0#1") && statsByQuestion(mixed).get("q0").n === 1, "通常の成績に、一問一答の記録が入らない");
  // 未解答の優先度：よく出る論点＞区分＞直近
  const rare = mkq("rare", "S", [it(1, true, "pr", 1)]), common = mkq("common", "S", [it(1, true, "pc", 20)]), lowRank = mkq("lowRank", "B", [it(1, true, "pl", 20)]);
  const recentQ = mkq("recentQ", "S", [it(1, true, "prc", 5, 3)]), notRecent = mkq("notRecent", "S", [it(1, true, "pnr", 5, 0)]);
  eq(selectDrill([rare, common, lowRank, recentQ, notRecent], new Map(), { now: NOW }).picked.map((x) => x.q.id), ["common", "lowRank", "recentQ", "notRecent", "rare"], "未解答はよく出る論点から（同じ頻度なら、区分・直近の出題）");
  // 間違えた＞日がたった＞未解答
  const mix = mkq("mix", "A", [it(1, true, "m1", 2), it(2, true, "m2", 2), it(3, true, "m3", 2), it(4, true, "m4", 30)]);
  const stm = drillStats([da("mix", 1, false, 2), da("mix", 2, true, 40)]);
  eq(selectDrill([mix], stm, { now: NOW }).picked.map((x) => x.item.n), [1, 2, 4, 3], "選択肢ごとに、間違えた→日がたった→未解答");
  eq(selectDrill([mix], stm, { now: NOW }).counts, { wrong: 1, due: 1, unsolved: 2 }, "分類の件数");
  // 同じ論点は、1回に1問まで
  const same = mkq("same", "S", [it(1, true, "dup", 9), it(2, false, "dup", 9), it(3, true, "other", 1)]);
  const sd = selectDrill([same, mkq("same2", "S", [it(1, true, "dup", 9)])], new Map(), { now: NOW }).picked;
  eq(sd.map((x) => x.item.point).sort(), ["dup", "other"], "同じ論点は1回に1問");
  // 区分 C・D の切り替えは、未解答だけに効く
  const qd = mkq("qd", "D", [it(1, true, "pd", 5)]), qc = mkq("qc", "C", [it(1, true, "pcc", 5)]);
  eq(selectDrill([qd, qc], new Map(), { now: NOW }).picked.map((x) => x.q.id), ["qc"], "D は既定で出さない");
  eq(selectDrill([qd, qc], new Map(), { now: NOW, includeD: true, includeC: false }).picked.map((x) => x.q.id), ["qd"], "切り替え");
  eq(selectDrill([qd], drillStats([da("qd", 1, false, 3)]), { now: NOW }).picked.length, 1, "D でも、間違えた選択肢は出す");
  eq(selectDrill([mkq("n", "S", [])], new Map(), { now: NOW }).picked, [], "選択肢がなくても落ちない");
  eq(selectDrill([{ id: "nodrill", exam: "x", num: 1, rank: "S", drill: null }], new Map(), { now: NOW }).picked, [], "drill が null の問題は飛ばす");
  eq(classifyDrill(mkq("z", "S", [it(1, true, "z", null)]), { n: 1, count: null, recent: null, point: "z" }, undefined, NOW).bucket, 3, "count が null でも落ちない");
  // 間違えが多いときも、未解答を最低2問混ぜる
  const wrongQs = Array.from({ length: 12 }, (_, i) => mkq("w" + i, "S", [it(1, true, "pw" + i, 5)]));
  const stw = drillStats(wrongQs.map((q, i) => da(q.id, 1, false, 1 + i)));
  const freshQ = [mkq("f1", "S", [it(1, true, "pf1", 9)]), mkq("f2", "S", [it(1, true, "pf2", 8)]), mkq("f3", "S", [it(1, true, "pf3", 1)])];
  const rw2 = selectDrill([...wrongQs, ...freshQ], stw, { now: NOW });
  eq([rw2.picked.length, rw2.picked.filter((x) => x.q.id.startsWith("f")).length], [SESSION_SIZE, 2], "未解答を2問混ぜる");
  const sm = drillSummary([da("a", 1, true, 3), da("a", 1, false, 2), da("a", 2, true, 1), { ...da("b", null, true, 1), choice_n: null, mode: "exam" }]);
  eq([sm.solved, sm.n, sm.correct], [2, 3, 2], "一問一答の集計（通常の記録は数えない）");
}

// --- 一問一答：選択肢が語句・式だけの問（drill.phrase）。問題文を出し、「この問の正答か」を isAnswer で判定する
{
  const base = { subject: "hourei", subjectName: "労働衛生関係法令", exam: "2024-08", examLabel: "2024年度 第1回", num: 3, rank: "A", rankLabel: "得点必須A", url: "/q/x/", books: [], figures: [], choiceNotes: [] };
  // 「選任が規定されていないものはどれか」：正答は (2)。語句そのものは、どれも「正しい記述／誤った記述」とは言えない
  const pq = { ...base, id: "2024-08-hourei-03", answer: ["2"], stemHtml: "<p>次の作業のうち、法令上、作業主任者の選任が規定されていないものはどれか。</p>",
    choices: ["酸素欠乏危険場所における作業", "ＶＤＴ作業", "特定化学物質を取り扱う作業"],
    drill: { denom: 23, phrase: true, items: [
      { n: 1, truth: true, isAnswer: false, point: "p1", pointName: "酸素欠乏危険作業には、作業主任者の選任が必要", count: 4, recent: 1 },
      { n: 2, truth: false, isAnswer: true, point: "p2", pointName: "ＶＤＴ作業には、作業主任者の選任の規定がない", count: 2, recent: 0 },
      { n: 3, truth: true, isAnswer: false, point: "p3", pointName: "特定化学物質の取扱いには、作業主任者の選任が必要", count: 5, recent: 2 }] } };
  const nq = { ...base, id: "2024-08-hourei-04", answer: ["1"], stemHtml: "<p>次の記述のうち、誤っているものはどれか。</p>", choices: ["誤った記述の文。", "正しい記述の文。"],
    drill: { denom: 23, phrase: false, items: [{ n: 1, truth: false, isAnswer: true, point: "q1", pointName: "論点A", count: 1, recent: 0 }, { n: 2, truth: true, isAnswer: false, point: "q2", pointName: "論点B", count: 1, recent: 0 }] } };
  eq([isPhraseDrill(pq), isPhraseDrill(nq), isPhraseDrill({ drill: { items: [] } }), isPhraseDrill({ drill: null })], [true, false, false, false], "phrase の判定（項目がない古いデータは false）");
  // 判定：語句の問は isAnswer、ふつうの問は truth（isAnswer があっても使わない）
  eq(pq.drill.items.map((it) => drillExpected(pq, it)), [false, true, false], "語句の問は isAnswer で判定（truth とは逆のこともある）");
  eq(nq.drill.items.map((it) => drillExpected(nq, it)), [false, true], "ふつうの問は truth で判定（isAnswer は使わない）");
  const u = () => "u";
  eq(makeDrillAttempt(pq, pq.drill.items[1], true, new Date("2026-11-10T00:00:00Z"), u), { id: "u", question_id: "2024-08-hourei-03", choice_n: 2, mode: "drill", selected: "true", is_correct: true, answered_at: "2026-11-10T00:00:00.000Z" }, "「正答」と答えて、実際に正答→正解（記録の形は同じ）");
  eq([makeDrillAttempt(pq, pq.drill.items[0], true, new Date(), u).is_correct, makeDrillAttempt(pq, pq.drill.items[0], false, new Date(), u).is_correct], [false, true], "正答でない選択肢：「正答」は不正解、「正答ではない」は正解");
  eq(makeDrillAttempt(nq, nq.drill.items[0], false, new Date(), u).is_correct, true, "ふつうの問は、これまでどおり");
  // isAnswer がないデータでは、問題の正答から求める
  const old = { ...pq, drill: { ...pq.drill, items: pq.drill.items.map(({ isAnswer, ...r }) => r) } };
  eq(old.drill.items.map((it) => drillExpected(old, it)), [false, true, false], "isAnswer がなければ、問題の正答（answer）から求める");
  // 表示：問題文が、折りたたみではなく、見える位置にある。ボタンの文言。論点は出さない
  const h = renderDrill(pq, pq.drill.items[0], { base: "/sokuteishi/", index: 1, total: 3 });
  ok(h.includes("作業主任者の選任が規定されていないものはどれか") && !h.includes("<details"), "語句の問：問題文を、開いた状態で出す");
  ok(h.indexOf("規定されていないものはどれか") < h.indexOf("酸素欠乏危険場所における作業"), "語句の問：問題文が、選択肢より上");
  ok(h.includes("正答（これが答え）") && h.includes("正答ではない") && !h.includes(">正しい（1）") && !h.includes(">誤り（2）"), "語句の問：ボタンは「正答／正答ではない」");
  ok(h.includes('id="p-true"') && h.includes('id="p-false"'), "語句の問：ボタンの id は同じ（キー操作が同じに働く）");
  ok(!h.includes("論点：") && !h.includes(pq.drill.items[0].pointName), "語句の問：答える前に、論点を出さない");
  const hn = renderDrill(nq, nq.drill.items[0], { base: "/sokuteishi/", index: 1, total: 2 });
  ok(hn.includes(">正しい（1）") && hn.includes("<details") && !hn.includes("正答（これが答え）"), "ふつうの問：これまでどおり（問題文は折りたたみ、ボタンは「正しい／誤り」）");
  // 結果の文言
  const r1 = renderDrillResult(pq, pq.drill.items[1], { base: "/sokuteishi/", ok: true, judged: true, expected: true });
  ok(r1.includes("この選択肢は<b>この問題の正答</b>です") && r1.includes("論点："), "語句の問：結果の文言（正答）");
  const r2 = renderDrillResult(pq, pq.drill.items[0], { base: "/sokuteishi/", ok: false, judged: true, expected: false });
  ok(r2.includes("あなたの答え：正答") && r2.includes("この問題の正答ではない選択肢") && !r2.includes("正しい記述") && !r2.includes("誤った記述"), "語句の問：結果の文言（正答ではない）。「正しい記述／誤った記述」とは言わない");
  const r3 = renderDrillResult(nq, nq.drill.items[0], { base: "/sokuteishi/", ok: true, judged: false, expected: false });
  ok(r3.includes("この記述は<b>誤った記述</b>です"), "ふつうの問：結果の文言は、これまでどおり");
  ok(renderDrillResult(nq, nq.drill.items[1], { base: "/sokuteishi/", ok: true, judged: true }).includes("正しい記述"), "expected を省いたときは、truth を使う");
}

// --- 一問一答の成績（選択肢の数で数える）
{
  const it = (n, truth) => ({ n, truth, point: "p" + n, pointName: "x", count: 1, recent: 0 });
  const mq = (id, subject, rank, ch, ns) => ({ id, subject, rank, chapters: ch, exam: "e", num: 1, drill: ns ? { denom: 23, items: ns.map((n) => it(n, true)) } : null });
  const qsd = [mq("a", "ippan", "S", ["c1", "c2"], [1, 2, 3, 4, 5]), mq("b", "ippan", "A", ["c1"], [1, 2]), mq("c", "hourei", "S", ["c3"], [1, 2, 3]), mq("t", "ippan", "S", ["c1"], null)];
  const D = (id, n, ok, t) => ({ id: `${id}${n}${t}`, question_id: id, choice_n: n, mode: "drill", selected: "true", is_correct: ok, answered_at: t });
  const att = [D("a", 1, true, "2026-11-01"), D("a", 1, false, "2026-11-02"), D("a", 2, true, "2026-11-01"), D("b", 1, false, "2026-11-01"),
    { id: "n", question_id: "a", choice_n: null, mode: "exam", selected: "1", is_correct: true, answered_at: "2026-11-03" }];
  const ag = aggregateDrill(qsd, drillStats(att));
  const g = (arr, k) => arr.find((x) => x.key === k);
  eq([g(ag.bySubject, "ippan").total, g(ag.bySubject, "ippan").solved, g(ag.bySubject, "ippan").n, g(ag.bySubject, "ippan").correct], [7, 3, 4, 2], "科目別：全選択肢7（drill のない問題は数えない）、解いた3肢、延べ4回、正解2");
  eq(g(ag.bySubject, "ippan").latestAcc, 1 / 3, "直近の正解率（a#1 は最新が誤り、a#2 は正解、b#1 は誤り）");
  eq([g(ag.bySubject, "hourei").total, g(ag.bySubject, "hourei").solved, g(ag.bySubject, "hourei").acc], [3, 0, null], "解いていない科目");
  eq([g(ag.byRank, "S").total, g(ag.byRank, "S").solved, g(ag.byRank, "A").solved], [8, 2, 1], "区分別");
  eq([g(ag.byChapter, "c1").total, g(ag.byChapter, "c1").solved], [7, 3], "章別（先頭の章だけ）");
  ok(!ag.byChapter.some((x) => x.key === "c2"), "2番目以降の章は数えない");
  eq(weakChapters(ag.byChapter, { min: 3 }).map((r) => r.key), ["c1"], "弱い章");
  eq(aggregate(qsd, statsByQuestion(att)).bySubject.find((x) => x.key === "ippan").solved, 1, "五肢択一の成績には、一問一答の記録が入らない");
  eq(aggregateDrill([], new Map()).bySubject.length, 0, "空でも落ちない");
}

// --- 成績
{
  eq(subjectOfId("2024-02-hourei-01"), "hourei", "問題IDから科目");
  const mkq = (id, subject, rank, ch) => ({ id, subject, rank, chapters: ch, exam: "e", num: 1 });
  const qs3 = [mkq("a", "ippan", "S", ["c1", "c2"]), mkq("b", "ippan", "S", ["c1"]), mkq("c", "hourei", "A", ["c3"]), mkq("d", "hourei", "A", []), mkq("e", "ippan", "B", ["c1"])];
  const A2 = (id, ok, t) => ({ id: id + t, question_id: id, choice_n: null, mode: "exam", selected: "1", is_correct: ok, answered_at: t });
  const st3 = statsByQuestion([A2("a", true, "2026-11-01"), A2("a", false, "2026-11-02"), A2("b", true, "2026-11-01"), A2("c", false, "2026-11-01")]);
  const ag = aggregate(qs3, st3);
  const g = (arr, k) => arr.find((x) => x.key === k);
  eq([g(ag.bySubject, "ippan").total, g(ag.bySubject, "ippan").solved, g(ag.bySubject, "ippan").n, g(ag.bySubject, "ippan").correct], [3, 2, 3, 2], "科目別の数");
  eq(Math.round(g(ag.bySubject, "ippan").acc * 100), 67, "通算の正答率");
  eq(g(ag.bySubject, "ippan").latestAcc, 0.5, "直近の正解率（a は最新が誤り、b は正解）");
  eq([g(ag.byRank, "S").solved, g(ag.byRank, "A").solved, g(ag.byRank, "B").solved, g(ag.byRank, "B").acc], [2, 1, 0, null], "区分別");
  eq(g(ag.byChapter, "c1").total, 3, "章は先頭の章だけに数える（c2 は数えない）");
  ok(!ag.byChapter.some((x) => x.key === "c2"), "2番目以降の章は数えない");
  eq(weakChapters(ag.byChapter, { min: 2 }).map((r) => r.key), ["c1"], "弱い章（解いた数の下限）");
  const rows = [{ key: "x", solved: 6, n: 10, acc: 0.8 }, { key: "y", solved: 9, n: 12, acc: 0.5 }, { key: "z", solved: 5, n: 5, acc: 0.5 }, { key: "w", solved: 3, n: 3, acc: 0 }];
  eq(weakChapters(rows).map((r) => r.key), ["y", "z", "x"], "弱い章の並び（正答率→解答数。解いた数が少ない章は除く）");
  const ep = aggregate([], new Map()); eq([ep.bySubject.length, ep.byChapter.length], [0, 0], "空でも落ちない");
}

// --- 保存層（localStorage 版。node ではメモリ上の代用品）
const mem = new Map();
const fake = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, v), removeItem: (k) => mem.delete(k) };
const store = createLocalStore(fake);
await store.add(at); await store.add({ ...at, id: "uuid-2" });
eq((await store.load()).length, 2, "保存→読み込み");
mem.set("sokuteishi.practice.v1", "{壊れたデータ");
eq(await store.load(), [], "壊れたデータでも落ちない");
await store.removeAll();
eq(await store.load(), [], "全削除");


// --- クラウド保存（偽の Supabase クライアントで試す。本物の接続は、運営者が実機で確かめる）
function fakeClient(rows = [], opt = {}) {
  return {
    rows, calls: [],
    from(t) {
      if (t !== "attempts") throw new Error("想定外のテーブル " + t);
      return {
        select: () => ({ order() { return this; }, range: (a, b) => Promise.resolve({ data: rows.slice(a, b + 1), error: null }) }),
        upsert: (list, o) => {
          if (opt.full) return Promise.resolve({ error: { message: "new row violates row-level security policy", code: "42501" } });
          if (opt.failInsert) return Promise.resolve({ error: { message: "network" } });
          if (!o || o.onConflict !== "id" || o.ignoreDuplicates !== true) return Promise.resolve({ error: { message: "重複を無視する指定がない" } });
          for (const r of list) { if ("user_id" in r) return Promise.resolve({ error: { message: "user_id を送ってはいけない" } }); if (!rows.some((x) => x.id === r.id)) rows.push(r); }
          return Promise.resolve({ error: null });
        },
        delete: () => ({
          not: () => { rows.length = 0; return Promise.resolve({ error: null }); },
          in: (col, ids) => { if (opt.failDelete) return Promise.resolve({ error: { message: "x" } }); for (const id of ids) { const i = rows.findIndex((r) => r[col] === id); if (i >= 0) rows.splice(i, 1); } return Promise.resolve({ error: null }); },
        }),
      };
    },
  };
}
const A = (id, t = "2026-11-01T00:00:00.000Z") => ({ id, question_id: "q", choice_n: null, mode: "exam", selected: "1", is_correct: true, answered_at: t });
{
  const big = Array.from({ length: PAGE * 2 + 5 }, (_, i) => A("id" + i));
  eq((await fetchAll(fakeClient(big))).length, PAGE * 2 + 5, "ページをまたいで全件読む");
  eq((await fetchAll(fakeClient(Array.from({ length: PAGE }, (_, i) => A("x" + i))))).length, PAGE, "ちょうど1ページ分でも止まる");
  const c0 = fakeClient([]); await insertMany(c0, Array.from({ length: 1201 }, (_, i) => A("n" + i))); eq(c0.rows.length, 1201, "500件ずつに分けて書く");
}
{
  // ログイン→取り込み：端末の3件のうち1件は、クラウドにもある（重複しない）。成功したら端末側は空に。
  const mem2 = new Map(); const st2 = { getItem: (k) => (mem2.has(k) ? mem2.get(k) : null), setItem: (k, v) => mem2.set(k, v), removeItem: (k) => mem2.delete(k) };
  const local = createLocalStore(st2); const s = createStore(local);
  for (const id of ["a", "b", "c"]) await s.add(A(id));
  eq(s.kind, "local", "未ログインは local");
  const cloud = fakeClient([A("b")]);
  s.setUser(cloud, "u1");
  const r = await s.syncAfterLogin();
  eq([r.imported, r.error, cloud.rows.length], [3, null, 3], "取り込み（重複なし）");
  eq((await local.load()).length, 0, "取り込み後、端末側は空");
  eq((await s.load()).map((x) => x.id).sort(), ["a", "b", "c"], "ログイン中の読み込み");
  eq(await s.add(A("d")), "cloud", "ログイン中の追加はクラウドへ");
  // 通信できないとき：端末に溜め、読み込みでは見え、つながったら送られる
  const bad = fakeClient(cloud.rows.slice(), { failInsert: true }); s.setUser(bad, "u1");
  eq(await s.add(A("e")), "pending", "送れなければ未送信に溜める");
  eq(await s.pendingCount(), 1, "未送信は1件");
  eq((await s.load()).some((x) => x.id === "e"), true, "未送信の分も、読み込みに含まれる");
  const good = fakeClient(cloud.rows.slice()); s.setUser(good, "u1");
  const r2 = await s.syncAfterLogin();
  eq([r2.flushed, await s.pendingCount(), good.rows.some((x) => x.id === "e")], [1, 0, true], "つながったら未送信を送る");
  // 取り込みに失敗したら、端末側の記録は消さない
  s.clearUser(); await s.add(A("z"));
  s.setUser(fakeClient([], { failInsert: true }), "u2");
  const r3 = await s.syncAfterLogin();
  eq([!!r3.error, (await local.load()).length], [true, 1], "取り込み失敗では、端末の記録を消さない");
  // 記録の削除
  const c4 = fakeClient([A("p")]); s.setUser(c4, "u3"); await s.removeAll();
  eq(c4.rows.length, 0, "ログイン中の全削除（クラウド）");
  // 別のユーザーの未送信は混ざらない
  s.clearUser();
}

// --- 記録の間引き（同じ問題・同じ選択肢は、最新10件まで）
{
  const T = (i) => new Date(Date.UTC(2026, 0, 1) + i * 3600000).toISOString();
  const N = (i, qid = "q", mode = "exam") => ({ id: `${qid}-${mode}-${i}`, question_id: qid, choice_n: null, mode, selected: "1", is_correct: true, answered_at: T(i) });
  const Dr = (i, qid, n) => ({ id: `${qid}#${n}-${i}`, question_id: qid, choice_n: n, mode: "drill", selected: "true", is_correct: true, answered_at: T(i) });
  eq(KEEP_PER_KEY, 10, "残す件数の既定値");
  const ten = Array.from({ length: 10 }, (_, i) => N(i));
  eq(pruneIds(ten, ten[9]), [], "10件までは消さない");
  const eleven = [...ten, N(10, "q", "review")];
  eq(pruneIds(eleven, eleven[10]), ["q-exam-0"], "11件目で、いちばん古い1件を消す（演習と復習は、同じ問題として数える）");
  const many = Array.from({ length: 14 }, (_, i) => N(i));
  eq(pruneIds(many, many[13]).sort(), ["q-exam-0", "q-exam-1", "q-exam-2", "q-exam-3"], "たまっていた分は、まとめて消す");
  // 別の問題・一問一答の記録は、巻き込まない
  const mix = [...Array.from({ length: 11 }, (_, i) => N(i, "q")), ...Array.from({ length: 11 }, (_, i) => N(i, "other")), ...Array.from({ length: 11 }, (_, i) => Dr(i, "q", 1)), ...Array.from({ length: 3 }, (_, i) => Dr(i, "q", 2))];
  eq(pruneIds(mix, N(10, "q")), ["q-exam-0"], "同じ問題の、通常の記録だけ");
  eq(pruneIds(mix, Dr(10, "q", 1)), ["q#1-0"], "一問一答は、同じ選択肢だけ");
  eq(pruneIds(mix, Dr(2, "q", 2)), [], "別の選択肢は、数えない");
  eq(pruneIds(eleven, eleven[10], 3).length, 8, "残す件数を変えられる");
  // 保存層：端末の記録から消す／クラウドから消す／上限のとき
  const mem3 = new Map(); const st3 = { getItem: (k) => (mem3.has(k) ? mem3.get(k) : null), setItem: (k, v) => mem3.set(k, v), removeItem: (k) => mem3.delete(k) };
  const s3 = createStore(createLocalStore(st3));
  for (const a of ten) await s3.add(a);
  await s3.remove(["q-exam-0", "q-exam-1"]);
  eq((await s3.load()).length, 8, "端末の記録の間引き");
  const cl = fakeClient(ten.map((a) => ({ ...a })));
  s3.setUser(cl, "u9");
  await s3.remove(["q-exam-2", "nothing"]);
  eq(cl.rows.length, 9, "クラウドの記録の間引き（ない id は無視）");
  await deleteByIds(cl, Array.from({ length: 250 }, (_, i) => "x" + i)); eq(cl.rows.length, 9, "100件ずつに分けても落ちない");
  s3.setUser(fakeClient([], { full: true }), "u9");
  eq([await s3.add(N(99)), await s3.pendingCount()], ["full", 0], "上限に達したら、保存せず、未送信にも溜めない");
  s3.setUser(fakeClient([], { failInsert: true }), "u9");
  eq(await s3.add(N(98)), "pending", "通信の失敗は、これまでどおり未送信に溜める");
}

// --- リンク
eq(fixLinks('<a href="/q/x/">a</a>', "/sokuteishi/"), '<a target="_blank" rel="noopener" href="/sokuteishi/q/x/">a</a>', "リンクの書き換え");

// --- 全問題の走査（_site/data があるとき）
const dir = new URL("../_site/data/", import.meta.url);
if (fs.existsSync(new URL("meta.json", dir))) {
  const meta = JSON.parse(fs.readFileSync(new URL("meta.json", dir)));
  const c = { q: 0, table: 0, fig: 0, math: 0, all: 0, multi: 0, drillNull: 0, drill: 0, phrase: 0, isAnswer: 0 };
  for (const s of meta.subjects) {
    for (const q of JSON.parse(fs.readFileSync(new URL(`${s.id}.json`, dir)))) {
      c.q++;
      const html = renderQuestion(q, { base: "/sokuteishi/", index: 1, total: 1 });
      const n = q.columns ? q.choiceCells.length : q.choices.length;
      const inputs = (html.match(/<input type="(radio|checkbox)"/g) || []).length;
      ok(inputs === n && n >= 2, `${q.id}：選択肢の数 ${inputs}/${n}`);
      ok(!q.columns || (html.match(/<tr data-n=/g) || []).length === n, `${q.id}：表の行数`);
      ok(!/undefined|\[object/.test(html), `${q.id}：未定義の値が出ている`);
      ok(html.includes("出典："), `${q.id}：出典がない`);
      ok((q.figures || []).every((f) => html.includes(`/sokuteishi${f.src}`)), `${q.id}：図の src`);
      const multi = q.answer.length > 1;
      ok(multi === html.includes('type="checkbox"'), `${q.id}：複数正答の入力方式`);
      for (const okv of [true, false]) {
        const r = renderResult(q, { base: "/sokuteishi/", ok: okv });
        ok(!/undefined|\[object/.test(r), `${q.id}：結果に未定義の値`);
        ok(!/href="\/(?!sokuteishi)/.test(r), `${q.id}：公開フォルダが付いていないリンク`);
        ok(!/<a (?![^>]*target="_blank")/.test(r), `${q.id}：新しいタブで開かないリンク`);
      }
      ok(gradeAnswer(q, [q.answer[0] === "all" ? "1" : q.answer[0]]) !== undefined, `${q.id}：採点`);
      if (q.drill) {
        const phrase = isPhraseDrill(q);
        if (phrase) {   // 選択肢が語句・式だけの問：問題文があり、正答の印が、問題の正答と合っていること
          c.phrase++;
          ok(!!q.stemHtml, `${q.id}：語句の問なのに、問題文がない`);
          ok(q.drill.items.every((it) => typeof it.isAnswer === "boolean"), `${q.id}：語句の問なのに、isAnswer がない選択肢がある`);
          const ans = q.answer.map(String);
          ok(q.answer[0] === "all" || q.drill.items.every((it) => it.isAnswer === ans.includes(String(it.n))), `${q.id}：isAnswer が、問題の正答（${q.answer}）と合わない`);
        }
        for (const item of q.drill.items) {
          c.drill++;
          if (typeof item.isAnswer === "boolean") c.isAnswer++;
          if (phrase) {
            const hp = renderDrill(q, item, { base: "/sokuteishi/", index: 1, total: 1 });
            ok(hp.includes("正答（これが答え）") && !hp.includes("<details") && hp.includes("pstem-open"), `${q.id}#${item.n}：語句の問の表示（問題文・ボタン）`);
            ok(drillExpected(q, item) === item.isAnswer, `${q.id}#${item.n}：語句の問の判定が isAnswer でない`);
          } else {
            ok(drillExpected(q, item) === item.truth, `${q.id}#${item.n}：ふつうの問の判定が truth でない`);
          }
          const h = renderDrill(q, item, { base: "/sokuteishi/", index: 1, total: 1 });
          ok(!/undefined|\[object/.test(h), `${q.id}#${item.n}：一問一答の表示に未定義の値`);
          // 見えている部分から、出題する記述そのもの（論点の名前と同じ文のことが多い）と、折りたたんだ問題文を除く
          const visible = h.replace(/<div class="pstatement">[\s\S]*?(?=<details|<div class="pjudge")/, "").replace(/<details[\s\S]*?<\/details>/, "");
          ok(!visible.includes(esc(item.pointName)), `${q.id}#${item.n}：答える前に、論点の名前が出ている`);
          ok(h.includes('id="p-true"') && h.includes('id="p-false"') && h.includes("pstatement"), `${q.id}#${item.n}：判定ボタンがない`);
          ok(!h.includes("論点："), `${q.id}#${item.n}：答える前に「論点：」が出ている`);
          for (const judged of [true, false]) {
            const r = renderDrillResult(q, item, { base: "/sokuteishi/", ok: judged === item.truth, judged });
            ok(!/undefined|\[object/.test(r), `${q.id}#${item.n}：結果に未定義の値`);
            ok(!/href="\/(?!sokuteishi)/.test(r) && !/<a (?![^>]*target="_blank")/.test(r), `${q.id}#${item.n}：リンク`);
            ok(r.includes("論点："), `${q.id}#${item.n}：答えたあとに論点がない`);
          }
          ok(typeof item.truth === "boolean" && q.choices[item.n - 1] !== undefined, `${q.id}#${item.n}：選択肢の本文がない`);
        }
      }
      if (q.columns) c.table++; if ((q.figures || []).length) c.fig++; if (/katex/.test(html)) c.math++;
      if (q.answer[0] === "all") c.all++; if (multi) c.multi++; if (!q.drill) c.drillNull++;
    }
  }
  console.log("走査：", JSON.stringify(c));
  console.log(c.phrase
    ? `語句・式だけの問（drill.phrase）：${c.phrase} 問を確認した（サイト側の連絡では 26 問。${c.phrase === 26 ? "一致" : "件数が違う。データが変わったか、確認する"}）。isAnswer のある選択肢：${c.isAnswer} / ${c.drill}`
    : "（このデータには、drill.phrase の問がない。サイト側の新しいデータでビルドしてから、もう一度実行する）");
} else console.log("（_site/data がないので、全問題の走査は省略。先に npm run build）");

console.log(fail ? `✗ ${fail} 件の失敗` : "✓ すべて成功");
process.exit(fail ? 1 : 0);
