-- ============================================================
-- 논문 저장용 표 만들기
-- 이 파일 전체를 복사해서, 새로 만든 Supabase 프로젝트의
-- "SQL Editor"에 붙여넣고 실행(Run)하면 됩니다.
-- ============================================================

create table if not exists papers (
    id uuid primary key default gen_random_uuid(),

    -- 중복 판별용 (같은 논문인지 구분하는 열쇠)
    doi text unique,
    pmid text,

    -- 원본(영어)
    title_en text not null,
    abstract_en text,

    -- 한글 (지금은 비워둠, 나중에 채움)
    title_ko text,
    abstract_ko text,
    abstract_ko_generated_at timestamptz,

    -- 저자/국가
    authors jsonb,
    countries text[],

    -- 날짜 (두 종류로 분리)
    publication_year int,
    publication_date date,        -- 논문이 실제 나온 날
    source_indexed_date date,     -- 출처가 이 논문을 등록한 날

    -- 연구 성격
    study_type text,              -- rct / meta_analysis / experimental_likely / review / unclassified
    is_retracted boolean default false,
    citation_count int default 0,

    -- 분류
    primary_category text,        -- OpenAlex 26개 분야 중 하나

    -- 출처
    sources text[] not null,      -- 예: ["europepmc","openalex"]
    source_ids jsonb,             -- 예: {"europepmc":"23467365"}

    -- 링크
    fulltext_url text,
    is_open_access boolean default false,
    journal_name text,

    -- 우리 DB 기록용
    first_seen_at timestamptz default now(),
    last_updated_at timestamptz default now(),

    raw_data jsonb
);

create index if not exists idx_papers_doi on papers(doi);
create index if not exists idx_papers_pub_date on papers(publication_date);
create index if not exists idx_papers_category on papers(primary_category);
create index if not exists idx_papers_citation on papers(citation_count desc);

-- 수집이 잘 됐는지 확인하는 기록표
create table if not exists collection_runs (
    id uuid primary key default gen_random_uuid(),
    source text not null,
    started_at timestamptz default now(),
    records_fetched int default 0,
    records_new int default 0,
    records_updated int default 0,
    records_failed int default 0,
    error_message text
);

-- 보안 설정 (Flare[V]와 동일한 방식: 읽기는 누구나, 쓰기는 service_role만)
alter table papers enable row level security;

create policy "누구나 읽기 가능" on papers for select using (true);
