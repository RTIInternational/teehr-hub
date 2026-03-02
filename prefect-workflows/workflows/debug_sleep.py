"""Debug flow that sleeps to allow shelling into the pod."""
import time
from prefect import flow, get_run_logger


@flow
def debug_sleep(sleep_seconds: int = 1800):
    """Sleep to keep the pod alive for debugging."""
    logger = get_run_logger()
    logger.info(f"Debug pod running. Sleeping for {sleep_seconds}s...")
    logger.info("Shell in with: kubectl exec -it <pod-name> -- /bin/bash")
    time.sleep(sleep_seconds)
    logger.info("Debug sleep complete.")
