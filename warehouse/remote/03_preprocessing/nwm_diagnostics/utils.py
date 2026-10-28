"""Cluster-sizing instrumentation and pod templates for the NWM diagnostics runs.

The metrics pipeline itself (`generate_nwmd_metrics`) lives in nwmd_metrics.ipynb,
so this module holds only helpers that are useful across notebooks and that the
notebooks pull in via the raw.githubusercontent download in their second cell.

The high-flow threshold definitions at the bottom are here for exactly that
reason: nwmd_flow_thresholds.ipynb writes the table and nwmd_metrics.ipynb reads
it, and the two MUST agree on the table name and the quantile list. Duplicating
them in both notebooks would let them drift, and the failure is silent -- the
metrics run would simply find no matching quantiles, join NULL thresholds and
put every row in the "all rows" level.
"""

import os
import json
import re
import time
import urllib.request
from collections import Counter
from urllib.parse import urlparse
from datetime import datetime, timezone

import teehr
from pyspark.sql import functions as F

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
        # /allexecutors, NOT /executors. The latter returns only executors the
        # driver still knows about, so a run that lost and replaced executors
        # reports num_executors_removed = 0 and looks healthy. This misdiagnosed
        # two separate failures: the giveaway both times was the executor ID
        # range running past the requested instance count.
        executors = _spark_api_get(spark, "/allexecutors")
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

    # Independent churn check that does not rely on the endpoint reporting dead
    # executors: Spark numbers executors sequentially from 1, so a maximum ID
    # above the requested instance count means executors were replaced.
    executor_ids = [
        int(e["id"]) for e in worker_executors if str(e.get("id", "")).isdigit()
    ]
    max_executor_id = max(executor_ids, default=0)
    requested_instances = int(
        spark.conf.get("spark.executor.instances", "0") or 0
    )
    replacements = max(0, max_executor_id - requested_instances)

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
        "max_executor_id": max_executor_id,
        "requested_instances": requested_instances,
        "executors_replaced": replacements,
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
    if replacements:
        print(
            f"WARNING: at least {replacements} executor(s) were replaced during this run "
            f"(max executor id {max_executor_id} > {requested_instances} requested). "
            "Executors died even if num_executors_removed is 0. Their shuffle output "
            "dies with them, which surfaces downstream as "
            "'Missing an output location for shuffle N'. To find out WHY, re-run with "
            "spark.kubernetes.executor.deleteOnTermination=false so the dead pods "
            "survive, then: kubectl describe pod <exec-pod> | tail -20"
        )
    if removed_executors:
        print(
            f"WARNING: {len(removed_executors)} executor(s) were removed/lost during this "
            "run. Reasons reported by the driver:"
        )
        # /allexecutors carries removeReason for dead executors, which usually
        # names the cause outright -- OOMKilled, evicted, deleted by
        # Kubernetes, unable to create executor -- so this normally settles
        # "why did they die" without needing deleteOnTermination=false.
        reasons = Counter()
        for e in removed_executors:
            reason = (e.get("removeReason") or "unknown").strip()
            reasons[" ".join(reason.split())[:200]] += 1
        for reason, count in reasons.most_common(6):
            print(f"    {count:>3}x  {reason}")
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

# --- Where did the time go? -----------------------------------------------
# capture_spark_run_metrics answers "was the cluster healthy"; these two answer
# "what was slow". Both read the Spark REST API and must run BEFORE spark.stop().


