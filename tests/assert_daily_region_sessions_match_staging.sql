-- Returns a row only if the mart's total sessions differ from the staging row count.
select s.staging_rows, m.mart_sessions
from (select count(*) as staging_rows from {{ ref('stg_session_events') }}) as s
cross join (select sum(sessions) as mart_sessions from {{ ref('mart_daily_region_quality') }}) as m
where s.staging_rows <> m.mart_sessions
