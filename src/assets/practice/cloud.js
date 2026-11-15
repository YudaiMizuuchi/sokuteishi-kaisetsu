// クラウド（Supabase）の読み書き。client を引数に取るので、本物がなくても（偽物で）試せる。
export const PAGE = 1000;   // 読み込みの1回あたりの行数（Supabase の既定の上限に合わせる）
export const CHUNK = 500;   // 書き込みの1回あたりの行数
const COLS = "id,question_id,choice_n,mode,selected,is_correct,answered_at";

/** 自分の記録をすべて読む（RLS で、本人の行だけが返る） */
export async function fetchAll(client) {
  const rows = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await client.from("attempts").select(COLS)
      .order("answered_at", { ascending: true }).order("id", { ascending: true }).range(from, from + PAGE - 1);
    if (error) throw error;
    // 日時の書式を、端末側と同じ（…Z）にそろえる（データベースは …+00:00 の形で返すため、並べ替えがずれないように）
    rows.push(...data.map((r) => ({ ...r, answered_at: new Date(r.answered_at).toISOString() })));
    if (data.length < PAGE) break;
  }
  return rows;
}

/** 記録を書く。同じ id が既にあれば、何もしない（重複しない）。user_id は、サーバー側が本人にする。 */
export async function insertMany(client, list) {
  for (let i = 0; i < list.length; i += CHUNK) {
    const chunk = list.slice(i, i + CHUNK).map((a) => ({
      id: a.id, question_id: a.question_id, choice_n: a.choice_n ?? null, mode: a.mode,
      selected: String(a.selected), is_correct: !!a.is_correct, answered_at: a.answered_at,
    }));
    const { error } = await client.from("attempts").upsert(chunk, { onConflict: "id", ignoreDuplicates: true });
    if (error) throw error;
  }
}

/** id を指定して消す（間引き用） */
export async function deleteByIds(client, ids) {
  for (let i = 0; i < ids.length; i += 100) {
    const { error } = await client.from("attempts").delete().in("id", ids.slice(i, i + 100));
    if (error) throw error;
  }
}

/** 自分の記録をすべて消す */
export async function deleteAll(client) {
  const { error } = await client.from("attempts").delete().not("id", "is", null);
  if (error) throw error;
}
