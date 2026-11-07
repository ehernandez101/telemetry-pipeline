-- Staging model: one clean row per session.
--
-- Raw data problems handled here:
--   1. Part 2 of the data has no stall_count column. union_by_name = true lines the
--      files up by column name and fills the missing column with NULL.
--   2. Some sessions were sent twice. We keep the earliest copy of each session_id.
--   3. Some events arrived hours late. We keep them and flag them with is_late.

with raw as (

    select *
    from read_parquet('data/raw/session_events_part*.parquet', union_by_name = true)

),

ranked as (

    select
        *,
        row_number() over (partition by session_id order by ingested_at) as copy_number
    from raw

)

select
    session_id,
    event_time,
    cast(event_time as date)                       as event_date,
    region,
    server_pool,
    startup_ms,
    stall_count,
    session_end,
    date_diff('second', event_time, session_end)   as session_seconds,
    ingested_at,
    (ingested_at - event_time) > interval 1 hour   as is_late
from ranked
where copy_number = 1
