from prefect import flow, tags

@flow(flow_run_name="hello-{name}", log_prints=True)
def hello(name: str = "Marvin") -> None:
    """Log a friendly greeting."""
    print(f"Hello, {name}!")