"""
Kubernetes Job client for submitting analytics Spark jobs.

This module provides functions to create, monitor, and manage Kubernetes Jobs
that run Spark analytics workloads.
"""

import logging
import os
from typing import Optional

from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class K8sJobConfig:
    """Configuration for analytics Kubernetes Jobs."""

    # Namespace for running jobs
    NAMESPACE = os.environ.get("API_JOB_NAMESPACE", "teehr-hub")

    # Analytics driver image
    JOB_IMAGE = os.environ.get(
        "API_JOB_IMAGE",
        os.environ.get("TEEHR_SPARK_IMAGE", "")  # Fallback to Spark image
    )

    # Service account for jobs (reusing prefect-job which has IRSA)
    SERVICE_ACCOUNT = os.environ.get("API_JOB_SERVICE_ACCOUNT", "prefect-job")

    # Resource requests
    CPU_REQUEST = os.environ.get("API_JOB_CPU_REQUEST", "4")
    MEMORY_REQUEST = os.environ.get("API_JOB_MEMORY_REQUEST", "16Gi")
    CPU_LIMIT = os.environ.get("API_JOB_CPU_LIMIT", "8")
    MEMORY_LIMIT = os.environ.get("API_JOB_MEMORY_LIMIT", "32Gi")

    # Job configuration
    ACTIVE_DEADLINE_SECONDS = int(os.environ.get("API_JOB_TIMEOUT", "1200"))  # 20 min
    TTL_SECONDS_AFTER_FINISHED = int(os.environ.get("API_JOB_TTL", "3600"))  # 1 hour
    BACKOFF_LIMIT = int(os.environ.get("API_JOB_BACKOFF_LIMIT", "0"))  # No retries

    # Spark/teehr environment variables to pass through
    SPARK_IMAGE = os.environ.get("TEEHR_SPARK_IMAGE", "")
    SPARK_NAMESPACE = os.environ.get("TEEHR_NAMESPACE", "teehr-hub")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    REMOTE_CATALOG_REST_URI = os.environ.get("REMOTE_CATALOG_REST_URI", "")
    REMOTE_CATALOG_TYPE = os.environ.get("REMOTE_CATALOG_TYPE", "rest")
    REMOTE_WAREHOUSE_S3_PATH = os.environ.get("REMOTE_WAREHOUSE_S3_PATH", "")


def _load_k8s_config() -> None:
    """Load Kubernetes configuration.

    Tries in-cluster config first, falls back to local kubeconfig.
    """
    try:
        k8s_config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config")
    except k8s_config.ConfigException:
        try:
            k8s_config.load_kube_config()
            logger.info("Loaded local kubeconfig")
        except k8s_config.ConfigException as e:
            logger.error(f"Could not load Kubernetes config: {e}")
            raise


def _get_batch_api() -> client.BatchV1Api:
    """Get Kubernetes Batch API client."""
    _load_k8s_config()
    return client.BatchV1Api()


def _get_core_api() -> client.CoreV1Api:
    """Get Kubernetes Core API client."""
    _load_k8s_config()
    return client.CoreV1Api()


# ============================================================================
# Job Creation
# ============================================================================

def create_analytics_job(
    run_id: str,
    analytics_id: str,
    parameters_json: str,
    namespace: Optional[str] = None,
    image: Optional[str] = None,
    service_account: Optional[str] = None,
) -> str:
    """Create a Kubernetes Job to run an analytics Spark workload.

    Parameters
    ----------
    run_id : str
        Unique identifier for this analytics run.
    analytics_id : str
        Type of analytics to run (e.g., "custom_metrics").
    parameters_json : str
        JSON-serialized analytics parameters.
    namespace : str, optional
        Kubernetes namespace. Defaults to API_JOB_NAMESPACE.
    image : str, optional
        Container image to use. Defaults to API_JOB_IMAGE.
    service_account : str, optional
        Service account to use. Defaults to API_JOB_SERVICE_ACCOUNT.

    Returns
    -------
    str
        Name of the created Job.
    """
    cfg = K8sJobConfig()

    namespace = namespace or cfg.NAMESPACE
    image = image or cfg.JOB_IMAGE
    service_account = service_account or cfg.SERVICE_ACCOUNT

    if not image:
        raise ValueError("No job image configured. Set API_JOB_IMAGE or TEEHR_SPARK_IMAGE.")

    # Job name: teehr-analytics-{first 8 chars of run_id}
    job_name = f"teehr-analytics-{run_id[:8]}"

    # Environment variables for the analytics driver
    env_vars = [
        client.V1EnvVar(name="RUN_ID", value=run_id),
        client.V1EnvVar(name="ANALYTICS_ID", value=analytics_id),
        client.V1EnvVar(name="PARAMETERS_JSON", value=parameters_json),
        # Spark/teehr config
        client.V1EnvVar(name="TEEHR_SPARK_IMAGE", value=cfg.SPARK_IMAGE),
        client.V1EnvVar(name="TEEHR_NAMESPACE", value=cfg.SPARK_NAMESPACE),
        client.V1EnvVar(name="AWS_REGION", value=cfg.AWS_REGION),
        client.V1EnvVar(name="REMOTE_CATALOG_REST_URI", value=cfg.REMOTE_CATALOG_REST_URI),
        client.V1EnvVar(name="REMOTE_CATALOG_TYPE", value=cfg.REMOTE_CATALOG_TYPE),
        client.V1EnvVar(name="REMOTE_WAREHOUSE_S3_PATH", value=cfg.REMOTE_WAREHOUSE_S3_PATH),
        client.V1EnvVar(name="IN_CLUSTER", value="true"),
    ]

    # Container spec
    container = client.V1Container(
        name="analytics-driver",
        image=image,
        image_pull_policy="Always",
        command=["python", "-m", "spark_analytics_driver"],
        env=env_vars,
        resources=client.V1ResourceRequirements(
            requests={
                "cpu": cfg.CPU_REQUEST,
                "memory": cfg.MEMORY_REQUEST,
            },
            limits={
                "cpu": cfg.CPU_LIMIT,
                "memory": cfg.MEMORY_LIMIT,
            },
        ),
        security_context=client.V1SecurityContext(
            run_as_user=1000,
            run_as_group=1000,
            allow_privilege_escalation=False,
        ),
    )

    # Pod spec
    pod_spec = client.V1PodSpec(
        service_account_name=service_account,
        restart_policy="Never",
        containers=[container],
        security_context=client.V1PodSecurityContext(
            run_as_user=1000,
            run_as_group=1000,
            fs_group=1000,
        ),
        tolerations=[
            client.V1Toleration(
                key="teehr-hub/dedicated",
                operator="Equal",
                value="worker",
                effect="NoSchedule",
            ),
            client.V1Toleration(
                key="teehr-hub_dedicated",
                operator="Equal",
                value="worker",
                effect="NoSchedule",
            ),
        ],
        node_selector={
            "teehr-hub/nodegroup-name": "spark-r5-4xlarge",
        },
    )

    # Job spec
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=job_name,
            namespace=namespace,
            labels={
                "app": "teehr-analytics",
                "run-id": run_id,
                "analytics-id": analytics_id,
            },
        ),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app": "teehr-analytics",
                        "run-id": run_id,
                    },
                ),
                spec=pod_spec,
            ),
            active_deadline_seconds=cfg.ACTIVE_DEADLINE_SECONDS,
            ttl_seconds_after_finished=cfg.TTL_SECONDS_AFTER_FINISHED,
            backoff_limit=cfg.BACKOFF_LIMIT,
        ),
    )

    # Create the job
    batch_api = _get_batch_api()
    try:
        batch_api.create_namespaced_job(namespace=namespace, body=job)
        logger.info(f"Created analytics job {job_name} for run {run_id}")
        return job_name
    except ApiException as e:
        logger.error(f"Failed to create job {job_name}: {e}")
        raise


