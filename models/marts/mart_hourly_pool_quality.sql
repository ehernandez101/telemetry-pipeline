-- Mart: one row per hour per server pool.
--
-- Hours are in UTC, based on when each session started.
-- sessions_started is how many sessions began in that hour. This data has no server
-- capacity column, so it measures traffic and quality, not "utilization".
-- stalls_per_session averages only sessions that have a stall_count (see the daily mart).

select
    date_trunc('hour', event_time)                           as hour_start,
    region,
    server_pool,
    count(*)                                                 as sessions_started,
    round(avg(startup_ms), 1)                                as avg_startup_ms,
    round(quantile_cont(startup_ms, 0.95), 0)                as p95_startup_ms,
    count(stall_count)                                       as sessions_with_stall_data,
    round(avg(stall_count), 3)                               as stalls_per_session
from {{ ref('stg_session_events') }}
group by date_trunc('hour', event_time), region, server_pool
