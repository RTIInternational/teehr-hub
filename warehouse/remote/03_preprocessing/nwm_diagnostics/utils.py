"""Cluster-sizing instrumentation and pod templates for the NWM diagnostics runs.

The metrics pipeline itself (`generate_nwmd_metrics`) lives in nwmd_metrics.ipynb,
so this module holds only helpers that are useful across notebooks and that the
notebook pulls in via the raw.githubusercontent download in its second cell.
"""

import os
import json
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timezone

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

def create_ondemand_pod_template(ephemeral_storage_request="20Gi"):
    """Create a pod template for on-demand Spark executors.

    Args:
        ephemeral_storage_request (str): Disk to reserve per executor for shuffle
            (SPARK_LOCAL_DIRS). See the note below -- this is not cosmetic.

    Returns:
        str: Path to the generated pod template YAML file.
    """

    # Alternate executor pod template targeting the ON-DEMAND `nb-r5-4xlarge-teehr`
    # node group instead of the spot `spark-r5-4xlarge-spot` pool, for tuning runs
    # where we want clean measurements without spot-interruption noise. Same
    # instance type (r5.4xlarge) so executor sizing math stays comparable to prior
    # spot-based runs. Different taint on this node group (hub.jupyter.org/dedicated
    # =user vs teehr-hub/dedicated=worker), so it needs its own tolerations.
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
    # the requested amount. At 20Gi that is ~3 executors per r5.4xlarge.
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

    print(
        f"Wrote alternate pod template to {ONDEMAND_POD_TEMPLATE_PATH} "
        f"(ephemeral-storage request: {ephemeral_storage_request})"
    )
    return ONDEMAND_POD_TEMPLATE_PATH
