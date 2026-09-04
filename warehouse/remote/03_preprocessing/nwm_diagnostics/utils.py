import os
import json
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timezone

import teehr
import pandas as pd
# from teehr.evaluation.spark_session_utils import create_spark_session

from teehr import DeterministicMetrics as dm
from teehr import Signatures as s
from teehr import RowLevelCalculatedFields as rcf
from teehr import TimeseriesAwareCalculatedFields as tcf
from teehr import Bootstrappers as bs

from teehr.models.filters import TableFilter

from pyspark.sql import functions as F

from pyspark.sql import DataFrame

import copy
import time

teehr.__version__

# --- Resource-sizing instrumentation -----------------------------------------
# Pulls executor/stage summary metrics from the Spark REST API (no external deps,
# works as long as the Spark UI is enabled) so we can right-size the cluster from
# actual numbers instead of guessing. Call capture_spark_run_metrics(spark, ...)
# any time before spark.stop() -- it reads cumulative stats for the session so far.


def _spark_api_get(spark, path):
    ui = spark.sparkContext.uiWebUrl
    if not ui:
        raise RuntimeError("Spark UI is not enabled (uiWebUrl is None) -- can't fetch REST metrics.")
    app_id = spark.sparkContext.applicationId
    port = urlparse(ui).port or 4040
    # uiWebUrl often reports the driver's internal pod IP, which isn't always
    # reachable from within the driver's own process in this environment (seen:
    # "Connection refused"). Try it first, then fall back to loopback addresses
    # on the same port -- Spark's UI Jetty server binds to all interfaces.
    candidates = list(dict.fromkeys([ui, f"http://localhost:{port}", f"http://127.0.0.1:{port}"]))
    last_err = None
    for base in candidates:
        url = f"{base}/api/v1/applications/{app_id}{path}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return json.load(resp)
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Could not reach Spark UI REST API at any of {candidates}: {last_err}")


def spark_config_summary(spark):
    """Compact 'Spark Params' string matching the profiling table's column format."""
    return (
        f"{spark.conf.get('spark.executor.instances', '?')} inst., "
        f"{spark.conf.get('spark.executor.memory', '?')}, "
        f"{spark.conf.get('spark.executor.cores', '?')} cores, "
        f"{spark.conf.get('spark.sql.shuffle.partitions', '?')} part., "
        f"{spark.conf.get('spark.executor.memoryOverhead', 'no')} memOH, "
        f"coalesce={spark.conf.get('spark.sql.adaptive.coalescePartitions.enabled', 'default')}"
    )


def _infer_days_from_filters(filters):
    """Best-effort day-count from reference_time filters, for the profiling row."""
    lo = hi = None
    for f in filters:
        if getattr(f, "column", None) != "reference_time":
            continue
        try:
            ts = datetime.fromisoformat(f.value)
        except Exception:
            continue
        if f.operator in (">", ">="):
            lo = ts if lo is None else min(lo, ts)
        elif f.operator in ("<", "<="):
            hi = ts if hi is None else max(hi, ts)
    return (hi - lo).days if lo and hi else "?"


