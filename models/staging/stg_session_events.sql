-- Staging model: one clean row per session, built incrementally.
--
-- Raw data problems handled here:
--   1. Part 2 of the data has no stall_count column. union_by_name = true lines the
--      files up by column name and fills the missing column with NULL.
--   2. Some sessions were sent twice. We keep the earliest copy of each session_id.
--      On incremental runs we also skip any session_id that is already in this table,
--      so a duplicate that arrives later can never replace the original.
--   3. Some events arrived hours late. We keep them and flag them with is_late.
--
-- Incremental logic: after the first build, a run only looks at events received
-- (ingested_at) after the newest event already in this table. Late events are
-- caught because their ingested_at is late too.
--
-- load_until pretends data received after that moment does not exist yet, so the
-- data can be replayed in batches. Example:
--   dbt run --select stg_session_events --full-refresh --vars "{load_until: '2026-10-07'}"
-- The default is far in the future, which means "load everything".

{{ config(materialized='incremental') }}

{% set load_until = var('load_until', '2999-12-31') %}

with raw as (

    select *
    from read_parquet('data/raw/session_events_part*.parquet', union_by_name = true)
    where ingested_at <= timestamp '{{ load_until }}'
    {% if is_incremental() %}
      and ingested_at > (select max(ingested_at) from {{ this }})
    {% endif %}

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
{% if is_incremental() %}
  and session_id not in (select session_id from {{ this }})
{% endif %}
