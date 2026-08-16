-- Схема БД для проекта AI Telegram WebApp (Supabase).
-- Заменяет локальный SQLite (src/database/repository.py).
-- Доступ к данным идёт ТОЛЬКО через Edge Functions (service_role),
-- поэтому здесь RLS отключён, а валидация initData делается в коде функций.

create table if not exists public.users (
    user_id            bigint primary key,
    api_key            text,
    api_key_provider   text not null default 'openrouter',
    api_key_openrouter text,
    api_key_openai     text,
    api_key_gemini     text,
    api_key_groq       text,
    api_key_huggingface text,
    api_key_venice     text,
    selected_model     text not null default 'openrouter/auto',
    system_prompt      text not null default 'Ты — полезный и дружелюбный AI-ассистент.',
    context_limit      integer not null default 10,
    stats_display      text not null default 'full',
    theme              text not null default 'dark',
    notify_sound       integer not null default 0,
    notify_vibrate     integer not null default 0,
    notify_sound_id    text not null default 'chime',
    vib_strength       integer not null default 40,
    key_mode           text not null default 'manual'
);

create table if not exists public.whitelist (
    user_id           bigint primary key,
    note              text default '',
    access_type       text not null default 'permanent',
    access_expires_at bigint,
    added_at          bigint not null default 0
);

create table if not exists public.messages (
    id         bigint generated always as identity primary key,
    user_id    bigint not null,
    role       text not null,
    content    text not null,
    image_url  text,
    created_at timestamptz not null default now()
);

create index if not exists messages_user_id_idx on public.messages (user_id);

create table if not exists public.api_stats (
    id          bigint generated always as identity primary key,
    user_id     bigint not null,
    tokens_used integer not null,
    timestamp   bigint not null
);

create index if not exists api_stats_user_id_idx on public.api_stats (user_id);

create table if not exists public.user_models (
    user_id        bigint not null,
    model_id       text not null,
    display_name   text not null,
    meta           text,
    short_id       text,
    added_at       bigint,
    context        integer,
    mod_in         text,
    mod_out        text,
    price_prompt   text,
    price_completion text,
    description    text,
    is_free        integer,
    primary key (user_id, model_id)
);

-- Помощник: добавить админа в whitelist (замените 123456789 на свой Telegram ID).
-- insert into public.whitelist (user_id, added_at) values (<ADMIN_ID>, extract(epoch from now())::bigint)
-- on conflict (user_id) do nothing;