def capture_spark_run_metrics(spark, label="run"):
    """Summarize executor/stage metrics for this Spark session so far.

    Surfaces exactly the signals needed to right-size a cluster: whether
    executors were lost mid-run (spot preemption), whether memory spilled to
    disk (undersized executor memory for the shuffle partition count), core
    counts (for utilization via report_utilization), and stage failure count.

    Note: peak/max memory here reflects Spark's on-heap *storage* memory pool
    (cache/broadcast), which is largely irrelevant for this notebook's
    pandas_udf-heavy bootstrap stage -- that stage's real memory pressure is
    off-heap Python worker memory, which isn't exposed by this REST endpoint.
    Treat memory-spill and failure/executor-loss counts as the trustworthy
    signals; treat the storage-memory-utilization note as informational only.
    """
    try:
        executors = _spark_api_get(spark, "/executors")
        stages_complete = _spark_api_get(spark, "/stages?status=complete")
        stages_failed = _spark_api_get(spark, "/stages?status=failed")
    except Exception as e:
        print(f"Could not fetch Spark REST metrics: {e}")
        return None

    # Exclude the driver entry -- it reports the driver pod's own (much larger,
    # unrelated) heap size, which otherwise skews max/peak memory calculations.
    worker_executors = [e for e in executors if e.get("id") != "driver"]
    active_executors = [e for e in worker_executors if e.get("isActive", True)]
    removed_executors = [e for e in worker_executors if not e.get("isActive", True)]

    total_gc_ms = sum(e.get("totalGCTime", 0) for e in worker_executors)
    total_duration_ms = sum(e.get("totalDuration", 0) for e in worker_executors)
    total_shuffle_read = sum(e.get("totalShuffleRead", 0) for e in worker_executors)
    total_shuffle_write = sum(e.get("totalShuffleWrite", 0) for e in worker_executors)
    peak_mem_used = max((e.get("memoryUsed", 0) for e in worker_executors), default=0)
    max_mem_avail = max((e.get("maxMemory", 0) for e in worker_executors), default=0)
    total_mem_spill = sum(s.get("memoryBytesSpilled", 0) for s in stages_complete)
    total_disk_spill = sum(s.get("diskBytesSpilled", 0) for s in stages_complete)
    total_cores = sum(e.get("totalCores", 0) for e in active_executors)

    summary = {
        "label": label,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "num_executors_seen": len(worker_executors),
        "num_executors_active": len(active_executors),
        "num_executors_removed": len(removed_executors),
        "total_cores_active": total_cores,
        "peak_executor_memory_used_gb": round(peak_mem_used / 1e9, 2),
        "executor_max_memory_gb": round(max_mem_avail / 1e9, 2),
        "total_gc_time_min": round(total_gc_ms / 1000 / 60, 2),
        "total_task_time_min": round(total_duration_ms / 1000 / 60, 2),
        "total_shuffle_read_gb": round(total_shuffle_read / 1e9, 2),
        "total_shuffle_write_gb": round(total_shuffle_write / 1e9, 2),
        "total_mem_spill_gb": round(total_mem_spill / 1e9, 2),
        "total_disk_spill_gb": round(total_disk_spill / 1e9, 2),
        "num_stages_completed": len(stages_complete),
        "num_stages_failed": len(stages_failed),
    }

    print(json.dumps(summary, indent=2))
    if removed_executors:
        print(
            f"WARNING: {len(removed_executors)} executor(s) were removed/lost during this "
            "run (spot preemption or similar) -- check the Spark UI Executors tab for cause."
        )
    if summary["num_stages_failed"] > 0:
        print(f"WARNING: {summary['num_stages_failed']} stage(s) failed during this run.")
    if summary["total_disk_spill_gb"] > 0:
        print(
            f"NOTE: {summary['total_disk_spill_gb']} GB spilled to disk -- executor memory "
            "may be undersized for the current shuffle partition count."
        )

    return summary


def report_utilization(run_metrics, wall_seconds):
    """Core utilization = total task-time / (wall_clock x active cores).

    Call after capture_spark_run_metrics with the same run's elapsed_seconds.
    Low utilization (well under 1.0) suggests too many cores/executors for the
    actual parallel work available (or a skew/coalescing bottleneck); high
    utilization near 1.0 means the cluster was busy essentially the whole time.
    """
    if not run_metrics or not run_metrics.get("total_cores_active"):
        print("No utilization data available.")
        return None
    core_minutes_available = wall_seconds / 60 * run_metrics["total_cores_active"]
    pct = run_metrics["total_task_time_min"] / core_minutes_available if core_minutes_available else 0
    print(f"Core utilization: {pct:.0%} ({run_metrics['total_task_time_min']:.1f} task-min / "
          f"{core_minutes_available:.1f} core-min available)")
    return pct

