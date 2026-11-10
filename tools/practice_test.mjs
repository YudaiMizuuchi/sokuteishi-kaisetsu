// 演習機能のテスト（node tools/practice_test.mjs）。ビルド後（_site/data があるとき）は、全問題の描画も走査する。
import fs from "node:fs";
import { gradeAnswer, makeAttempt, statsByQuestion, matches, orderQuestions, summarize, classify, selectReview, aggregate, weakChapters, subjectOfId, INTERVAL_DAYS, SESSION_SIZE } from "../src/assets/practice/logic.js";
import { renderQuestion, renderResult, fixLinks } from "../src/assets/practice/render.js";
import { createLocalStore, createStore } from "../src/assets/practice/store.js";
import { fetchAll, insertMany, deleteAll, PAGE } from "../src/assets/practice/cloud.js";

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
          if (opt.failInsert) return Promise.resolve({ error: { message: "network" } });
          if (!o || o.onConflict !== "id" || o.ignoreDuplicates !== true) return Promise.resolve({ error: { message: "重複を無視する指定がない" } });
          for (const r of list) { if ("user_id" in r) return Promise.resolve({ error: { message: "user_id を送ってはいけない" } }); if (!rows.some((x) => x.id === r.id)) rows.push(r); }
          return Promise.resolve({ error: null });
        },
        delete: () => ({ not: () => { rows.length = 0; return Promise.resolve({ error: null }); } }),
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

// --- リンク
eq(fixLinks('<a href="/q/x/">a</a>', "/sokuteishi/"), '<a target="_blank" rel="noopener" href="/sokuteishi/q/x/">a</a>', "リンクの書き換え");

// --- 全問題の走査（_site/data があるとき）
const dir = new URL("../_site/data/", import.meta.url);
if (fs.existsSync(new URL("meta.json", dir))) {
  const meta = JSON.parse(fs.readFileSync(new URL("meta.json", dir)));
  const c = { q: 0, table: 0, fig: 0, math: 0, all: 0, multi: 0, drillNull: 0 };
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
      if (q.columns) c.table++; if ((q.figures || []).length) c.fig++; if (/katex/.test(html)) c.math++;
      if (q.answer[0] === "all") c.all++; if (multi) c.multi++; if (!q.drill) c.drillNull++;
    }
  }
  console.log("走査：", JSON.stringify(c));
} else console.log("（_site/data がないので、全問題の走査は省略。先に npm run build）");

console.log(fail ? `✗ ${fail} 件の失敗` : "✓ すべて成功");
process.exit(fail ? 1 : 0);
