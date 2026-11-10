// 問題の描画（文字列を返す。DOM に触れないので、node で全問題を走査して試せる）
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const withBase = (base, p) => base.replace(/\/$/, "") + p;

/** サイト内の "/…" のリンクに公開フォルダを付け、新しいタブで開くようにする（演習の画面を残すため） */
export function fixLinks(html, base) {
  return String(html || "")
    .replace(/href="\//g, `href="${base.replace(/\/$/, "")}/`)
    .replace(/<a /g, '<a target="_blank" rel="noopener" ');
}

export const isMulti = (q) => (q.answer || []).length > 1;

/** 問題文＋選択肢（答える前の状態）。選択肢は、1つなら選択ボタン、正答が複数ならチェックボックス。 */
export function renderQuestion(q, { base, index, total }) {
  const multi = isMulti(q);
  const type = multi ? "checkbox" : "radio";
  const input = (n) => `<input type="${type}" name="choice" value="${n}" id="c-${n}">`;
  const figs = (q.figures || []).map((f) => `<figure class="fig"><img src="${withBase(base, f.src)}" alt="${esc(f.alt)}" loading="lazy"></figure>`).join("");
  let choices;
  if (q.columns) {
    choices = `<div class="choice-table-wrap"><table class="choices choice-table pchoices-table"><thead><tr><th></th>${q.columns.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${
      q.choiceCells.map((row, i) => `<tr data-n="${i + 1}"><th scope="row" class="n"><label for="c-${i + 1}">${input(i + 1)} (${i + 1})</label></th>${row.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  } else {
    choices = `<ol class="pchoices">${(q.choices || []).map((c, i) => `<li data-n="${i + 1}"><label for="c-${i + 1}">${input(i + 1)}<span class="n">(${i + 1})</span><span class="ctext">${c}</span></label></li>`).join("")}</ol>`;
  }
  const body = q.stemHtml
    ? `<div class="qtext">${q.stemHtml}</div>${figs}<fieldset class="pfield"><legend class="sr-only">選択肢${multi ? "（正答は複数あります。すべて選んでください）" : ""}</legend>${multi ? `<p class="hint">正答は複数あります。すべて選んでください。</p>` : ""}${choices}</fieldset>`
    : `<p class="source">問題文と選択肢は<a href="${esc(q.sourcePdf)}" target="_blank" rel="noopener">公式の公表試験問題（PDF）</a>でご確認ください。</p>`;
  return `<article class="q pq" data-id="${esc(q.id)}">
    <div class="qmeta"><span class="pprog">${index} / ${total}</span><span>${esc(q.examLabel)}（${esc(q.held)}）</span><span class="subj">${esc(q.subjectName)}</span>${q.rank ? `<span class="rank rank-${q.rank}" title="過去の出題頻度から見た、この問題の区分">${esc(q.rankLabel || "")}</span>${q.method ? `<span class="method">${esc(q.method)}</span>` : ""}` : ""}</div>
    <h2 class="qtitle">問${q.num}</h2>
    ${body}
    <div class="pactions"><button type="button" class="reveal-like" id="p-check" disabled>答え合わせ</button><span class="hint" id="p-hint">選択肢を選んでください（数字キーでも選べます）</span></div>
    <div id="p-result" aria-live="polite"></div>
    ${q.stemHtml ? `<p class="credit">出典：${esc(q.source)}</p>` : ""}
  </article>`;
}

const ansText = (q) => (q.answer[0] === "all" ? "全員正解" : q.answer.map((a) => `(${a})`).join("・"));

/** 答え合わせの後に出す部分（正誤・正答・解説・注記・リンク） */
export function renderResult(q, { base, ok }) {
  const verdict = ok === null
    ? `<p class="pverdict pv-none">この問題は、正答が公表されていないため、採点しません。</p>`
    : q.answer[0] === "all"
      ? `<p class="pverdict pv-ok">✓ 全員正解の問題です。</p>`
      : ok ? `<p class="pverdict pv-ok">✓ 正解です。正答 <b>${ansText(q)}</b></p>`
           : `<p class="pverdict pv-ng">✗ 不正解です。正答 <b>${ansText(q)}</b></p>`;
  const notes = (q.choiceNotes || []).length
    ? `<ol class="notes">${q.choiceNotes.map((n, i) => `<li${n.isAnswer ? ' class="is-answer"' : ""}><span class="n">(${i + 1})</span><span>${fixLinks(n.html, base)}</span></li>`).join("")}</ol>` : "";
  const tags = (q.chapters || []).length
    ? `<div class="tags"><span class="tags-l">参考書の章：</span>${q.chapterLabels.slice(0, 3).map((l, i) => `<a class="tag" href="${withBase(base, `/chapter/${q.chapters[i]}/`)}" target="_blank" rel="noopener">${esc(l)}</a>`).join("")}</div>` : "";
  const books = (q.books || []).length
    ? `<div class="review">${q.books.map((b) => `<a class="book-link" href="${withBase(base, b.url)}" target="_blank" rel="noopener">参考書「${esc(b.label)}」で復習する<span class="ext" aria-label="（新しいタブで開きます）">↗</span></a>`).join("")}</div>` : "";
  const pageLink = `<p class="plink"><a href="${withBase(base, q.url)}" target="_blank" rel="noopener">この問題の解説ページを開く<span class="ext" aria-label="（新しいタブで開きます）">↗</span></a></p>`;
  return `${verdict}<div class="answer">
    ${q.textNote ? `<p class="lawnote">原文について：${esc(q.textNote)}</p>` : ""}${q.examNote ? `<p class="lawnote">協会の注記：${esc(q.examNote)}</p>` : ""}${q.lawNote ? `<p class="lawnote">法改正に関する注意：${esc(q.lawNote)}</p>` : ""}
    ${q.hasExplanation ? q.explanationHtml : `<p class="hint">この問題には、まだ解説がありません。</p>`}
    ${q.reviewNote ? `<p class="review-note"><b>現在、管理者にて確認中</b>${esc(q.reviewNote)}</p>` : ""}${q.minorNote ? `<p class="minor-note"><b>細かい論点なので、深追いは禁物です。</b>${esc(q.minorNote)}</p>` : ""}
    ${notes}${q.freqHtml ? fixLinks(q.freqHtml, base) : ""}${tags}${books}${pageLink}
  </div>`;
}