# --- Stage-attempt failure detail -----------------------------------------
# /stages?status=failed only reports stages whose FINAL status is failed -- a
# stage that fails once and succeeds on retry shows as "complete" overall, so
# it's invisible there even though the retry cost real wall-clock time. This
# queries each stage's full attempt history (including successful-after-retry
# ones) via /stages/{stageId} and surfaces the actual failureReason per failed
# attempt, so we don't need to read it off the Spark UI by hand.
def get_stage_attempt_failures(spark, max_stages=200):
    stage_summaries = (
        _spark_api_get(spark, "/stages?status=complete")
        + _spark_api_get(spark, "/stages?status=failed")
    )
    stage_ids = sorted({s["stageId"] for s in stage_summaries})[:max_stages]

    failures = []
    for stage_id in stage_ids:
        try:
            attempts = _spark_api_get(spark, f"/stages/{stage_id}")
        except Exception as e:
            print(f"Could not fetch stage {stage_id}: {e}")
            continue
        if not isinstance(attempts, list):
            attempts = [attempts]
        for a in attempts:
            if a.get("status") == "FAILED" or a.get("failureReason"):
                failures.append({
                    "stageId": stage_id,
                    "attemptId": a.get("attemptId"),
                    "status": a.get("status"),
                    "numCompleteTasks": a.get("numCompleteTasks"),
                    "numFailedTasks": a.get("numFailedTasks"),
                    "failureReason": a.get("failureReason"),
                })

    if not failures:
        print("No failed stage attempts found (checked stage IDs: "
              f"{stage_ids[0]}-{stage_ids[-1]}).")
        return []

    print(f"Found {len(failures)} failed stage attempt(s):\n")
    for f in failures:
        print(f"Stage {f['stageId']} attempt {f['attemptId']} "
              f"({f['numCompleteTasks']} complete / {f['numFailedTasks']} failed tasks):")
        print(f"  {f['failureReason']}\n")
    return failures

def create_ondemand_pod_template():
    """Create a pod template for on-demand Spark executors.

    Returns:
        str: Path to the generated pod template YAML file.
    """
    

    # Alternate executor pod template targeting the ON-DEMAND `nb-r5-4xlarge-teehr`
    # node group instead of the spot `spark-r5-4xlarge-spot` pool, for tuning runs
    # where we want clean measurements without spot-interruption noise. Same
    # instance type (r5.4xlarge) so executor sizing math stays comparable to prior
    # spot-based runs. Different taint on this node group (hub.jupyter.org/dedicated
    # =user vs teehr-hub/dedicated=worker), so it needs its own tolerations.
    ONDEMAND_POD_TEMPLATE_PATH = os.path.expanduser("~/executor-pod-template-ondemand.yaml")

    with open(ONDEMAND_POD_TEMPLATE_PATH, "w") as f:
        f.write("""apiVersion: v1
kind: Pod
spec:
terminationGracePeriodSeconds: 60
securityContext:
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
containers:
- name: spark-kubernetes-executor
    securityContext:
    runAsUser: 1000
    runAsGroup: 1000
    allowPrivilegeEscalation: false
    lifecycle:
    preStop:
        exec:
        command: ["/bin/sh", "-c", "sleep 30"]
    volumeMounts:
    - name: data-nfs
    mountPath: /data
volumes:
- name: data-nfs
    persistentVolumeClaim:
    claimName: data-nfs
tolerations:
- effect: "NoSchedule"
    key: "hub.jupyter.org/dedicated"
    operator: "Equal"
    value: "user"
- effect: "NoSchedule"
    key: "hub.jupyter.org_dedicated"
    operator: "Equal"
    value: "user"
nodeSelector:
    teehr-hub/nodegroup-name: nb-r5-4xlarge
    """)

    print(f"Wrote alternate pod template to {ONDEMAND_POD_TEMPLATE_PATH}")
    return ONDEMAND_POD_TEMPLATE_PATH


