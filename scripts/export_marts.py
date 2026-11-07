"""Write the two dbt marts out as CSV files for the dashboard.

Run from the repo root, after `dbt build`, with the virtual environment active:
    python scripts/export_marts.py

Output goes to dashboard/data/. The marts are small summaries (no session-level rows),
all synthetic, so these files are safe to commit.
Close any other window running dbt first: the database file is opened read-only.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard" / "data"
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(ROOT / "telemetry.duckdb"), read_only=True)

for name in ["mart_daily_region_quality", "mart_hourly_pool_quality"]:
    path = (OUT / f"{name}.csv").as_posix()
    con.execute(
        f"COPY (SELECT * FROM {name} ORDER BY 1, 2) TO '{path}' (HEADER, DELIMITER ',')"
    )
    rows = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    print(f"{name}: {rows:,} rows -> {path}")
