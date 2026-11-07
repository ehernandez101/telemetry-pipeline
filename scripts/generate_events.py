"""Generate synthetic video-session events for the dbt + DuckDB project.

Everything here is SYNTHETIC. No real system, customer or employer data is used.

Run from the repo root, with the virtual environment active:
    python scripts/generate_events.py

It writes two Parquet files into data/raw/ (git ignores that folder):
    session_events_part1.parquet   2026-10-01 to 2026-10-12, all columns
    session_events_part2.parquet   2026-10-13 to 2026-10-14, WITHOUT stall_count

Messy data added on purpose, because real telemetry has all three:
    1. Duplicates: about 1.5% of sessions are sent twice (same session_id).
    2. Late events: about 3% arrive 6 to 48 hours after the session started.
    3. Schema drift: part 2 is missing the stall_count column.

One pattern is planted so the later analysis has something to find:
    us-east pool 4 is slower and stalls more between 18:00 and 21:59 UTC.
"""
from pathlib import Path

import duckdb

N_SESSIONS = 2_000_000
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()          # in-memory database; nothing is saved except the Parquet files
con.execute("SET threads = 1")  # one thread, so the same seed gives the same data
con.execute("SELECT setseed(0.42)")

# Step 1: one row per session, with a random number for every decision.
con.execute(f"""
CREATE TEMP TABLE draws AS
SELECT
    i AS n,
    random() AS r_day,   random() AS r_peak,  random() AS r_hour,
    random() AS r_min,   random() AS r_sec,   random() AS r_region,
    random() AS r_pool,  random() AS r_u1,    random() AS r_u2,
    random() AS r_stall, random() AS r_dur,   random() AS r_delay,
    random() AS r_late,  random() AS r_dup
FROM range(1, {N_SESSIONS} + 1) AS t(i)
""")

# Step 2: turn the random numbers into the columns we want.
con.execute("""
CREATE TEMP TABLE sessions AS
WITH a AS (
    SELECT
        n,
        DATE '2026-10-01' + CAST(floor(r_day * 14) AS INTEGER) AS event_day,
        CASE WHEN r_peak < 0.55
             THEN 17 + CAST(floor(r_hour * 6) AS INTEGER)
             ELSE CAST(floor(r_hour * 24) AS INTEGER) END AS hr,
        CAST(floor(r_min * 60) AS INTEGER) AS mi,
        CAST(floor(r_sec * 60) AS INTEGER) AS se,
        CASE WHEN r_region < 0.35 THEN 'us-east'
             WHEN r_region < 0.60 THEN 'us-west'
             WHEN r_region < 0.80 THEN 'eu-west'
             WHEN r_region < 0.92 THEN 'ap-south'
             ELSE 'sa-east' END AS region,
        1 + CAST(floor(r_pool * 4) AS INTEGER) AS pool_no,
        r_u1, r_u2, r_stall, r_dur, r_delay, r_late, r_dup
    FROM draws
),
b AS (
    SELECT *,
        CAST(event_day AS TIMESTAMP) + to_hours(hr) + to_minutes(mi) + to_seconds(se) AS event_time,
        CASE WHEN region = 'us-east' AND pool_no = 4 AND hr BETWEEN 18 AND 21
             THEN 1.8 ELSE 1.0 END AS load_factor
    FROM a
)
SELECT
    'S' || lpad(CAST(n AS VARCHAR), 8, '0') AS session_id,
    event_day,
    event_time,
    region,
    region || '-pool-' || CAST(pool_no AS VARCHAR) AS server_pool,
    CAST(round(exp(ln(800) + 0.45 * sqrt(-2 * ln(1 - r_u1)) * cos(2 * pi() * r_u2)) * load_factor) AS INTEGER) AS startup_ms,
    CAST(floor(-ln(1 - r_stall) * 0.5 * load_factor) AS INTEGER) AS stall_count,
    event_time + to_seconds(60 + CAST(floor(r_dur * 3600) AS INTEGER)) AS session_end,
    CASE WHEN r_late < 0.03
         THEN event_time + to_hours(6 + CAST(floor(r_delay * 42) AS INTEGER))
         ELSE event_time + to_seconds(1 + CAST(floor(r_delay * 30) AS INTEGER)) END AS ingested_at,
    r_dup,
    r_delay
FROM b
""")

# Step 3: add the duplicates. A resend is the same event received a little later.
con.execute("""
CREATE TEMP TABLE events AS
SELECT session_id, event_day, event_time, region, server_pool, startup_ms,
       stall_count, session_end, ingested_at
FROM sessions
UNION ALL
SELECT session_id, event_day, event_time, region, server_pool, startup_ms,
       stall_count, session_end,
       ingested_at + to_seconds(1 + CAST(floor(r_delay * 60) AS INTEGER)) AS ingested_at
FROM sessions
WHERE r_dup < 0.015
""")

part1 = (OUT_DIR / "session_events_part1.parquet").as_posix()
part2 = (OUT_DIR / "session_events_part2.parquet").as_posix()

con.execute(f"""
COPY (SELECT session_id, event_time, region, server_pool, startup_ms,
             stall_count, session_end, ingested_at
      FROM events WHERE event_day <= DATE '2026-10-12'
      ORDER BY event_time)
TO '{part1}' (FORMAT PARQUET)
""")
con.execute(f"""
COPY (SELECT session_id, event_time, region, server_pool, startup_ms,
             session_end, ingested_at
      FROM events WHERE event_day >= DATE '2026-10-13'
      ORDER BY event_time)
TO '{part2}' (FORMAT PARQUET)
""")

# Step 4: print what was written, so you can check it.
print("Wrote:", part1)
print("Wrote:", part2)
for label, path in [("part1", part1), ("part2", part2)]:
    rows, ids, first, last = con.execute(
        f"SELECT count(*), count(DISTINCT session_id), min(event_time), max(event_time) "
        f"FROM read_parquet('{path}')"
    ).fetchone()
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]
    late = con.execute(
        f"SELECT count(*) FROM read_parquet('{path}') "
        f"WHERE ingested_at - event_time > INTERVAL 1 HOUR"
    ).fetchone()[0]
    print(f"\n{label}: {rows:,} rows, {ids:,} distinct session_ids, {rows - ids:,} duplicate rows")
    print(f"  events from {first} to {last}")
    print(f"  late-arriving rows (more than 1 hour): {late:,}")
    print(f"  columns: {cols}")
