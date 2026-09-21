-- ===========================================================================
-- EchoBoard — Supabase (PostgreSQL) schema for the EchoBoard Classroom
-- Handwriting Dataset (ECHD).
--
-- Apply once per project: Supabase Dashboard > SQL Editor > paste > Run.
-- Safe to re-run; every statement is idempotent.
--
-- This schema is the relational equivalent of the previous MongoDB ECHD
-- document. The nested documents are normalised into columns and one child
-- table, and backend/database.py reassembles the original nested JSON shape
-- so existing API consumers and the dashboard are unaffected:
--
--   image_metadata    -> width, height, format, size_kb
--   quality_metadata  -> blur_score, lighting_score, duplicate, occluded, selected
--   processing_status -> ocr_completed, annotation_completed, reviewed
--   annotations[]     -> public.annotations (one row per annotation)
--
-- Provenance columns (sequence_id, subject, board_type, writer_id, video_id,
-- frame_index, timestamp_ms, change_score, dataset_version) are required for
-- downstream model training: they identify which lesson, board and writer a
-- sample came from, and where in the source video it occurred.
-- ===========================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Dataset versions
-- ---------------------------------------------------------------------------
create table if not exists public.dataset_versions (
    version_id  text primary key,
    description text        not null default '',
    created_at  timestamptz not null default now()
);

insert into public.dataset_versions (version_id, description)
values ('ECHD_v1', 'Initial version')
on conflict (version_id) do nothing;

-- ---------------------------------------------------------------------------
-- Source videos
-- ---------------------------------------------------------------------------
create table if not exists public.videos (
    id           uuid primary key default gen_random_uuid(),
    filename     text             not null default '',
    duration_sec double precision not null default 0,
    total_frames integer          not null default 0,
    fps          double precision not null default 0,
    processing   boolean          not null default true,
    created_at   timestamptz      not null default now(),
    updated_at   timestamptz      not null default now()
);

create index if not exists videos_created_at_idx
    on public.videos (created_at desc);

-- ---------------------------------------------------------------------------
-- Dataset images
-- ---------------------------------------------------------------------------
create table if not exists public.dataset_images (
    id         uuid primary key default gen_random_uuid(),

    -- Human-readable ECHD identifier, e.g. IMG0001.
    image_id   text not null unique,
    image_name text not null default '',

    -- Object path inside the Supabase Storage bucket.
    image_path text not null,

    -- Provenance (training-relevant).
    sequence_id     text,
    subject         text,
    board_type      text,
    writer_id       text,
    uploaded_by     text,
    video_id        uuid references public.videos (id) on delete set null,
    frame_index     integer          not null default 0,
    timestamp_ms    bigint           not null default 0,
    change_score    double precision not null default 0,
    dataset_version text             not null default 'ECHD_v1'
                        references public.dataset_versions (version_id),

    -- image_metadata
    width   integer not null default 0,
    height  integer not null default 0,
    format  text    not null default 'jpg',
    size_kb integer not null default 0,

    -- quality_metadata
    blur_score     double precision not null default 0,
    lighting_score integer          not null default 0,
    duplicate      boolean          not null default false,
    occluded       boolean          not null default false,
    selected       boolean          not null default true,

    -- processing_status
    ocr_completed        boolean not null default false,
    annotation_completed boolean not null default false,
    reviewed             boolean not null default false,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists dataset_images_created_at_idx
    on public.dataset_images (created_at desc);
create index if not exists dataset_images_sequence_id_idx
    on public.dataset_images (sequence_id);
create index if not exists dataset_images_video_id_idx
    on public.dataset_images (video_id);
create index if not exists dataset_images_subject_idx
    on public.dataset_images (subject);
create index if not exists dataset_images_annotation_completed_idx
    on public.dataset_images (annotation_completed);

-- ---------------------------------------------------------------------------
-- Annotations (was the embedded annotations[] array)
-- ---------------------------------------------------------------------------
create table if not exists public.annotations (
    annotation_id text primary key,
    image_id      text not null
                      references public.dataset_images (image_id) on delete cascade,
    class         text             not null default 'Text',
    bbox          jsonb            not null default '[]'::jsonb,
    text          text             not null default '',
    latex         text             not null default '',
    confidence    double precision not null default 0,
    created_at    timestamptz      not null default now()
);

create index if not exists annotations_image_id_idx
    on public.annotations (image_id);

-- ---------------------------------------------------------------------------
-- Sequential ECHD identifiers (IMG0001, ANN0001)
--
-- Sequences are transactional and race-free, replacing the previous
-- find_one_and_update counter documents. Exposed as RPC so the backend can
-- allocate an id through the Supabase REST API.
-- ---------------------------------------------------------------------------
create sequence if not exists public.image_id_seq as bigint start 1;
create sequence if not exists public.annotation_id_seq as bigint start 1;

create or replace function public.next_image_id()
    returns text
    language sql
    volatile
as $$
    select 'IMG' || lpad(nextval('public.image_id_seq')::text, 4, '0');
$$;

create or replace function public.next_annotation_id()
    returns text
    language sql
    volatile
as $$
    select 'ANN' || lpad(nextval('public.annotation_id_seq')::text, 4, '0');
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security
--
-- RLS is enabled with no policies, so anon and authenticated clients cannot
-- read or write these tables. The backend connects with the service_role
-- key, which bypasses RLS by design. Keep that key server-side only: it must
-- never be shipped to the dashboard or committed.
--
-- If you later expose the dataset to browser clients directly, add explicit
-- policies here rather than disabling RLS.
-- ---------------------------------------------------------------------------
alter table public.dataset_versions enable row level security;
alter table public.videos           enable row level security;
alter table public.dataset_images   enable row level security;
alter table public.annotations      enable row level security;
