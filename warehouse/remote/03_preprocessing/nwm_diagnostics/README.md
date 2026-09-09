# NWM Diagnostics Metrics

This directory builds `teehr.nwmd_metrics_by_location`, the table behind the **NWM
Diagnostics** dashboard. It compares National Water Model streamflow forecasts against
USGS streamgage observations and summarizes how well the model did, sliced by location,
time period, forecast lead time, and flow condition.

The document has two halves:

- **[Part 1 — For scientists and dashboard users](#part-1--for-scientists-and-dashboard-users)**
  explains what the numbers mean, in plain terms.
- **[Part 2 — For data scientists and engineers](#part-2--for-data-scientists-and-engineers)**
  explains how the pipeline works and how to change it.

| File | What it is |
| --- | --- |
| `nwmd_metrics.ipynb` | The production notebook. Defines and runs the pipeline. |
| `utils.py` | Cluster-sizing instrumentation and the executor pod template. Downloaded by the notebook from the branch at run time. |
| `query_metrics_tables.ipynb` | Spot-check and validation queries against the output table. |
| `explore_nwmd_metrics.ipynb` | Ad-hoc exploration. |
| `01_calculate_nwm_metrics.ipynb` | The original cell-by-cell version. Kept for reference; superseded by `nwmd_metrics.ipynb`. |
| `legacy_vs_vectorized_validadtion.ipynb` | Checks that the vectorized bootstrap engine reaches the executors. |
| `profiling.md` | Running record of cluster configurations and runtimes. |

---

# Part 1 — For scientists and dashboard users

## What goes in

Two streams of hourly streamflow, already paired up by location and time:

- **Observed** — what a USGS streamgage actually measured. In the table this is the
  *primary* value.
- **Forecast** — what the National Water Model predicted for that same place and time.
  In the table this is the *secondary* value.

The pairing is done upstream, in a table called `fcst_joined_timeseries`. Each row there
is a single hour at a single gage: the observation, the matching forecast value, when the
forecast was issued (its *reference time*), and which model configuration produced it.

Two configurations are processed:

| Configuration | Forecast horizon | Grouped into |
| --- | --- | --- |
| `nwm30_short_range` | out to 18 hours | 3 bins of 6 hours |
| `nwm30_medium_range` | out to 10 days | 10 bins of 1 day |

The most recent run covered **water years 2025 and 2026** (1 October 2024 through
30 September 2026) across roughly **7,500 gages**.

## The central idea: forecasts get worse the further ahead they look

A forecast issued this morning for *this afternoon* should be better than one issued
today for *nine days from now*. If you lump all forecasts together you can't see that,
so the first thing the pipeline does is sort every forecast value by **how far ahead it
was looking** — its lead time — and put it in a bin.

For medium range, bin `P2DT0H_P3DT0H` holds everything that was forecasting 2 to 3 days
ahead. For short range, `PT6H_PT12H` holds everything 6 to 12 hours ahead. Those labels
are ISO-8601 durations: `PT6H` is 6 hours, `P2DT0H` is 2 days.

Bins are **start-exclusive and end-inclusive**: `PT6H_PT12H` covers lead times of 7 through
12 hours, so a forecast valid exactly 6 hours out belongs to the *previous* bin. That is
why an 18-hour forecast gives three 6-hour bins rather than four. (Before
[teehr #815](https://github.com/RTIInternational/teehr/issues/815) the convention was the
other way round, which produced a stray fourth bin holding only hour 18, and an eleventh
medium-range bin holding only hour 240. Results computed before that fix are not
comparable with results computed after it.)

Every metric is reported separately for every bin. Reading a metric across bins is how
you see forecast skill decay with lead time.

## Step by step, with a worked example

Take one gage, one forecast issued at midnight, and follow it through.

### 1. Sort the hours into lead-time bins

A medium-range forecast issued at midnight produces a value for every hour out to about
11 days. Hours 0–24 go in the first bin, hours 24–48 in the second, and so on.

```
forecast issued 2026-01-15 00:00, gage usgs-01018009
  hour   1  ... 24   -> bin PT0S_P1DT0H     (up to 1 day ahead)
  hour  25  ... 48   -> bin P1DT0H_P2DT0H   (1 to 2 days ahead)
  ...
  hour 217 ... 240   -> bin P9DT0H_P10DT0H  (9 to 10 days ahead)
```

### 2. Summarize each bin three ways

Within one bin there are 24 hourly pairs. Rather than comparing all 24 individually, the
pipeline reduces the bin to three summaries, and keeps all three:

| Summary | Question it answers |
| --- | --- |
| `mean` | Did the model get the overall *volume* of water right? |
| `max` | Did the model get the *peak* right? This is the one that matters for flooding. |
| `min` | Did the model get the *low point* right? Relevant for drought and baseflow. |

Both sides are summarized the same way, so `max` compares the highest observed value in
that day against the highest forecast value in that day.

This matters because a forecast can get the average right while badly missing the peak.
Keeping `mean`, `max`, and `min` separately makes that visible instead of averaging it
away. In the dashboard this is the "aggregation method" selector.

```
bin PT0S_P1DT0H, 24 hourly pairs
                        observed   forecast
  mean of the 24          12.4       11.8
  max  of the 24          31.7       24.1     <- model under-predicted the peak
  min  of the 24           6.2        6.4
```

### 3. Repeat for every forecast, then pool

The above happens for every forecast issued in the period. One day-0-to-1 bin from one
forecast isn't informative on its own; pooling hundreds of them is. So all the
`PT0S_P1DT0H` + `max` pairs for that gage get pooled, and the metrics in step 6 are
computed over that pool.

The `count` column tells you how many bins went into the pool, and `n_timesteps` tells
you how many individual hourly observations sat behind them.

### 4. Optionally restrict to high flows

Model performance during a flood is a different question from model performance on an
average Tuesday, and averages are dominated by ordinary days. So every metric is also
computed using **only the hours when the river was actually running high**.

"High" is defined per gage from **its entire observed record** — the 85th, 95th, and 99th
percentile of everything that streamgage has ever measured, computed once and stored in
`teehr.nwmd_flow_thresholds`. An hour counts as an event if the *observed* flow exceeded
that gage's threshold.

| `threshold` value | Which hours are included |
| --- | --- |
| `NULL` | All hours. No restriction. |
| `above_q85` | Only hours above that gage's 85th percentile |
| `above_q95` | Only hours above its 95th percentile |
| `above_q99` | Only hours above its 99th percentile |

Two things to keep in mind:

- The percentile is **specific to each gage**. A small creek and a large river have
  completely different 99th percentiles. This is deliberate — it asks "was this river
  high *for itself*", which is what matters hydrologically.
- The percentile comes from the gage's **full period of record**, not from the time window
  being analyzed. So `above_q95` means the same thing in every row of the table, and
  numbers from a run covering one quarter are directly comparable with numbers from a run
  covering two years. The thresholds only change if someone deliberately recomputes them
  (see `build_flow_thresholds` in Part 2) — and when that happens, every row's meaning
  shifts with them.

Restricting to `above_q99` is why some rows have small `count` values: a 99th-percentile
event is rare by construction. `count = 13` means only 13 bins qualified. Metrics on 13
samples are noisy, which is exactly what the confidence intervals in step 7 are for.

### 5. Choose a time period

Metrics are reported at two time scales, so you can see both the seasonal picture and
the annual one:

| `water_year` | `quarter` | Means |
| --- | --- | --- |
| `2026` | `2026-Q1` | Just that calendar quarter |
| `2026` | `NULL` | The whole of water year 2026 |

A water year runs 1 October to 30 September and is named for the year it ends in, so
water year 2026 began in October 2025. One consequence worth knowing: because `quarter`
is labeled by *calendar* year, water year 2026 contains quarters labeled `2025-Q4`
*and* `2026-Q1` through `2026-Q3`. That looks odd but is correct.

A `NULL` in the `quarter` column always means "aggregated across" — the row is the whole
water year, not one quarter.

### 6. Compute the metrics

Two kinds of column. **Signatures** describe the observed data alone — useful context,
not a judgment of the model:

| Column | Meaning |
| --- | --- |
| `count` | How many binned values went into this row |
| `n_timesteps` | How many individual hourly observations sat behind them |
| `average`, `minimum`, `maximum` | Summary of the observed values |

**Comparison metrics** judge the forecast against the observation. The ratio metrics all
have an ideal value of **1.0**; above 1 means the model runs high, below 1 means it runs
low:

| Column | What it compares | Ideal |
| --- | --- | --- |
| `relative_mean` | forecast mean ÷ observed mean | 1.0 |
| `relative_median` | forecast median ÷ observed median | 1.0 |
| `relative_minimum` | forecast minimum ÷ observed minimum | 1.0 |
| `relative_maximum` | forecast maximum ÷ observed maximum | 1.0 |
| `relative_standard_deviation` | forecast variability ÷ observed variability | 1.0 |

`relative_mean` and `relative_median` together are informative: if the mean ratio is far
from 1 but the median ratio is close, a handful of large events are driving the error.

The remaining metrics are standard hydrologic scores:

| Column | Meaning | Ideal | Notes |
| --- | --- | --- | --- |
| `relative_bias` | Total error as a fraction of total observed flow. `-0.2` means the model delivered 20% too little water overall. | 0.0 | |
| `pearson_correlation` | Does the forecast rise and fall *when* the river does? Purely about timing and shape. | 1.0 | Can be high even if magnitudes are badly wrong |
| `nash_sutcliffe_efficiency` | Is the forecast better than just always predicting the average observed flow? | 1.0 | **0 means no better than that flat average. Negative means worse.** Unbounded below |
| `kling_gupta_efficiency` | Combines correlation, variability, and bias into one score | 1.0 | Often preferred over NSE because you can decompose *why* it is low |

A practical reading order: `pearson_correlation` for timing, `relative_bias` for volume,
`relative_maximum` for peaks, and `kling_gupta_efficiency` as the overall summary.

### 7. How confident should you be?

Every comparison metric also has a **95% confidence interval**, in the columns ending
`_boot_0_025` and `_boot_0_975`. For example `kling_gupta_efficiency` is accompanied by
`kling_gupta_efficiency_boot_0_025` and `kling_gupta_efficiency_boot_0_975`.

These come from resampling: the pooled data is re-drawn 1,000 times and the metric
recomputed each time, giving a range of plausible values. The interval is the 2.5th to
97.5th percentile of those 1,000 results.

Why it matters: a KGE of 0.55 computed from 400 bins is a solid result. The same 0.55
from 13 `above_q99` bins might have an interval spanning 0.05 to 0.85, which means you
genuinely cannot distinguish it from mediocre. **Check the interval before drawing a
conclusion, especially at the higher thresholds.** Where two configurations or two lead
times have overlapping intervals, the difference between them is not established.

The resampling preserves short-range time structure rather than shuffling hours
independently, because streamflow is strongly autocorrelated — today's flow tells you a
lot about tomorrow's. Ignoring that would make the intervals falsely narrow.

## Reading an actual row

Here is a real row from the current table, reformatted:

| Column | Value |
| --- | --- |
| `primary_location_id` | `usgs-01018009` |
| `secondary_location_id` | `nwm30-817499` |
| `configuration_name` | `nwm30_medium_range` |
| `variable_name` / `unit_name` | `streamflow_hourly_inst` / `m^3/s` |
| `water_year` / `quarter` | `2026` / `2026-Q1` |
| `forecast_lead_time_bin` | `PT0S_P1DT0H` |
| `threshold` | `above_q85` |
| `window_agg` | `max` |
| `count` | `13` |
| `average` | `1.38` |

In words:

> At USGS gage 01018009, paired with NWM reach 817499, using medium-range forecasts in
> the first quarter of water year 2026: looking only at forecasts 0 to 1 day ahead, and
> only at hours when observed flow exceeded this gage's 85th percentile, comparing the
> *peak* flow in each 1-day window. Thirteen such windows qualified, and their peak
> observed flows averaged 1.38 m³/s.

The comparison metrics on that row then tell you how the forecast peaks stacked up
against those 13 observed peaks.

## What this table cannot tell you

- **Why** the model was wrong. These are diagnostics, not attribution. A low KGE doesn't
  distinguish bad precipitation forcing from bad routing.
- Anything about ungaged locations. Every row is anchored to a USGS gage.
- Anything about flows outside the observed record's range — the thresholds are empirical
  percentiles of what that gage has actually measured, not modelled extremes.
- Whether a difference is *meaningful* — that's what the confidence intervals are for,
  and overlapping intervals mean "not established".

Also note that gages with short or patchy records produce percentile thresholds from
little data, so their `above_q99` rows in particular can rest on very few observations.
`count` and `n_timesteps` are there to let you check.

---

# Part 2 — For data scientists and engineers

## Shape of the pipeline

Everything lives in one cell of `nwmd_metrics.ipynb` (cell index 3), which defines the
dimension spec plus `generate_nwmd_metrics(spark, config, output_table_name)`. The
notebook is the source of truth; `utils.py` holds only instrumentation and the pod
template, and is fetched from the pushed branch by cell 1 at run time.

```
nwmd_flow_thresholds    (per-gage q85/q95/q99 over the primary_timeseries POR,
  |                      built once by build_flow_thresholds)
  v
fcst_joined_timeseries  (one row per gage x hour x reference_time)
  |
  |  .filter(configuration, reference_time range)
  |  join_flow_thresholds(...)          broadcast join -> threshold_q85/95/99
  |  .add_calculated_fields(...)        water_year, quarter, lead-time bin,
  |                                     above_q85/95/99 event flags
  v
PRE_BIN expansion                       threshold: 4 levels, row-FILTERING (4x rows)
  |
  v
bin aggregation                         group_by_bin includes reference_time
  |                                     -> mean/min/max of primary & secondary, n_in_bin
  v
POST_BIN expansion                      temporal rollups (grouping sets)
  |                                     window_agg pivot (metric cols -> rows)
  v
final aggregation                       group_by (no reference_time)
  |                                     signatures + 9 point metrics + 9 bootstrapped
  v
.order_by().add_geometry()
  |
  v
write_to(nwmd_metrics_by_location*)     create_or_replace | upsert
  |
  v
ALTER TABLE ... SET TBLPROPERTIES       description, group_by, metrics
```

The TBLPROPERTIES matter: `api/src/routes/queryables.py` reads `metrics`, `group_by` and
`description` off the Iceberg table and emits them as `x-teehr-group-by` /
`x-teehr-metrics`, so the web API exposes this table generically without knowing anything
about it. `routes/metrics.py` then accepts any `group_by` column as an equality filter and
maps the literal string `"null"` to `IS NULL`.

## The dimension spec

Every group-by column of the output is declared once, and every derived list is computed
from those declarations. Before this refactor the same field names were spelled out by
hand in eight places (CF list, two `stack()` strings with hard-coded arities,
`group_by_bin`, a literal `group_by`, `nullables`, `partition_by`, TBLPROPERTIES) and had
to be kept in sync manually.

```python
@dataclass(frozen=True)
class Dimension:
    names: Tuple[str, ...]           # >1 name = correlated levels (grouping sets)
    stage: str                       # PRE_BIN | BIN | POST_BIN
    levels: Tuple[Level, ...] = ()   # empty => plain grouping key, no expansion
    calculated_fields: Tuple = ()
    consumes: Tuple[str, ...] = ()   # helper cols dropped after the stack
    payload_fields: Tuple[str, ...] = ()
    nullable_names: Tuple[str, ...] = ()
    partition_names: Tuple[str, ...] = ()
    in_bin_group: bool = True
    in_final_group: bool = True
```

`DimensionSpec` then derives:

| Property | Replaces |
| --- | --- |
| `calculated_fields` | the hand-written CF list |
| `group_by_bin` | the literal bin group-by (keeps `reference_time`) |
| `group_by` | the literal 11-element final group-by (drops `reference_time`) |
| `nullable_fields` | `nullables = [...]` |
| `partition_by` | `partition_by=[...]` |
| `nullable_partition_fields` | (new) the safety check described below |

The `reference_time`-in-bin / not-in-final asymmetry is intentional: the bin aggregation
is per-forecast, and the final aggregation pools across forecasts.

## High-flow thresholds are climatological, and precomputed

`build_flow_thresholds(spark)` computes exact percentiles per
`(location_id, variable_name, unit_name)` over the whole `primary_timeseries` record and
writes `iceberg.teehr.nwmd_flow_thresholds` in long form
(`location_id, variable_name, unit_name, quantile, threshold_value, n_values, por_start,
por_end, computed_at`). `load_flow_thresholds()` pivots it to one row per location and
`join_flow_thresholds()` broadcast-joins it on.

This replaced `tcf.AbovePercentileEventDetection` computed inline over the *filtered
joined timeseries*, which was wrong three ways:

1. **Window dependence.** The percentile moved when the `reference_time` filter moved, so
   rows written by different runs were not comparable and re-running a single quarter
   silently redefined its own thresholds.
2. **Coverage weighting.** Each observed hour appears in the joined table once per
   reference time that forecasts it, so the distribution being quantiled was weighted by
   forecast coverage rather than being the observed distribution. In a synthetic check,
   quantiling a coverage-skewed sample moved q85 from 85.1 to 94.0.
3. **Per-configuration thresholds.** The quantile group included `configuration_name`,
   and each configuration runs under its own filter regardless — so `above_q85` meant
   something different for short range than for medium range at the same gage, which
   undermines comparing configurations.

It is also cheaper: a broadcast join plus a column comparison replaces an `applyInPandas`
UDF that shuffled by gage and pulled each gage's whole series into pandas, at a stage
*upstream* of the 4x threshold expansion.

`rcf.ThresholdValueExceeded` is `coalesce(value > threshold, False)` — strictly greater,
matching the old comparison exactly, so the flags remain comparable. Verified: given the
same threshold value, zero rows disagree, including NULL-valued rows (old returned NULL
and was dropped by `.where`, new returns False).

**The join key is a *parsed* variable name, not the raw one.** A `variable_name` is
`{parameter}_{period}_{statistic}`, and observations arrive as `streamflow_none_inst`
while forecasts are `streamflow_hourly_inst`. Those describe the same physical quantity,
and `JoinedTimeseriesView._perform_join` in teehr already treats them as equivalent: for
the `inst` statistic it joins on parameter and statistic only, ignoring period; non-inst
variables must match in full. `variable_join_key_sql()` reproduces that rule, collapsing
both names to `streamflow_inst` so the threshold join lands, while leaving
`streamflow_daily_mean` distinct from `streamflow_hourly_mean`. Joining on the raw
`variable_name` matches nothing and every row silently falls into the NULL threshold
level — which is exactly how this was found. Use `get(parts, 2)` rather than `parts[2]`:
under ANSI mode an out-of-range array index raises rather than returning NULL, so a
variable name with fewer than three parts would abort the run.

`load_flow_thresholds` prints the `(variable_name -> join key, unit_name)` combinations it
loaded, so a key mismatch is visible in the run log rather than only in the output table.

The left join is deliberate. A gage with no threshold row keeps its rows, gets `False` at
every level, and therefore appears only under the NULL "all rows" level rather than
vanishing from the table. Both the event flags and the joined `threshold_q*` value columns
are listed in the threshold dimension's `consumes`, so they are dropped at the PRE_BIN
stack and never reach the bin aggregation as group keys.

**Re-running `build_flow_thresholds` changes the meaning of every existing row.** Treat it
as a deliberate, announced operation, not routine maintenance. `n_values`, `por_start` and
`por_end` are stored per row so you can see what a threshold was computed from.

## PRE_BIN vs POST_BIN — the load-bearing distinction

Two structurally different kinds of dimension, and getting this wrong is either a
correctness bug or a large performance loss:

**`PRE_BIN`** (`threshold`) — each level selects a *subset* of rows, so expansion must
happen **before** the bin aggregation. The per-bin mean/min/max for `above_q95` has to be
computed over only the rows exceeding q95. Cost: 4x rows through the largest shuffle.

**`POST_BIN`** (temporal rollups, `window_agg`) — every level keeps all rows. Expanding
after the bin aggregation gives an identical result without multiplying the scan, the
event detection, and the bin-agg shuffle, which handle far more rows than the post-bin
stream does.

`POST_BIN` is only exact if the dimension is **constant within every `group_by_bin`
group**. That holds for anything derived from `reference_time` (itself a bin key). It
would *not* hold for a `value_time`-derived field, since a bin spans many value times —
adding one would silently split bins and change the bin means. Treat that as a
precondition, not a style preference.

## Three stack shapes, one generator

`expand_dimension()` generates the `stack()` SQL from the spec, so arity and level list
cannot drift apart:

```python
out_names = [*dim.names, "_keep_row", *dim.payload_fields]
rows = [[*lvl.values, lvl.keep, *(lvl.payload[p] for p in dim.payload_fields)]
        for lvl in dim.levels]
dropped = set(dim.consumes) | set(out_names)
base_cols = [c for c in tbl.to_sdf().columns if c not in dropped]
```

`stack()` may reference columns absent from `base_cols` (`above_q85`, `quarter`,
`mean_primary_value`) — that is how helper columns get consumed and dropped in one step.

**Beware which Spark methods the table accessor shadows.** `selectExpr`, `select`, `where`
and `join` all reach Spark through the `__getattr__` proxy (which forwards `**kwargs`), but
`filter` is teehr's own `TableFilter` API and — the dangerous one — **`.drop()` is
`BaseTable.drop()`, which drops the TABLE FROM THE CATALOG**, not columns. It happens to
take no arguments, so `.drop("col")` raises `TypeError` rather than destroying a table, but
do not rely on that. To shed columns, `select` what you want, or join on column *names*
(`on=["a", "b"]`) so Spark emits a single copy of each key and there is nothing to drop.

The three shapes it covers:

1. **Row-filtering** — `threshold`. Levels carry a `keep` predicate; a trailing
   `.where("_keep_row")` is applied only when some level's keep is not `"true"`.
2. **Grouping sets** — the temporal dimension. `names=("water_year", "quarter")` with
   correlated levels. This is Spark `GROUPING SETS` emulated by row replication, because
   teehr's `aggregate()` only accepts a flat `group_by` list.
3. **Metric-output pivot** — `window_agg`. Uses `payload` to map output columns to source
   columns, turning `mean_primary_value`/`min_.../max_...` into rows keyed by `window_agg`.

## Temporal rollups are grouping sets, not independent nulls

`config["rollups"]` selects levels over `(water_year, quarter)`; default
`("quarter", "water_year")`:

| `rollups` | levels | post-bin multiplier |
| --- | --- | --- |
| `["quarter"]` | `(wy, q)` | 1x |
| `["quarter", "water_year"]` *(default)* | `+ (wy, NULL)` | 2x |
| `["quarter", "water_year", "all"]` | `+ (NULL, NULL)` | 3x |

They must be **one** `Dimension`, not two. Because every quarter belongs to exactly one
water year, an independent NULL level on `water_year` would produce
`(quarter='2025-Q4', water_year=NULL)` containing exactly the same rows as
`(quarter='2025-Q4', water_year=2026)` — a duplicate. A rollup is only meaningful when the
finer column collapses with it, which is what a grouping set expresses.

**A rollup summarizes what that run read, not what is in the table.** Enabling `"all"` on
a per-water-year run writes a period-of-record row containing only that year, and each
subsequent run overwrites it. You cannot assemble it after the fact from the
per-water-year rows either: NSE, KGE and correlation are not averageable, and the
bin-level rows they would need are not persisted. So `"all"` is only valid on a run whose
`reference_time` filters span the whole record.

## Bootstrap

```python
bootstrap = bs.Stationary(reps=config.get("bootstrap_reps", 1000),
                          seed=1234, quantiles=[0.025, 0.975])
```

Stationary block bootstrap from `arch`, with the block length estimated per series
(`optimal_block_length`, `b_sb` estimate) since streamflow is autocorrelated.

`unpack_results=True` is set on all nine bootstrapped metrics. This is only safe on
teehr >= `162297f8`: `post_process_metric_results` now derives the quantile keys
statically via `derive_map_key_list()` from `bootstrap.quantiles`. Before that fix,
unpacking called `sdf.select(col).first()` **once per metric** — a real Spark action that
re-executed the entire upstream DAG nine times, and the confirmed cause of the
`ShuffleMapStage ... first at teehr/querying/utils.py:207` failures recorded in
`profiling.md`. With it set, each MapType column becomes one column per quantile:
`kling_gupta_efficiency_boot` -> `..._boot_0_025`, `..._boot_0_975` (dots become
underscores).

Point estimates and their CIs are built from the **same kwargs**, via
`BOOTSTRAPPED_METRICS`. Previously the `*_boot` variants silently omitted
`add_epsilon=True`, so the interval described a different estimator than the point value
it accompanied and the point value could fall outside its own CI.

Bootstrap dominates runtime. For iteration, set `"bootstrap_reps": 10` — a full-scale
smoke test that exercises the identical shuffle and executor-disk path.

## Write path

```python
if ev.spark.catalog.tableExists(full_table_name):
    results.write_to(table_name=output_table_name, write_mode="upsert",
                     uniqueness_fields=group_by,            # the FULL key
                     nullable_fields=spec.nullable_fields,
                     use_partition_filters=USE_PARTITION_FILTERS)  # False
else:
    results.write_to(table_name=output_table_name, write_mode="create_or_replace",
                     partition_by=spec.partition_by)
```

Two non-obvious points, both of which were bugs:

**`uniqueness_fields` must be the full key.** `Write._build_on_clause` applies null-safe
`<=>` only to fields present in **both** `uniqueness_fields` and `nullable_fields`. The
previous "`group_by` minus nullables" made the two lists disjoint, so `threshold` and
`member` never entered the MERGE `ON` clause at all — one target row matched every
threshold level, and `threshold` landed in the `UPDATE SET` clause because
`update_fields = set(source_fields) - set(uniqueness_fields)`.

**`upsert` evaluates the whole pipeline three times — prefer `overwrite`.** Iceberg's MERGE
evaluates its source repeatedly. A profiled run showed `fcst_joined_timeseries` scanned **3x**
(verified by distinct output-attribute ids `#79`, `#378`, `#572`, with `MergeRows` in the plan), so
the entire bootstrap-and-shuffle chain ran three times over. That multiple dwarfs any tuning of
`bootstrap_reps` or location count.

The default is therefore `write_mode="overwrite"`, which is a single-pass `INSERT OVERWRITE`. It is
scoped to just the partitions being rebuilt by
`spark.sql.sources.partitionOverwriteMode=dynamic` in the session config — that setting is
**mandatory**, and `generate_nwmd_metrics` refuses to run without it, because in the default
`static` mode `INSERT OVERWRITE` replaces the **entire table** and would destroy every other
configuration's rows.

`write_mode="upsert"` remains available for runs that must add rows to partitions whose existing
contents have to survive. A dynamic overwrite replaces everything in the partitions it touches, so
combining `overwrite` with `location_sample_n` / `location_ids` would delete every location the run
did not compute — the function raises rather than letting that happen.

**Never CTAS a table that does not exist yet.** The first write to a new table creates an
empty table and commits it, then does an `INSERT OVERWRITE`:

```python
results.limit(0).write_to(table_name, write_mode="create_or_replace",
                          partition_by=spec.partition_by)
results.write_to(table_name, write_mode="overwrite")
```

A `CREATE OR REPLACE TABLE ... AS SELECT` leaves the target *staged* — not resolvable in
the REST catalog — for the entire duration of the write. teehr requests
`X-Iceberg-Access-Delegation: vended-credentials`
(`spark_session_utils.py`), so executors fetch scoped S3 credentials from the catalog per
table and refresh them as they approach expiry. On a multi-hour write that refresh returns
`RESTException: Unable to process: Table does not exist` and kills the task, which then
fails the stage after four attempts. A short write commits before any refresh is due, so a
smoke test passes and only the full run dies — deep into the write, which makes it look
like a data problem rather than an auth one.

`limit(0)` is free: Spark prunes it to `LocalTableScan <empty>`, so the create step does
not touch the upstream plan, and letting teehr perform the create keeps the audit columns
and the partitioning. `overwrite` is `INSERT OVERWRITE TABLE`, which is also idempotent on
a retry where `append` would double-write.

`build_flow_thresholds` has the same exposure for the same reason — the exact-percentile
scan over the whole period of record is slow, and it used to run inside the CTAS. It now
collects the result (a few rows per gage) and creates the table from that, so the CTAS
itself is near-instant.

**`use_partition_filters=False`.** `_build_partition_filters` runs `SELECT DISTINCT` /
`MIN`-`MAX` over the *lazy* source view — `to_warehouse` registers the result as an
uncached temp view — which executes the whole bootstrap DAG once before the MERGE
executes it again. Partition pruning is not worth 2x the most expensive stage.

Leaving it off is also what makes a nullable partition column safe. Iceberg itself is
fine with NULL identity-partition values; the constraint is teehr's, and only when
partition filters are on: those predicates are `t.<f> IN (...)` for strings (built from
`... WHERE <f> IS NOT NULL`) and `t.<f> >= min AND t.<f> <= max` for numerics, and **both
evaluate to NULL, i.e. not matched, for a NULL partition value** — so those rows would
fall outside the merge and be re-INSERTed, and therefore duplicated, on every upsert.
`DimensionSpec.nullable_partition_fields` reports the situation and the write site asserts
on the genuinely unsafe combination.

Partitioning is `["configuration_name", "water_year"]`. Both are low cardinality, appear
in `group_by` (so they reach the MERGE `ON` clause and Iceberg can prune), and each run
writes exactly one of each. `partition_by` is only honored by `create_or_replace`, so the
first run fixes the layout.

## Cluster sizing, and the two failure modes we hit

Current working configuration (cell 4):

```python
spark = create_spark_session(
    start_spark_cluster=True,
    executor_instances=64, executor_memory="16g", executor_cores=2,
    pod_template_path=pod_template_path,
    update_configs={
        "spark.sql.shuffle.partitions": 1024,
        "spark.sql.adaptive.coalescePartitions.enabled": "false",
        "spark.executorEnv.TEEHR_BOOTSTRAP_ENGINE": "vectorized",
        "spark.executor.memoryOverhead": "4g",
    })
```

`coalescePartitions` is disabled deliberately: AQE coalesces on shuffle *byte* size, not
per-row compute cost, and it was collapsing the bootstrap `pandas_udf` stage to ~2 tasks
regardless of executor count.

**Failure mode 1 — executor eviction for ephemeral storage.** A full run died with ~55
evictions and the resulting `FetchFailedException` / `Missing an output location for
shuffle N` cascade; 71 of 135 executors were replaced before the job aborted. Spark puts
`SPARK_LOCAL_DIRS` on an `emptyDir` backed by the node root volume — r5.4xlarge has no
instance store and the node group provisions an 80 GB gp3 root (~71 GiB allocatable,
kubelet evicts under 8 GiB free) — 5–6 executors shared each node, and the pods requested
**no ephemeral storage at all**. So the scheduler could not account for shuffle disk, and
kubelet ranks eviction victims by usage over request, which put the executors first every
time.

Fix: `create_ondemand_pod_template(ephemeral_storage_request=...)` declares the request,
which both spreads executors and buys eviction immunity up to the request.

Sizing it is a two-part change, and both parts must move together:

- the **node** needs the disk. `teehr-cloud-platform` gives the three executor-running node
  groups 300 GB gp3 root volumes (up from 80 GB, ~71 GiB allocatable) at 250 MB/s. At 80 GB
  disk capped a node at 3 executors while its cores allowed 8 and its memory allowed 6, so
  most of every instance was paid for and idle — and runs died once shuffle filled it.
- the **request** should match where *memory* binds, not where disk does: 6 executors per
  r5.4xlarge at 20 GiB each. Hence **40Gi** (6 × 40 = 240 GiB of ~290 GiB allocatable).
  Leaving it at 20Gi with the bigger volume would let the scheduler pack 14 per node and
  oversubscribe memory instead.

A 2026-09-09 run wrote 1,243 GB of shuffle — ~19.4 GB per executor against the old 20Gi
request, i.e. no headroom — and lost 11 executors.

Confirm the request survived Spark's own resource merge:

```bash
kubectl get pod <exec-pod> -o jsonpath='{.spec.containers[0].resources}'
kubectl describe node <node> | grep -A6 "Allocated resources"   # ephemeral-storage != 0
```

The systemic fix is a larger root volume — `volume_size = 80` in
`teehr-cloud-platform/terraform/eks.tf`.

**Failure mode 2 — missing `requests` on the executors.** Every teehr `pandas_udf` died
with `ModuleNotFoundError: No module named 'requests'`. teehr imports `requests` in
`evaluation/download.py`, which `import teehr` reaches via `evaluation/evaluation.py`, so
a missing `requests` breaks importing the package at all. It had never been declared and
always arrived transitively; `dataretrieval` 1.3.0 switched to `httpx` and dropped it,
while `poetry.lock` still pinned `dataretrieval` 1.1.5 — so local envs kept working while
the lean executor image (which installs from `pyproject.toml`, not the lock) failed.
Fixed in teehr by declaring `requests` and raising the `dataretrieval` floor to `>=1.3`
(which is also where `usgs.py`'s `waterdata` import comes from).

The general lesson: the driver runs in the Jupyter image and the executors run the lean
`spark-executor` image. **Anything a `pandas_udf` imports must exist in the executor
image**, and a driver-only test will not catch it. Local-mode runs
(`create_spark_session()` with no cluster) execute all Python on the driver and mask this
entire class of bug.

## Observed runtimes

Both configurations, all ~7,500 gages, water years 2025–2026, 1,000 bootstrap reps,
64 executors:

| Configuration | Lead-time bins | Runtime |
| --- | --- | --- |
| `nwm30_medium_range` | 11 | 4,761 s (~1h 19m) |
| `nwm30_short_range` | 4 | 8,997 s (~2h 30m) |

Those bin counts are from before the teehr #815 fix; runs after it produce 10 and 3 bins
respectively, and correspondingly slightly less work.

Short range takes longer despite having fewer bins: it is issued far more frequently, so
it contributes many more reference times and therefore more rows.

For scale, the run immediately before this one (same cluster and window, stopped by the
`requests` failure described above) reached ~650 GB of shuffle write with zero evictions
and no executor churn, which is what confirmed the ephemeral-storage fix. Add new
measurements to `profiling.md`.

## Always release the cluster

The run cell wraps the config loop in `try/finally` and calls `spark.stop()` in the
`finally`. This is not tidiness: an exception in the loop does **not** stop the
SparkContext, so a crash partway through leaves the executor pods running and billing --
which happened once overnight at 22 x r5.4xlarge.

Two details worth preserving if you edit that cell:

- **Capture the Spark metrics before stopping.** `capture_spark_run_metrics` reads the
  Spark REST API, which stops answering the moment the session ends, and a crashed run is
  exactly when the executor and stage numbers are worth having. That call is wrapped in its
  own `try` so a failure there can never skip the `spark.stop()`.
- **It stops on success too**, deliberately -- there is no reason to hold 64 executors idle
  once the write has committed. The inspection cells below therefore start their own
  session, guarded with `SparkSession.getActiveSession() is None`. Note `spark._jsc` is
  *not* a usable liveness check: it remains a live `JavaObject` after `stop()` and would
  report a dead session as running.

`finally` cannot help if the kernel itself is killed. After any hard kill, check for
orphans with `kubectl get pods | grep exec`.

## Working on the code

**Adding a dimension** is one entry in `build_dimensions()`. Decide the stage first
(does the level select a row subset, or relabel?), then:

```python
Dimension(
    names=("season",),
    stage=POST_BIN,                       # derived from reference_time -> safe
    calculated_fields=(rcf.Seasons(value_time_field_name="reference_time"),),
    levels=(Level(values=("cast(season as string)",)),),
)
```

Prefer existing teehr calculated fields over hand-written SQL — `rcf.WaterYear`,
`rcf.Seasons`, `rcf.Month`, `rcf.DayOfYear`, `rcf.ForecastLeadTimeBins` all exist and are
Spark-native. `rcf.GenericSQL` is the escape hatch (used for `quarter`).

Note the **frontend hard-codes its dimension names** in
`frontend/src/features/nwmd/hooks/useInitialFilters.ts` and `components/FilterSidebar.tsx`
even though it discovers dimension *values* dynamically. A new dimension reaches the table
and the API automatically, but will not appear in the dashboard without a frontend change.
The API needs nothing.

**Profiling a run.** `utils.profile_spark_stages(spark)` ranks stages by total task time — the
right measure, since wall time hides parallelism and a stage that is 20% of task time cannot be made
to matter more than 20% by tuning it. It also reports disk input against shuffle write; a large ratio
means the run is shuffle-bound and the levers that scale with input (locations, row counts) will
disappoint. A profiled run measured **10.3 GB input against 1,063 GB shuffle write — 104x**.

`utils.profile_spark_sql_plan(spark)` reports operator counts and, more usefully, **repeated table
scans**, counted by output-attribute signature rather than by plan node (the plan description
contains both the initial and AQE-optimized trees, so node counts double). A table scanned more than
once means the plan evaluates the pipeline more than once, and nothing inside the pipeline can
recover that multiple.

Both read the Spark REST API and must run **before** `spark.stop()`; the run cell calls them from its
`finally` for exactly that reason.

**Cheap test runs.** Combine `"location_sample_n": 25` with `"bootstrap_reps": 10` to
exercise the whole pipeline — including the threshold join, both stack shapes, and the
executor-disk path — in a fraction of the runtime. The sample is deterministic given
`location_sample_seed`, and is ordered by a hash of the gage id rather than by the id
itself, since ordering by id returns only the lowest-numbered gages, which are clustered
in the northeast. Note `build_flow_thresholds` is separate and still computes over all
gages unless you narrow its `location_pattern`.

**Testing without a cluster.** The spec is pure Python, so it can be exercised offline
with stubs for `s`/`dm`/`rcf`/`tcf`/`pd` — extract cell 3, drop the
`generate_nwmd_metrics` definition, `exec` the rest, and assert on `spec.group_by_bin`,
`spec.group_by`, `spec.nullable_fields`, `spec.partition_by`. That catches list-derivation
mistakes in seconds.

The generated SQL and the aggregation semantics can be validated against a **local**
`pyspark` session with synthetic rows and stand-ins for teehr's `aggregate`/`write_to`.
The property worth asserting: for a fixed
`(location, lead_time_bin, threshold, window_agg, water_year)`, the `quarter IS NULL`
row's totals must equal the sum over that water year's per-quarter rows. Join **null-safe**
(`eqNullSafe`) when checking — `threshold` is NULL for the no-threshold level and a plain
equi-join silently drops those rows, which is the same trap as the upsert `ON` clause.

**Equivalence when changing the aggregation.** Compare against the previous table with a
null-safe join on the full key and assert zero differing rows in both directions; the
pattern is already written in `query_metrics_tables.ipynb`.

## Known rough edges

- `quarter` is labeled by calendar year, so one water year spans `2025-Q4` and `2026-Q*`.
  Correct but confusing; changing it would break the frontend's
  `getQuarterDateRange()` (`shared/utils/formatters.ts`), which maps `Q1` to Jan–Mar.
- `entity_fields` is read from the live `fcst_joined_timeseries` schema, so a new column
  there silently changes the merge key and the output schema.
- `nwmd_flow_thresholds` must exist before a metrics run; `load_flow_thresholds` raises
  with instructions if it does not. It is not rebuilt automatically, by design.
- Thresholds are computed across `configuration_name` in `primary_timeseries`. If a gage
  ever has two observation configurations for the same variable, they will be blended —
  pass `configuration_name=` to restrict.
- A sampled run is opt-in via `location_sample_n` / `location_ids`, so the default is
  always the full gage set. Check the config before reading results as production numbers —
  `resolve_location_ids` prints `SAMPLED RUN: ...` when a subset is active.
- Adding a dimension changes the output columns, so `MERGE ... INSERT *` will not resolve
  against an existing table; the first run after such a change needs `create_or_replace`.
- `nwmd_metrics_by_location` is absent from the `/collections` listing in
  `api/src/routes/ogc_foundation.py`, which hard-codes its table list. `/items` and
  `/queryables` work fine.
- Three older copies of this pipeline still exist (`01_calculate_nwm_metrics.ipynb`,
  `warehouse/local/nwmd/calculate_nwm_metrics.ipynb`) and will drift.
- There is no Prefect workflow for this table — it is the only production metrics table
  built by hand from a notebook. `prefect-workflows/workflows/metrics/utils/forecast_utils.py`
  is the pattern to follow if it is ever promoted.
