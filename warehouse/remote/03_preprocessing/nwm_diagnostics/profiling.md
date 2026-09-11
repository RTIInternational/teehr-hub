# Profiling
- All run with Bleeding Edge 4XL server.
- Desired bootstrap iterations: 1000
- Total locations: 7486

**2026-08-31: fixed the root cause of the crashes/nondeterminism** -- `unpack_results=True`
on the bootstrap metrics triggered a Spark `.first()` action per metric (9x) inside
`.aggregate()` itself, re-executing the whole upstream lazy DAG each time and racing
against spot-instance preemption -- exactly matching the `ShuffleMapStage ... (first at
.../teehr/querying/utils.py:207)` failures below. Replaced with a manual unpack after
aggregation (no Spark action). Also found `spark.sql.adaptive.coalescePartitions.enabled`
was collapsing the bootstrap pandas_udf stage down to ~2 tasks regardless of executor
count, since AQE coalesces based on shuffle byte size, not per-row compute cost -- disabled
for this workload. Rows below from before that point reflect the old, buggy pipeline.

| # Locations | # Days | # Bootstrap Iterations | Spark Params | Aggregation Time | Notes |
| --- | --- | --- | --- | --- | --- |
| All | 92 | 1000 | Cluster - 64 inst., 16g, 2 cores, 1024 part., 4g memOH, coalesce=false | 626s | %78 util. |
| 3000 | 92 | 1000 | Cluster - 32 inst., 12g, 2 cores, 512 part., no memOH, coalesce=false | 219s | 72% util. |
| 3000 | 92 | 1000 | Cluster - 32 inst., 12g, 2 cores, 256 part., no memOH, coalesce=false | 304s | 50% util. |
| 3000 | 92 | 1000 | Cluster - 96 inst., 12g, 2 cores, 1024 part., no memOH, coalesce=false | 230s | (see run_metrics above) |
| 3000 | 92 | 1000 | Cluster - 96 inst., 12g, 2 cores, 1024 part., no memOH, coalesce=false | 1194s | 75% util. |
| 3000 | 92 | 1000 | Cluster - 192 inst., 12g, 2 cores, 2048 part., no memOH, coalesce=false | 814s | 58% util. |
| 3000 | 92 | 1000 | Cluster - 192 inst., 12g, 2 cores, 1024 part., no memOH, coalesce=false | 826s | 57% util. |
| 3000 | 92 | 1000 | Cluster - 96 inst., 12g, 2 cores, 1024 part., no memOH, coalesce=false | 1241s | 76% util. |
| --- | --- | --- | --- | --- | --- |
| 3000 | 92 | 1000 | Cluster - 120 inst., 12g, 2 cores, 2560 part., no memOH, coalesce=false | 858s | (see run_metrics above) |
| 3000 | 92 | 1000 | Cluster - 240 inst., 12g, 2 cores, 2560 part., no memOH, coalesce=false | 1300s | (see run_metrics above) |
| 3000 | 92 | 1000 | Cluster - 240 inst., 12g, 2 cores, 2560 part., no memOH, coalesce=false | 710s | (see run_metrics above) |
| 1000 | 92 | 1000 | Cluster - 80 inst., 12g, 2 cores, 2560 part., no memOH, coalesce=false | 506s | (see run_metrics above)
| 100 | 92 | 1000 | Cluster - 8 inst., 12g, 2 cores, 256 part., no memOH, coalesce=false | 407s | (see run_metrics above) |
| 100 | 92 (2025-Q4) | 1000 | Cluster - 8 inst., 12g, 2 cores, 256 part., no memOH, coalesce=false | 323s | Success, first run after both fixes |
| All | 90 | 1000 | Cluster - 32 inst., 32g, 2 cores, 4096 part. | 52m | Success |
| All | 90 | 1000 | Cluster - 32 inst., 32g, 2 cores, 512 part., 8g mem. overhead | n/a | Began failing at stage 4. |
| All | 90 | 1000 | Cluster - 32 inst., 32g, 2 cores, 2048 part. | n/a | All good until failing at stage 191. |
| All | 90 | 10 | Cluster - 64 inst., 16g, 1 core, 2048 part. | n/a | Job aborted due to stage failure: ShuffleMapStage 30 (first at /srv/conda/envs/notebook/lib/python3.12/site-packages/teehr/querying/utils.py:207) has failed the maximum allowable number of times: 4. |
| All | 90 | 10 | Cluster - 32 inst., 32g, 1 core, 2048 part. | 1hr46m12s | |
| All | 365 | 100 | Cluster - 64 inst., 16g, 1 core, 2048 part. | n/a | OOM failures around stages 12-22 |
| All | 365 | 100 | Cluster - 32 inst., 32g, 2 cores, 2048 part. | n/a | OOM failures around stages 12-22 |
| All | 365 | 100 | Cluster - 32 inst., 32g, 2 cores, 2048 part. | n/a | Failures around stages 12-22 - executors deleted by a user or the framework. |
| All | 365 | 100 | Cluster - 128 inst., 32g, 2 cores, 1024 part. | n/a | Failures around stages 12-22 - executors deleted by a user or the framework. |
| All | 90 | 100 | Cluster - 128 inst., 32g, 2 cores, 4096 part. (no AEQ) | n/a | Failures around stages 12-22 - executors deleted by a user or the framework. |
| All | 90 | 100 | Cluster - 64 inst., 40g, 2 cores, 4096 part., 12g memOH (no AEQ) | n/a | Started seeing failures around stage ~50, cancelled to tweak |
| All | 90 | 100 | Cluster - 128 inst., 16g, 2 cores, 2048 part., 16g memOH | n/a | Acted funny around stage 18, cancelled to tweak |
| All | 90 (2025-Q3) | 100 | Cluster - 128 inst., 20g, 2 cores, 2048 part., 10g memOH | ~2.5 hrs (8907s) | Stg18: 12min |
| All | 270 | 100 | Cluster - 128 inst., 20g, 2 cores, 2048 part., 10g memOH |  | Stg18: ~20-30min - Failed around stage ~90 |
| All | 90 (2025-Q4) | 100 | Cluster - 128 inst., 20g, 2 cores, 2048 part., 10g memOH |  | Failed around stage ~90 |
| All | 90 (2025-Q4) | 100 | Cluster - 128 inst., 24g, 2 cores, 2048 part., 16g memOH |  | Failed around stage ~90 |
| All | 90 (2026-Q1) | 100 | Cluster - 128 inst., 24g, 2 cores, 2048 part., 16g memOH | ~2.5 hrs | Had to try write process multiple times |
| All | 90 (2026-Q2) | 100 | Cluster - 128 inst., 24g, 2 cores, 2048 part., 16g memOH | ~2.5 hrs | Had to try write process multiple times |
| All | 90 (2025-Q4) | 100 | Cluster - 128 inst., 24g, 2 cores, 2048 part., 16g memOH | ~2.5 hrs | Worked after previously failing with same config? |
| 3 | 30 | 10 | Cluster - 64 inst., 16g, 1 core, 2048 part. | 3m34s | |
| 3 | 90 | 10 | Cluster - 64 inst., 16g, 1 core, 2048 part. | 4m41s | |
| 3 | 30 | 100 | Cluster - 64 inst., 16g, 1 core, 2048 part. | 7m17s | |
| 3 | 90 | 100 | Cluster - 64 inst., 16g, 1 core, 2048 part. | 10m36s | |
| 3 | 30 | 10 | Default | 1m24s | |
| 3 | 90 | 10 | Default | 1m57s | |
| 3 | 30 | 100 | Default | 5m26s | |
| 3 | 90 | 100 | Default | 8m47s | |