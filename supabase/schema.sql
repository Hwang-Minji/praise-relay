-- 칭찬 릴레이 표. Supabase 대시보드 → SQL Editor에 붙여 넣고 Run을 눌러요.
-- API의 "to" 칸은 SQL 예약어라서 표에서는 to_name 열로 저장해요.
create table if not exists public.entries (
  id bigint generated always as identity primary key,
  name text not null check (char_length(name) between 1 and 40),
  message text not null check (char_length(message) between 1 and 500),
  to_name text check (to_name is null or char_length(to_name) between 1 and 40),
  created_at timestamptz not null default now()
);

-- 브라우저용 공개 키(anon/publishable)로는 읽지도 쓰지도 못하게 막아요.
-- 정책을 만들지 않았으니 Vercel 함수가 쓰는 비밀 키(secret/service_role)만 이 표를 다룰 수 있어요.
alter table public.entries enable row level security;
