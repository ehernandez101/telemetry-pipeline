-- Returns any day and region that appears more than once. The test passes when this returns no rows.
select event_date, region, count(*) as copies
from {{ ref('mart_daily_region_quality') }}
group by event_date, region
having count(*) > 1
