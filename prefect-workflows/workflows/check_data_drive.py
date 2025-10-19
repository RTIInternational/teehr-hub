from prefect import flow
import os
import time

@flow(flow_run_name="list-data-drive", log_prints=True)
def list() -> None:
    """List contents of /data:"""
    print("Contents of /data:")
    for entry in os.listdir("/data"):
        print(entry)
    
    # time.sleep(10)