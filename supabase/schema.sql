-- 過去問演習：解答の記録（利用者ごと）。Supabase の SQL Editor に貼り付けて、1回だけ実行する。
-- 何度実行しても壊れないように、if not exists／drop policy if exists を使っている。
-- 問題データは、ここに入れない（サイトの静的 JSON を使う）。入れるのは、解答の記録だけ。

create table if not exists public.attempts (
  id          uuid primary key default gen_random_uuid(),            -- 端末で作った uuid を、そのまま使う（再送・取り込みの重複を防ぐ）
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  question_id text not null check (char_length(question_id) <= 40),  -- 例 2024-02-hourei-01
  choice_n    smallint check (choice_n between 1 and 20),            -- 通常の問題は null、一問一答は選択肢番号
  mode        text not null check (mode in ('exam', 'review', 'drill')),
  selected    text not null check (char_length(selected) <= 20),     -- 通常：選んだ番号（"1,3"）／一問一答："true" か "false"
  is_correct  boolean not null,
  answered_at timestamptz not null default now()
);

create index if not exists attempts_user_q on public.attempts (user_id, question_id, answered_at desc);

alter table public.attempts enable row level security;

-- 権限：ログインした人（authenticated）だけ。追記と読み取りと削除だけで、更新はさせない。
revoke all on public.attempts from anon;
revoke all on public.attempts from authenticated;
grant select, insert, delete on public.attempts to authenticated;

-- 行レベルセキュリティ：自分の行（user_id = 自分）だけ。
drop policy if exists attempts_select on public.attempts;
drop policy if exists attempts_insert on public.attempts;
drop policy if exists attempts_delete on public.attempts;
create policy attempts_select on public.attempts for select to authenticated using (user_id = (select auth.uid()));
create policy attempts_insert on public.attempts for insert to authenticated with check (user_id = (select auth.uid()));
create policy attempts_delete on public.attempts for delete to authenticated using (user_id = (select auth.uid()));
