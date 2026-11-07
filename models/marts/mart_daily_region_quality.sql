-- Mart: one row per day per region.
--
-- stalls_per_session averages only sessions that have a stall_count. avg() skips NULLs,
-- so the days from the raw file without that column show NULL here, not 0.
-- stall_data_coverage_pct says what share of the day's sessions have the value.

select
    event_date,
    region,
    count(*)                                                        as sessions,
    round(avg(startup_ms), 1)                                       as avg_startup_ms,
    round(quantile_cont(startup_ms, 0.95), 0)                       as p95_startup_ms,
    count(stall_count)                                              as sessions_with_stall_data,
    round(100.0 * count(stall_count) / count(*), 1)                 as stall_data_coverage_pct,
    round(avg(stall_count), 3)                                      as stalls_per_session,
    sum(case when is_late then 1 else 0 end)                        as late_sessions,
    round(100.0 * sum(case when is_late then 1 else 0 end) / count(*), 2) as late_pct
from {{ ref('stg_session_events') }}
group by event_date, region
