# File guide

One row per file: what it is, and why it exists. This is the answer to "why is this here?" for every file in the repo. Each row is added in the same commit as the file.

| File | What it is | Why it exists |
| --- | --- | --- |
| `README.md` | The project's front page | Says what the project is, that everything is synthetic and local, and where it stands. Results are added last, from real runs |
| `.gitignore` | A list of things git must not track | Keeps the virtual environment, generated data, the DuckDB database file, dbt build output and local secrets out of the repo. All of it can be rebuilt, and generated files are large and make the history noisy |
| `requirements.in` | The two packages this project asks for directly: `dbt-core` and `dbt-duckdb` | Short and readable. It records what I chose, not every package those two pull in |
| `requirements.txt` | Every installed package with its exact version, from `pip freeze` | Makes the setup reproducible, so the CI run uses the same versions as my machine |
| `docs/FILE_GUIDE.md` | This file | Lets me explain every file in the repo, and shows a reviewer that I can |
| `scripts/generate_events.py` | Python script that runs SQL in DuckDB to create the synthetic session events | The project has no real data, so this builds it: about 2 million sessions over 14 days, with duplicates, late-arriving events and one file missing a column added on purpose. It writes two Parquet files into `data/raw/`, which git ignores because the script can rebuild them |
| `dbt_project.yml` | dbt's main settings file for this project | dbt looks for it to know a folder is a dbt project. It names the project, says where models live, and sets how staging models (views) and marts (tables) are built |
| `profiles.yml` | Tells dbt how to connect to the database | Points dbt at a local DuckDB file, `telemetry.duckdb`. It holds no password or secret, because DuckDB is a file on my own computer. That is the only reason it is safe to keep in the repo |
| `models/staging/stg_session_events.sql` | The first dbt model: a cleaned view of the raw session events | Reads both Parquet files together (part 2 lacks `stall_count`, so it is filled with NULL), keeps one row per `session_id` (the earliest copy), and adds `event_date`, `session_seconds` and an `is_late` flag. Later models build on this view instead of the raw files |
| `models/staging/stg_session_events.yml` | Plain-English descriptions of that model and its columns | dbt turns these into the docs site, so every model and column is explained where it is defined |
| `models/marts/mart_daily_region_quality.sql` | A table with one row per day per region summarizing session quality | Answers "how is playback quality by region, by day?" with session counts, startup time, stall rate and late-arrival share. The stall rate averages only sessions that have a value, and a coverage column shows how many that is |
| `models/marts/mart_daily_region_quality.yml` | Descriptions and basic tests for that table | Documents every column and checks that the keys are never empty |
| `tests/assert_daily_region_one_row_per_grain.sql` | A custom test: no day and region appears twice | Duplicate rows at this grain would silently double-count sessions. The test returns any such rows, so it fails if they exist |
| `tests/assert_daily_region_sessions_match_staging.sql` | A custom test: the mart's total sessions equal the staging model's row count | Proves nothing was lost or double-counted when summarizing |
