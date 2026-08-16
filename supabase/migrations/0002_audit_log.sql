-- Audit log для безопасности: фиксируем все-sensitive действия.
create table if not exists public.audit_log (
    id         bigint generated always as identity primary key,
    user_id    bigint not null,
    action     text not null,
    ip         text,
    user_agent text,
    ok         boolean not null default true,
    detail     text,
    ts         bigint not null default extract(epoch from now())::bigint
);

create index if not exists audit_log_user_ts on public.audit_log (user_id, ts desc);
