-- =============================================================================
--  Supabase 초기 설정 SQL (SQL Editor에 붙여넣고 Run)
-- -----------------------------------------------------------------------------
--  1) supabase.com → 프로젝트 생성 후
--  2) 왼쪽 메뉴 SQL Editor → New query
--  3) 이 파일 전체를 붙여넣고 Run
-- =============================================================================

-- 학습 기록 테이블
create table if not exists study_records (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  keywords    text not null,
  image_path  text not null
);

-- (선택) 인덱스: 복습 퀴즈용 날짜 조회 속도 개선
create index if not exists idx_study_records_created_at
  on study_records (created_at desc);

-- =============================================================================
--  Storage 버킷은 SQL Editor가 아니라 웹 UI에서 만드세요:
--    Storage → New bucket
--    이름: study-images
--    Public bucket: OFF (체크 해제 — Private 로 보관)
-- =============================================================================
