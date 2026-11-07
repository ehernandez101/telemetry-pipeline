-- Returns any hour and pool that appears more than once. The test passes when this returns no rows.
select hour_start, server_pool, count(*) as copies
from {{ ref('mart_hourly_pool_quality') }}
group by hour_start, server_pool
having count(*) > 1
