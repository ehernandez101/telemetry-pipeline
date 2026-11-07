"""Time one question answered two ways: from the raw files, and from the pre-built mart.

Question: which 10 pool-hours had the worst 95th-percentile startup time
(ignoring hours with fewer than 100 sessions)?

Run from the repo root, after `dbt build`, with the virtual environment active:
    python scripts/time_query.py

SLOW: reads the raw Parquet files, keeps the earliest copy of each session, then
      computes the percentile per pool-hour. All of that happens on every run.
FAST: reads the same numbers from mart_hourly_pool_quality, which dbt already built.

Each version runs once to warm up, then 5 times; the median time is reported.
The script also checks that both versions return exactly the same rows.
"""
import statistics
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "data" / "raw" / "session_events_part*.parquet").as_posix()
DB = ROOT / "telemetry.duckdb"

SLOW = f"""
with raw as (
    select * from read_parquet('{RAW}', union_by_name = true)
),
ranked as (
    select *, row_number() over (partition by session_id order by ingested_at) as copy_number
    from raw
),
dedup as (
    select * from ranked where copy_number = 1
)
select
    date_trunc('hour', event_time)               as hour_start,
    server_pool,
    count(*)                                     as sessions_started,
    round(quantile_cont(startup_ms, 0.95), 0)    as p95_startup_ms
from dedup
group by date_trunc('hour', event_time), server_pool
having count(*) >= 100
order by p95_startup_ms desc, hour_start, server_pool
limit 10
"""

FAST = """
select hour_start, server_pool, sessions_started, p95_startup_ms
from mart_hourly_pool_quality
where sessions_started >= 100
order by p95_startup_ms desc, hour_start, server_pool
limit 10
"""

RUNS = 5


def timed(con, sql):
    con.execute(sql).fetchall()  # warm-up run, not counted
    times, rows = [], None
    for _ in range(RUNS):
        start = time.perf_counter()
        rows = con.execute(sql).fetchall()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times), min(times), max(times), rows


con = duckdb.connect(str(DB), read_only=True)
slow_med, slow_min, slow_max, slow_rows = timed(con, SLOW)
fast_med, fast_min, fast_max, fast_rows = timed(con, FAST)

print(f"SLOW (raw files):  median {slow_med:8.1f} ms   (min {slow_min:.1f}, max {slow_max:.1f})")
print(f"FAST (mart):       median {fast_med:8.1f} ms   (min {fast_min:.1f}, max {fast_max:.1f})")
print(f"Speed-up: {slow_med / fast_med:.0f}x")
print("Same 10 rows from both versions:", slow_rows == fast_rows)
print("\nTop rows:")
for row in fast_rows[:3]:
    print(" ", row)
