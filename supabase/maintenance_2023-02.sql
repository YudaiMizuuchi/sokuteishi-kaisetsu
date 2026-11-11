-- 任意の保守用 SQL：令和4年度第2回（2023-02）の共通4科目・80問の、差し替えより前の記録を、全員分まとめて消す。
-- 背景：2026年11月11日に、この80問の中身（問題文・選択肢・正答）を差し替えた。問題IDは同じなので、以前の記録は、別の問題に対する記録になっている。
-- 実行しなくても、画面側が、各利用者が次に開いたときに、本人の分を自動で外して消す。この SQL は、開かない利用者の分も含めて、先に片付けたいときに使う。
-- Supabase の SQL Editor で実行する。1 を実行して件数を見てから、2 を実行する。

-- 1. 消える件数の確認（消さない）
select count(*) as 消える行数, count(distinct user_id) as 利用者数
from public.attempts
where question_id ~ '^2023-02-(ippan|hourei|design|bunseki)-[0-9]+$'
  and answered_at < timestamptz '2026-11-12 00:00:00+09';

-- 2. 削除（元に戻せない）
delete from public.attempts
where question_id ~ '^2023-02-(ippan|hourei|design|bunseki)-[0-9]+$'
  and answered_at < timestamptz '2026-11-12 00:00:00+09';
