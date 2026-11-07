-- Returns a row only if the mart's total sessions differ from the staging row count.
select s.staging_rows, m.mart_sessions
from (select count(*) as staging_rows from {{ ref('stg_session_events') }}) as s
cross join (select sum(sessions_started) as mart_sessions from {{ ref('mart_hourly_pool_quality') }}) as m
where s.staging_rows <> m.mart_sessions