# ============================================================================
# Job Status
# ============================================================================

def get_job_status(
    run_id: str,
    namespace: Optional[str] = None,
) -> dict:
    """Get status of an analytics job.

    Parameters
    ----------
    run_id : str
        The analytics run ID.
    namespace : str, optional
        Kubernetes namespace.

    Returns
    -------
    dict
        Job status with keys:
        - exists: bool
        - status: "pending" | "running" | "succeeded" | "failed" | "unknown"
        - job_name: str or None
        - start_time: datetime or None
        - completion_time: datetime or None
        - message: str or None
    """
    cfg = K8sJobConfig()
    namespace = namespace or cfg.NAMESPACE
    job_name = f"teehr-analytics-{run_id[:8]}"

    batch_api = _get_batch_api()

    try:
        job = batch_api.read_namespaced_job(name=job_name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            return {
                "exists": False,
                "status": "unknown",
                "job_name": None,
                "start_time": None,
                "completion_time": None,
                "message": "Job not found",
            }
        raise

    status = job.status
    result = {
        "exists": True,
        "job_name": job_name,
        "start_time": status.start_time,
        "completion_time": status.completion_time,
        "message": None,
    }

    # Determine status
    if status.succeeded and status.succeeded > 0:
        result["status"] = "succeeded"
    elif status.failed and status.failed > 0:
        result["status"] = "failed"
        # Try to get failure reason from conditions
        if status.conditions:
            for cond in status.conditions:
                if cond.type == "Failed" and cond.status == "True":
                    result["message"] = cond.message
    elif status.active and status.active > 0:
        result["status"] = "running"
    else:
        result["status"] = "pending"

    return result


def get_job_logs(
    run_id: str,
    namespace: Optional[str] = None,
    tail_lines: int = 100,
) -> Optional[str]:
    """Get logs from an analytics job's pod.

    Parameters
    ----------
    run_id : str
        The analytics run ID.
    namespace : str, optional
        Kubernetes namespace.
    tail_lines : int
        Number of lines to return from end of log.

    Returns
    -------
    str or None
        Log output, or None if pod not found.
    """
    cfg = K8sJobConfig()
    namespace = namespace or cfg.NAMESPACE

    core_api = _get_core_api()

    # Find pod by label selector
    label_selector = f"run-id={run_id}"

    try:
        pods = core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
        )
    except ApiException:
        return None

    if not pods.items:
        return None

    # Get logs from the first (should be only) pod
    pod_name = pods.items[0].metadata.name

    try:
        logs = core_api.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
        )
        return logs
    except ApiException:
        return None


def delete_job(
    run_id: str,
    namespace: Optional[str] = None,
) -> bool:
    """Delete an analytics job and its pods.

    Parameters
    ----------
    run_id : str
        The analytics run ID.
    namespace : str, optional
        Kubernetes namespace.

    Returns
    -------
    bool
        True if job was deleted, False if not found.
    """
    cfg = K8sJobConfig()
    namespace = namespace or cfg.NAMESPACE
    job_name = f"teehr-analytics-{run_id[:8]}"

    batch_api = _get_batch_api()

    try:
        batch_api.delete_namespaced_job(
            name=job_name,
            namespace=namespace,
            propagation_policy="Background",  # Also delete pods
        )
        logger.info(f"Deleted job {job_name}")
        return True
    except ApiException as e:
        if e.status == 404:
            return False
        raise
