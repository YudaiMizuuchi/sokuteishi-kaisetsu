-- 過去問演習：解答の記録（利用者ごと）。Supabase の SQL Editor に貼り付けて実行する。
-- 何度実行しても壊れない（if not exists／create or replace／drop policy if exists）。前の版を実行済みでも、この版を、もう一度そのまま実行してよい。
-- 問題データは、ここに入れない（サイトの静的 JSON を使う）。入れるのは、解答の記録だけ。

-- ============ 1. テーブル ============
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

-- ============ 2. 権限：ログインした人（authenticated）だけ。追記・読み取り・削除だけで、更新はさせない ============
revoke all on public.attempts from anon;
revoke all on public.attempts from authenticated;
grant select, insert, delete on public.attempts to authenticated;

-- ============ 3. 行レベルセキュリティ：自分の行（user_id = 自分）だけ ============
drop policy if exists attempts_select on public.attempts;
drop policy if exists attempts_insert on public.attempts;
drop policy if exists attempts_delete on public.attempts;
create policy attempts_select on public.attempts for select to authenticated using (user_id = (select auth.uid()));
create policy attempts_delete on public.attempts for delete to authenticated using (user_id = (select auth.uid()));
-- 追記は、1人あたりの行数の上限まで（無料枠 500 MB を、1人の大量書き込みで使い切らないため）。
-- 目安：同じ問題・選択肢の記録は、画面側で最新10件に間引くので、全問・全選択肢を解いても 約 12.7 万行。上限は 20 万行。
-- 件数は、関数で数える（方針の中で、同じテーブルを直接参照すると、「infinite recursion」のエラーになるため）。
create or replace function public.my_attempts_count()
returns bigint
language sql
stable
security definer
set search_path = ''
as $$
  select count(*) from public.attempts where user_id = auth.uid();
$$;
revoke all on function public.my_attempts_count() from public;
revoke all on function public.my_attempts_count() from anon;
grant execute on function public.my_attempts_count() to authenticated;

create policy attempts_insert on public.attempts for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and (select public.my_attempts_count()) < 200000
  );

-- ============ 4. アカウントの削除（本人が、画面から行う） ============
-- ログインの登録情報（auth.users の自分の行）を消す。解答の記録は、on delete cascade で、あわせて消える。
-- security definer：呼んだ人ではなく、関数の持ち主の権限で動く。消せるのは、auth.uid()（呼んだ本人）の行だけ。
create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'not signed in';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_my_account() from public;
revoke all on function public.delete_my_account() from anon;
grant execute on function public.delete_my_account() to authenticated;