def profile_spark_stages(spark, top=12, min_task_min=0.5):
    """Rank stages by total task time, with the IO that explains them.

    Total task time (executorRunTime summed over tasks) is the right measure of
    where compute goes -- wall time hides parallelism, and a stage that is 20%
    of task time cannot be made to matter more than 20% by tuning it.

    Watch the input-vs-shuffle columns. A job whose disk input is small but
    whose shuffle write is large is shuffle-bound, and tuning the things that
    scale with input (locations, row counts) will disappoint. This pipeline
    multiplies rows 4x for thresholds pre-bin and 6x post-bin, so the
    expansion, not the scan, is usually the cost.

    Returns the rows so they can be diffed between runs.
    """
    try:
        stages = _spark_api_get(spark, "/stages")
    except Exception as e:
        print(f"Could not fetch Spark stages: {e}")
        return None

    def _parse(value):
        if not value:
            return None
        try:
            return datetime.strptime(value[:23], "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            return None

    rows = []
    for s in stages:
        started, finished = _parse(s.get("submissionTime")), _parse(s.get("completionTime"))
        rows.append({
            "stage": f"{s['stageId']}.{s['attemptId']}",
            "status": s.get("status", "?"),
            "task_min": s.get("executorRunTime", 0) / 60000,
            "wall_s": (finished - started).total_seconds() if started and finished else None,
            "tasks": s.get("numTasks", 0),
            "complete": s.get("numCompleteTasks", 0),
            "failed": s.get("numFailedTasks", 0),
            "input_gb": s.get("inputBytes", 0) / 1e9,
            "shuffle_read_gb": s.get("shuffleReadBytes", 0) / 1e9,
            "shuffle_write_gb": s.get("shuffleWriteBytes", 0) / 1e9,
            "disk_spill_gb": s.get("diskBytesSpilled", 0) / 1e9,
        })

    total_task_min = sum(r["task_min"] for r in rows) or 1.0
    ranked = sorted(rows, key=lambda r: -r["task_min"])

    print(
        f"{'stage':>8} {'status':9} {'task-min':>9} {'share':>6} {'wall-s':>7} "
        f"{'tasks':>10} {'in GB':>7} {'shufR':>8} {'shufW':>8} {'spill':>6}"
    )
    for r in ranked[:top]:
        if r["task_min"] < min_task_min:
            continue
        wall = f"{r['wall_s']:.0f}" if r["wall_s"] is not None else "-"
        tasks = f"{r['complete']}/{r['tasks']}"
        print(
            f"{r['stage']:>8} {r['status']:9} {r['task_min']:9.1f} "
            f"{100 * r['task_min'] / total_task_min:5.1f}% {wall:>7} {tasks:>10} "
            f"{r['input_gb']:7.1f} {r['shuffle_read_gb']:8.1f} "
            f"{r['shuffle_write_gb']:8.1f} {r['disk_spill_gb']:6.1f}"
        )

    total_input = sum(r["input_gb"] for r in rows)
    total_write = sum(r["shuffle_write_gb"] for r in rows)
    print(f"\ntotal task time: {total_task_min:.0f} task-min across {len(rows)} stages")
    print(f"disk input: {total_input:.1f} GB | shuffle write: {total_write:.1f} GB", end="")
    if total_input > 0:
        print(f" | amplification: {total_write / total_input:.0f}x")
    else:
        print()
    if total_input and total_write / total_input > 5:
        print(
            "NOTE: shuffle write greatly exceeds disk input -- this run is "
            "shuffle-bound. Reducing locations or bootstrap reps will help far "
            "less than reducing the row-expansion factor or the number of passes "
            "over the pipeline (see profile_spark_sql_plan)."
        )
    return ranked


def profile_spark_sql_plan(spark, execution_id=None):
    """Report operator counts and REPEATED TABLE SCANS for one SQL execution.

    The thing worth catching here is a table scanned more than once. That means
    the plan evaluates the pipeline more than once, and no amount of tuning
    inside the pipeline will recover the multiple. Iceberg's MERGE is the usual
    culprit: it evaluates its source several times, so an `upsert` can run the
    whole bootstrap and shuffle chain three times over where an
    `INSERT OVERWRITE` runs it once.

    Pass execution_id to target a specific query; by default the longest-running
    one is profiled.
    """
    try:
        executions = _spark_api_get(spark, "/sql?length=100")
    except Exception as e:
        print(f"Could not fetch Spark SQL executions: {e}")
        return None
    if not executions:
        print("No SQL executions recorded.")
        return None

    if execution_id is None:
        chosen = max(executions, key=lambda e: e.get("duration", 0))
    else:
        matches = [e for e in executions if e.get("id") == execution_id]
        if not matches:
            print(f"No SQL execution with id {execution_id}.")
            return None
        chosen = matches[0]

    exec_id = chosen.get("id")
    print(
        f"SQL execution {exec_id}: status={chosen.get('status')} "
        f"duration={chosen.get('duration', 0) / 1000:.0f}s"
    )

    try:
        detail = _spark_api_get(
            spark, f"/sql/{exec_id}?details=true&planDescription=true"
        )
        plan = detail.get("planDescription") or ""
    except Exception as e:
        print(f"Could not fetch the plan description: {e}")
        return None

    # The plan text lists the operator tree and then numbered node details;
    # count only the numbered headers so each operator is counted once.
    operators = Counter(re.findall(r"^\(\d+\)\s+(\S+)", plan, re.M))
    print("\noperators:")
    for name, count in operators.most_common(14):
        print(f"  {count:>4}  {name}")

    # Count DISTINCT scans by their output-attribute signature, not by numbered
    # plan nodes: the plan description contains both the initial and the
    # AQE-optimized plan, so node counts double-count. Two scan nodes that emit
    # the same attribute ids are the same scan printed twice; different ids mean
    # genuinely separate evaluations.
    scans = Counter()
    for table, attrs in re.findall(
        r"^\(\d+\)\s+BatchScan (\S+).*?\n\s*Output \[\d+\]: \[([^\]]*)\]",
        plan,
        re.M | re.S,
    ):
        scans[(table, attrs.strip())] += 1
    per_table = Counter(table for table, _ in scans)
    if not per_table:  # older Spark / different plan formatting
        per_table = Counter(re.findall(r"^\(\d+\)\s+BatchScan (\S+)", plan, re.M))

    print("\ndistinct table scans in this plan:")
    repeated = []
    for table, count in per_table.most_common():
        flag = ""
        if count > 1:
            flag = "  <-- evaluated more than once"
            repeated.append((table, count))
        print(f"  {count:>4}  {table}{flag}")

    if repeated:
        worst = max(count for _, count in repeated)
        print(
            f"\nWARNING: the pipeline is evaluated {worst}x in this plan. "
            f"{'MergeRows present -- this is an Iceberg MERGE (upsert). ' if operators.get('MergeRows') else ''}"
            "Everything inside the pipeline pays that multiple, so it dominates "
            "any tuning of reps, locations or partition counts. Consider "
            "write_mode='overwrite' with "
            "spark.sql.sources.partitionOverwriteMode=dynamic, which writes in "
            "one pass, when the run rebuilds whole partitions."
        )
    return {
        "execution_id": exec_id,
        "operators": dict(operators),
        "scans": dict(per_table),
    }


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

def create_ondemand_pod_template(ephemeral_storage_request="40Gi"):
    """Create a pod template for on-demand Spark executors.

    Args:
        ephemeral_storage_request (str): Disk to reserve per executor for shuffle
            (SPARK_LOCAL_DIRS). See the note below -- this is not cosmetic.

    Returns:
        str: Path to the generated pod template YAML file.
    """

    # Executor pod template targeting the ON-DEMAND `spark-r5-4xlarge` node group,
    # not the spot `spark-r5-4xlarge-spot` pool: this job writes once at the very
    # end, so a spot reclaim at hour 3 destroys the entire run, and tuning runs
    # need measurements free of spot-interruption noise. Same instance type
    # (r5.4xlarge) so executor sizing math stays comparable to prior spot runs.
    #
    # 2026-09-09: was `nb-r5-4xlarge`. That choice predates the non-spot
    # `spark-r5-4xlarge` group (terraform/eks.tf:396) and read as "on-demand OR
    # spot" when the real choice is now "on-demand worker pool OR the pool
    # JupyterHub spawns user servers into". Executors were landing on the
    # notebook pool -- 15 of the 16 nodes in use -- where a user server can
    # displace an executor. At executor_cores=3 a node is ~95% committed on both
    # CPU and memory, so that contention is no longer cheap. The worker group
    # carries the same 300 GB gp3 volumes (local.spark_executor_block_device_
    # mappings, eks.tf:399) and scales from desired_size=0, so nothing is lost.
    # NOTE the taints differ (teehr-hub/dedicated=worker vs
    # hub.jupyter.org/dedicated=user) -- the tolerations below MUST change with
    # the nodeSelector or the pods sit unschedulable.
    #
    # ephemeral-storage request: 2026-09-06, a full-dataset run died with ~55
    # executor evictions ("The node was low on resource: ephemeral-storage") and
    # the resulting FetchFailedException / "Missing an output location for shuffle
    # N" cascade -- 71 of 135 executors were replaced before the job aborted.
    # Spark puts SPARK_LOCAL_DIRS on an emptyDir backed by the node's root volume
    # (r5.4xlarge has no instance store: ~71Gi allocatable, kubelet evicts under
    # 8Gi free), 5-6 executors shared each node, and the pods requested NO
    # ephemeral-storage at all -- so the scheduler could not account for shuffle
    # disk, AND kubelet ranks eviction victims by usage over request, which put
    # the executors first in line every time. Declaring a request fixes both:
    # it spreads executors across enough nodes and buys eviction immunity up to
    # the requested amount.
    #
    # 2026-09-09: raised 20Gi -> 40Gi. A run wrote 1,243 GB of shuffle, ~19.4 GB
    # per executor against the 20Gi request -- no headroom -- and 11 executors
    # were lost. The node groups that run executors now carry 300 GB gp3 root
    # volumes instead of 80 GB (teehr-cloud-platform, spark-executor-node-disk),
    # so the request should match where MEMORY binds rather than where disk
    # does: 6 executors per r5.4xlarge at 20 GiB each. 40Gi x 6 = 240 GiB of the
    # ~290 GiB now allocatable. Leaving it at 20Gi would have let the scheduler
    # pack 14 per node and oversubscribe memory instead.
    #
    # Verify it survived Spark's own resource settings after launch with:
    #   kubectl get pod <exec-pod> -o jsonpath='{.spec.containers[0].resources}'
    ONDEMAND_POD_TEMPLATE_PATH = os.path.expanduser("~/executor-pod-template-ondemand.yaml")

    with open(ONDEMAND_POD_TEMPLATE_PATH, "w") as f:
        f.write(f"""apiVersion: v1
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
    resources:
      requests:
        ephemeral-storage: {ephemeral_storage_request}
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
    key: "teehr-hub/dedicated"
    operator: "Equal"
    value: "worker"
  - effect: "NoSchedule"
    key: "teehr-hub_dedicated"
    operator: "Equal"
    value: "worker"
  nodeSelector:
    teehr-hub/nodegroup-name: spark-r5-4xlarge
    """)

    print(
        f"Wrote alternate pod template to {ONDEMAND_POD_TEMPLATE_PATH} "
        f"(ephemeral-storage request: {ephemeral_storage_request})"
    )
    return ONDEMAND_POD_TEMPLATE_PATH


# --- High-flow thresholds --------------------------------------------------
# Thresholds are CLIMATOLOGICAL: fixed percentiles of each gage's own observed
# period of record, computed once from primary_timeseries, persisted, and joined
# on at run time.
#
# They used to be derived inline by tcf.AbovePercentileEventDetection over the
# filtered joined timeseries, which was wrong three ways:
#
#   1. the percentile moved whenever the run's reference_time window moved, so
#      rows written by different runs were not comparable, and re-running a
#      single quarter silently redefined its own thresholds;
#   2. each observed hour appears in the joined table once per reference_time
#      that forecasts it, so the distribution being quantiled was weighted by
#      forecast coverage rather than being the observed distribution; and
#   3. it was grouped by configuration_name (and each configuration is a
#      separate run anyway), so `above_q85` meant something DIFFERENT for short
#      range than for medium range at the same gage -- which quietly undermined
#      comparing configurations.
#
# Reading them from primary_timeseries over the full record fixes all three, and
# replaces an applyInPandas UDF (plus its shuffle, and its habit of pulling a
# whole gage's series into pandas) with a broadcast join and a column compare.
#
# The table is built by nwmd_flow_thresholds.ipynb and read by
# nwmd_metrics.ipynb (load_flow_thresholds / join_flow_thresholds).

THRESHOLD_TABLE = "nwmd_flow_thresholds"
THRESHOLD_QUANTILES = (0.85, 0.95, 0.99)


def event_col(quantile) -> str:
    """The one place a quantile maps to its event-flag column name."""
    return f"above_q{int(quantile * 100)}"


def threshold_value_col(quantile) -> str:
    """The one place a quantile maps to its joined threshold-value column."""
    return f"threshold_q{int(quantile * 100)}"


VARIABLE_JOIN_KEY = "_variable_join_key"


def variable_join_key_sql(column="variable_name") -> str:
    """SQL for the key that matches an observed variable to a forecast one.

    Mirrors teehr's own rule in JoinedTimeseriesView._perform_join: a
    variable_name is `{parameter}_{period}_{statistic}`, and for the `inst`
    statistic the PERIOD IS IGNORED. That matters here because observations
    arrive as `streamflow_none_inst` while forecasts are
    `streamflow_hourly_inst` -- the same physical quantity, and the joined
    timeseries already treats them as such. Joining thresholds on the raw
    variable_name therefore matches nothing.

    Non-inst variables must still match in full, so a daily mean cannot be
    silently compared against an instantaneous value.
    """
    # get() rather than [] : under ANSI mode an out-of-range array index raises
    # instead of returning NULL, so a variable_name with fewer than three
    # underscore-separated parts would crash the whole run. teehr's own join SQL
    # guards this with an explicit size() check.
    parts = f"split({column}, '_')"
    return (
        f"CASE WHEN get({parts}, 2) = 'inst' "
        f"THEN concat_ws('_', get({parts}, 0), get({parts}, 2)) "
        f"ELSE {column} END"
    )


def build_flow_thresholds(
    spark,
    quantiles=THRESHOLD_QUANTILES,
    output_table_name=THRESHOLD_TABLE,
    location_pattern="usgs-%",
    configuration_name=None,
):
    """Compute and persist per-gage high-flow thresholds from primary_timeseries.

    Run this once. Run it again only when you deliberately want the thresholds
    to move (say after a large observation backfill) -- every metrics run reads
    the persisted values, which is what keeps a re-run of one quarter
    comparable with its neighbors.

    Percentiles are exact (`percentile`, not `percentile_approx`) so the result
    is reproducible, and are taken over ALL observed values for a gage,
    across configuration_name, since a threshold is a property of the river
    rather than of whichever ingest produced the observation. Rows with a NULL
    value are excluded; zeros are kept, as zero flow is meaningful.

    Args:
        spark (SparkSession): The Spark session to use.
        quantiles (tuple): Percentiles to compute, as fractions.
        output_table_name (str): Table to create or replace.
        location_pattern (str): SQL LIKE pattern limiting which gages to
            compute for. None for all.
        configuration_name (str): Restrict to one observation configuration.
            None (default) uses every configuration present.
    """
    start = time.perf_counter()
    ev = teehr.RemoteReadWriteEvaluation(spark=spark, enable_spark_proxy=True)

    sdf = ev.table("primary_timeseries").to_sdf().where(F.col("value").isNotNull())
    if location_pattern:
        sdf = sdf.where(F.col("location_id").like(location_pattern))
    if configuration_name:
        sdf = sdf.where(F.col("configuration_name") == configuration_name)

    qs = list(quantiles)
    pct_list = ", ".join(str(q) for q in qs)
    grouped = sdf.groupBy("location_id", "variable_name", "unit_name").agg(
        F.expr(f"percentile(value, array({pct_list}))").alias("_pcts"),
        F.count("value").alias("n_values"),
        F.min("value_time").alias("por_start"),
        F.max("value_time").alias("por_end"),
    )

    # Long format -- one row per (location, variable, unit, quantile). Keeps the
    # table extensible to new quantiles without a schema change, and is the
    # shape a dashboard would want for "this gage's q95 is 12.4 m^3/s".
    pairs = ", ".join(f"{q}, _pcts[{i}]" for i, q in enumerate(qs))
    thresholds = (
        grouped.selectExpr(
            "location_id", "variable_name", "unit_name",
            "n_values", "por_start", "por_end",
            f"stack({len(qs)}, {pairs}) as (quantile, threshold_value)",
        )
        .withColumn("computed_at", F.current_timestamp())
    )

    # Materialize before creating the table. The exact-percentile scan over the
    # whole period of record is the slow part, and running it inside a CTAS
    # leaves the target table staged for the duration -- long enough for an
    # executor's vended S3 credentials to refresh against a table the catalog
    # cannot yet resolve, which fails the task with "Table does not exist".
    # The result is only a few rows per gage, so collecting it is cheap and
    # makes the CTAS itself near-instant.
    materialized = ev.spark.createDataFrame(
        thresholds.collect(), thresholds.schema
    )

    full_table_name = f"iceberg.teehr.{output_table_name}"
    materialized.createOrReplaceTempView("_nwmd_thresholds_src")
    ev.spark.sql(
        f"CREATE OR REPLACE TABLE {full_table_name} USING iceberg "
        f"AS SELECT * FROM _nwmd_thresholds_src"
    )
    ev.spark.sql("DROP VIEW IF EXISTS _nwmd_thresholds_src")
    ev.spark.sql(
        f"ALTER TABLE {full_table_name} SET TBLPROPERTIES ("
        f"'description' = 'Climatological high-flow thresholds per location, "
        f"from the primary_timeseries period of record')"
    )

    summary = ev.spark.sql(f"""
        SELECT count(DISTINCT location_id) AS locations,
               count(*) AS rows,
               min(n_values) AS min_obs_per_location,
               min(por_start) AS por_start,
               max(por_end) AS por_end
        FROM {full_table_name}
    """).collect()[0]
    print(
        f"Wrote {full_table_name}: {summary['rows']} rows for "
        f"{summary['locations']} locations, POR {summary['por_start']} to "
        f"{summary['por_end']}, fewest observations at any location: "
        f"{summary['min_obs_per_location']}"
    )
    print(f"{time.perf_counter() - start:.1f} s")
    return full_table_name
