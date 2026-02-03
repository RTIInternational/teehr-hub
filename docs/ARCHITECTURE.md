# Architecture and Code Organization

AWS Services
- ECR
    - Store all built containers needed
- ECS
    - Iceberg rest server
    - Trino database engine
- S3
    - Store raw data
    - Store iceberg warehouse
- VPC
    - S3 VPC Gateway Endpoint
        - Enables cost-free data transfer from S3 (e.g., s3://noaa-nwm-retrospective-3-0-pds/)
        - Routes S3 traffic through AWS internal network instead of internet gateway
- EKS
    - JupyterHub with TEEHR
    - Spark executors
    - Prefect
    - Apply migrations job?
- EFS
    - Data drive


GitHub Repos
- teehr
    - Main TEEHR codebase that contains code to:
        - Manage local data warehouse schema
        - Ingest timeseries from common sources
        - Query timeseries/generate complex aggregates
    - Workflows to:
        - Build TEEHR docs
        - Build and publish pip package
        - Trigger TEEHR-HUB build (main, v0.6-dev)
        - Trigger on any new tag -> builds image, deploys to TH
- teehr-hub
    - Terraform for EKS, S3, EFS (TEEHR-HUB)
    - Garden for (currently Helm and kubernetes manifests):
        - JupyterHub
        - Spark executors
        - Prefect (future)
    - GH Workflows to:
        - Deploy Garden (currently just Helm)
        - Build TEEHR-HUB Jupyter image
        - Build TEEHR-SPARK executor image
    - Prefect workflows using TEEHR to (want code in this repo or just infra?):
        - Ingest USGS obs
        - Operational NWM
        - Research datastream
        - Pre-process metrics
    - Notebooks used to ingest one-off data (again, here?)
    - Do we need an all-local dev option?
    - Maybe best if this primarily focuses on infra?
- teehr-eaas
    - Mainly Iceberg warehouse
    - Terraform for ECS, S3
    - GH Workflows to:
        - Build Iceberg
        - Build Trino
        - Build TEEHR-MIGRATOR image?
    - Migrations (maybe here instead of TEEHR-HUB)
        - Uses TEEHR
        - Schema changes
        - Optimizations
    Local options in docker-compose to test?