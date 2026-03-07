region = "us-east-2"

cluster_name = "teehr-hub"

cluster_nodes_location = "us-east-2a"

cluster_version = "1.32"

environment = "dev"

project_name = "teehr"

# CIROH project IDs for dedicated node groups
# Each project ID will create: nb-r5-xlarge-{id}, nb-r5-4xlarge-{id}, spark-r5-4xlarge-spot-{id}
# Example: project_ids = ["MMM", "ABC", "XYZ"]
project_ids = ["MMM", "Testbed", "FIRO", "ResOps"]