def generate_nwmd_metrics(spark, config):
    """Generate the teehr.nwmd_metrics_by_location table for the given config.

    config format:
        {
            "configurations": ["nwm30_medium_range"],
            "forecast_lead_time_bin_hours": 24,
            "start_reference_time": "2025-10-01T00:00",
            "end_reference_time": "2026-10-01T00:00"
        },

    Args:
        spark (SparkSession): The Spark session to use for processing.
        config (dict): Configuration dictionary containing necessary parameters.
    """
    # Placeholder for the actual implementation of generating metrics.
    # This function should include the logic to process the data and populate
    # the teehr.nwmd_metrics_by_location table based on the provided config.

    configurations = config.get("configurations")
    forecast_lead_time_bin_hours = config.get("forecast_lead_time_bin_hours")
    start_reference_time = config.get("start_reference_time")
    end_reference_time = config.get("end_reference_time")

    # pod_template_path = create_ondemand_pod_template()

    # spark = create_spark_session(
    #     start_spark_cluster=True,
    #     executor_instances=64,
    #     executor_memory="16g",
    #     executor_cores=2,
    #     aws_profile="default",
    #     pod_template_path=pod_template_path,
    #     update_configs={
    #         "spark.sql.shuffle.partitions": 1024,
    #         "spark.sql.adaptive.coalescePartitions.enabled": "false",
    #         "spark.kubernetes.executor.annotation.cluster-autoscaler.kubernetes.io/safe-to-evict": "false",
    #         "spark.executorEnv.TEEHR_BOOTSTRAP_ENGINE": "vectorized",
    #         "spark.executor.memoryOverhead": "4g",
    #     }
    # )

    start = time.perf_counter()

    ev = teehr.RemoteReadWriteEvaluation(spark=spark, enable_spark_proxy=True)

    joined_cols = ev.table("fcst_joined_timeseries").to_sdf().columns
    non_unique_fields = ['primary_value','secondary_value','created_at','updated_at', "value_time"]
    uniquenes_fields = [c for c in joined_cols if c not in non_unique_fields]
    print(f"Unique fields for grouping: {uniquenes_fields}")

    ids = ev.locations.filter("id like 'usgs-%'").to_sdf().select("id")
    sample = ids.sample(False, 0.5, seed=456).limit(10).collect()
    location_ids = [r.id for r in sample]
    print("Number of location_ids:", len(location_ids))

    # spark.sql("""
    # USE iceberg.teehr
    # """)
    # rows = spark.sql("""
    # SELECT distinct primary_location_id FROM fcst_joined_timeseries
    # """).collect()
    # location_ids = [r.primary_location_id for r in rows]
    # print(len(location_ids))

    filters = [
        TableFilter(
            column="configuration_name",
            operator="in",
            value=configurations
        ),
        TableFilter(
            column="reference_time",
            operator=">=",
            value=start_reference_time,
        ),
        TableFilter(
            column="reference_time",
            operator="<",
            value=end_reference_time,
        ),
        TableFilter(
            column="primary_location_id",
            operator="in",
            value=location_ids
        )
    ]   

    # Define the above percentile event detection calculated fields for 85th, 95th, and 99th percentiles.
    # Note: both the threshold and event detection are based on the primary_value field.  
    # This may differ from the way it is done in the NWM Explorer.  Does the NWM Explorer use the primary_value 
    # of the threshold definition but the secondary_value field for event detection?

    remove_for_quantiles = ["secondary_location_id", "reference_time", "member"]
    quantile_group = [c for c in uniquenes_fields if c not in remove_for_quantiles]

    calculated_fields = [
        rcf.GenericSQL(
            output_field_name="quarter",
            sql_statement="CONCAT(YEAR(reference_time), '-Q', QUARTER(reference_time))"
        ),
        rcf.ForecastLeadTimeBins(
            bin_size=pd.Timedelta(hours=forecast_lead_time_bin_hours),
            output_field_name="forecast_lead_time_bin"
        ),
        tcf.AbovePercentileEventDetection(
            quantile=0.85,
            output_event_field_name="above_q85",
            skip_event_id=True,
            value_field_name="primary_value",
            uniqueness_fields=quantile_group
        ),
        tcf.AbovePercentileEventDetection(
            quantile=0.95,
            output_event_field_name="above_q95",
            skip_event_id=True,
            value_field_name="primary_value",
            uniqueness_fields=quantile_group
        ),
        tcf.AbovePercentileEventDetection(
            quantile=0.99,
            output_event_field_name="above_q99",
            skip_event_id=True,
            value_field_name="primary_value",
            uniqueness_fields=quantile_group
        )
    ]   

    # Get raw joined timeseries
    tbl = ev.table("fcst_joined_timeseries").filter(filters).add_calculated_fields(calculated_fields)       

    # Stack thresholds
    threshold_cols = ["above_q85", "above_q95", "above_q99"]
    threshold_stack_base_cols = [c for c in tbl.columns if c not in threshold_cols]
    # print(f"Stacking thresholds: {threshold_cols} with base columns: {threshold_stack_base_cols}")

    joined_timeseries_with_thresholds_tbl = (
        tbl.selectExpr(
            *threshold_stack_base_cols,
            """
            stack(
                4,
                cast(null as string), true,
                'above_q85', above_q85,
                'above_q95', above_q95,
                'above_q99', above_q99
            ) as (threshold, keep_row)
            """
        )
        .where("keep_row")
        .select(*threshold_stack_base_cols, "threshold")   # no .drop()
    )

    # print(f"no threshold_rows: {joined_timeseries_with_thresholds_tbl.where("threshold is NULL").count()}")
    # print(f"threshold_rows: {joined_timeseries_with_thresholds_tbl.where("threshold is not NULL").count()}")
    # print(f"total: {joined_timeseries_with_thresholds_tbl.count()}")

    # Add window aggregations
    window_metrics = [
        s.Average(
            primary_field_name="primary_value",
            output_field_name="mean_primary_value"
        ),
        s.Average(
            primary_field_name="secondary_value",
            output_field_name="mean_secondary_value"
        ),
        s.Minimum(
            primary_field_name="primary_value",
            output_field_name="min_primary_value"
        ),
        s.Minimum(
            primary_field_name="secondary_value",
            output_field_name="min_secondary_value"
        ),
        s.Maximum(
            primary_field_name="primary_value",
            output_field_name="max_primary_value"
        ),
        s.Maximum(
            primary_field_name="secondary_value",
            output_field_name="max_secondary_value"
        ),
        s.Count(
            primary_field_name="secondary_value",
            output_field_name="n_in_bin"
        )
    ]

    group_by_bin = [*uniquenes_fields, "quarter", "forecast_lead_time_bin", "threshold"]
    # print(f"Grouping by: {group_by_bin}")

    bin_aggs_tbl = joined_timeseries_with_thresholds_tbl.aggregate(
        group_by=group_by_bin,
        metrics=window_metrics
    )
    # print(f"bin_aggs: {bin_aggs_tbl.count()}")

    pivoted_bin_aggs_tbl = bin_aggs_tbl.selectExpr(
        *group_by_bin,
        """
        stack(
            3,
            'mean', mean_primary_value, mean_secondary_value,
            'min',  min_primary_value,  min_secondary_value,
            'max',  max_primary_value,  max_secondary_value
        ) as (window_agg, primary_value, secondary_value)
        """
    )
    # print(f"pivoted_bin_aggs: {pivoted_bin_aggs_tbl.count()}")

    # Configure bootstrap
    bootstrap = bs.Stationary(
        reps=1000,
        seed=1234,
        quantiles=[0.025, 0.975]
    )

    metrics = [
        s.Count(),
        s.Average(),
        s.Minimum(),
        s.Maximum(),
        dm.RelativeMean(),
        dm.RelativeMedian(),
        dm.RelativeMinimum(),
        dm.RelativeMaximum(),
        dm.RelativeStandardDeviation(),
        dm.RelativeBias(
            add_epsilon=True,
        ),
        dm.NashSutcliffeEfficiency(
            add_epsilon=True,
        ),
        dm.KlingGuptaEfficiency(
            add_epsilon=True,
        ),
        dm.PearsonCorrelation(
            add_epsilon=True,
        ),
        # NOTE: unpack_results is intentionally NOT set on the bootstrap metrics below.
        # teehr's default unpack path (post_process_metric_results -> unpack_sdf_dict_columns)
        # calls sdf.select(column_name).first() once per metric with unpack_results=True -- a
        # real Spark action that retriggers the entire upstream lazy DAG once per metric (9x
        # here) and is the confirmed cause of the "ShuffleMapStage ... first at
        # teehr/querying/utils.py:207" crashes and nondeterministic same-config failures seen
        # in the profiling table above. We unpack manually after aggregation instead (see the
        # unpack_quantile_bootstrap_columns cell below), which needs no Spark action since the
        # quantile keys are already known statically from `bootstap.quantiles`.
        dm.RelativeMean(
            output_field_name="relative_mean_boot",
            bootstrap=bootstrap,
        ),
        dm.RelativeMedian(
            output_field_name="relative_median_boot",
            bootstrap=bootstrap,
        ),
        dm.RelativeMinimum(
            output_field_name="relative_minimum_boot",
            bootstrap=bootstrap,
        ),
        dm.RelativeMaximum(
            output_field_name="relative_maximum_boot",
            bootstrap=bootstrap,
        ),
        dm.RelativeStandardDeviation(
            output_field_name="relative_standard_deviation_boot",
            bootstrap=bootstrap,
        ),
        dm.NashSutcliffeEfficiency(
            output_field_name="nash_sutcliffe_efficiency_boot",
            bootstrap=bootstrap,
        ),
        dm.RelativeBias(
            output_field_name="relative_bias_boot",
            bootstrap=bootstrap,
        ),
        dm.PearsonCorrelation(
            output_field_name="pearson_correlation_boot",
            bootstrap=bootstrap,
        ),
        dm.KlingGuptaEfficiency(
            output_field_name="kling_gupta_efficiency_boot",
            bootstrap=bootstrap,
        ),
    ]

    group_by = [
        "primary_location_id",
        "secondary_location_id",
        "configuration_name",
        "unit_name",
        "variable_name",
        "member",
        "quarter",
        "forecast_lead_time_bin",
        "threshold",
        "window_agg",
    ]

    results = pivoted_bin_aggs_tbl.aggregate(
        group_by=group_by,
        metrics=metrics
    )

    def unpack_quantile_bootstrap_columns(table, metrics):
        sdf = table.to_sdf()
        for m in metrics:
            if not getattr(m, "bootstrap", None):
                continue
            for q in m.bootstrap.quantiles:
                key = f"{m.output_field_name}_{q}"
                sdf = sdf.withColumn(key.replace(".", "_"), F.col(m.output_field_name).getItem(key))
            sdf = sdf.drop(m.output_field_name)
        return table._with_sdf(sdf)

    results = unpack_quantile_bootstrap_columns(results, metrics)

    results = results.order_by(group_by).add_geometry()

    # print(results.explain(mode="simple"))

    # NOTE: pointed at a *_test table while validating the unpack_results/.first() fix so we
    # don't overwrite the useful existing results in nwmd_metrics_by_location. Repoint back to
    # "nwmd_metrics_by_location" only after full-scale validation succeeds consistently.
    table_name = "nwmd_metrics_by_location_test"

    nullables = ["member", "threshold"]
    table_exists = ev.spark.catalog.tableExists(f"iceberg.teehr.{table_name}")

    if table_exists:
        results.write_to(
            table_name=table_name,
            write_mode="upsert",
            uniqueness_fields=[column for column in group_by if column not in nullables],
            nullable_fields=nullables,
            partition_by=["quarter"],
        )
    else:
        results.write_to(
            table_name=table_name,
            write_mode="create_or_replace",
            partition_by=["quarter"],
        )

    # Read the metric column names off the written result rather than off the metric
    # models. The bootstrap metrics' MapType columns are replaced by one column per
    # quantile (e.g. relative_mean_boot -> relative_mean_boot_0_025, _0_975), so
    # `metric.output_field_name` would advertise columns that don't exist in the
    # table. `.columns` is schema-only, so this costs no Spark action.
    # "name" and "geometry" come from add_geometry(), not from a metric.
    non_metric_columns = set(group_by) | {"name", "geometry"}
    metric_columns = [
        c for c in results.to_sdf().columns if c not in non_metric_columns
    ]

    properties = {
        "description": "NWM diagnostics metrics by location ID",
        "group_by": ", ".join(group_by),
        "metrics": ", ".join(metric_columns)
    }

    for key, value in properties.items():
        ev.spark.sql(f"""
            ALTER TABLE iceberg.teehr.{table_name} SET TBLPROPERTIES ('{key}' = '{value}')
        """)

    end = time.perf_counter()

    elapsed_seconds = end - start
    print(f"{elapsed_seconds:.6f} s")

    # Capture resource-usage metrics for this run BEFORE spark.stop() (the REST API
    # stops responding once the session ends). Paste the printed markdown row into
    # the Profiling table above to keep a running record.
    # n_locations = len(location_ids) if "location_ids" in globals() else "All"
    # n_days = _infer_days_from_filters(filters)

    # run_metrics = capture_spark_run_metrics(spark, label=f"{n_locations} locations, {n_days} days")
    # report_utilization(run_metrics, elapsed_seconds)

    # print(
    #     f"\n| {n_locations} | {n_days} | {bootstap.reps} | Cluster - {spark_config_summary(spark)} "
    #     f"| {elapsed_seconds:.0f}s | (see run_metrics above) |"
    # )

    # Run this against the still-live session (spark.stop() is commented out below)
    # to see the actual failure reason for the retried/failed stages from this run,
    # without needing to read it off the Spark UI by hand.
    # stage_failures = get_stage_attempt_failures(spark)

    # spark.stop()