# TEEHR Cloud
TEEHR Cloud is a coordinated set of services built around the Tools for Exploratory Evaluation in Hydrologic Research (TEEHR) to support large scale data analytics for the purpose of evaluating hydrologic model performance.

TEEHR Cloud utilizes Kubernetes to orchestrate the services that make up the system.  The primary components are:
- JupyterHub
- Prefect
- Apache Iceberg
- Apache Spark
- Trino
- FastAPI
- React


## Local Development
For local development developers can run a local instance of the cluster using KinD.  You will need to have the following installed.  The versions shown are known to work for our developers.  Subsequent minor and bug fix releases should also work but your milage may vary.

KinD https://kind.sigs.k8s.io/
```bash
% kind version
kind v0.27.0 go1.24.0 darwin/arm64
```

Garden https://docs.garden.io/getting-started/quickstart
```bash
% garden version
garden version: 0.13.54
```

kubctl https://kubernetes.io/docs/tasks/tools/
```bash
% kubectl version
Client Version: v1.32.3
Kustomize Version: v5.5.0
Server Version: v1.32.2
```

Optional, but recommended, k9s https://k9scli.io/
```bash
 % k9s version
 ____  __ ________       
|    |/  /   __   \______
|       /\____    /  ___/
|    \   \  /    /\___  \
|____|\__ \/____//____  /
         \/           \/ 

Version:    v0.50.2
Commit:     bc22b8705304b86c2f4c417a088accdfed13fdf8
Date:       2025-04-10T15:32:12Z
```

After you have the dependencies above installed you should be able to create a kind cluster by running the following from the repo root.
```bash
./kind/create_kind_cluster.sh 
```

If the kind cluster creation is successful, you can then run the following to deploy the application to the local cluster:
```bash
garden deploy
```

This should create all the services in the cluster.  To test, open a browser and go to `https://api.teehr.local.app.garden`. Two notes:
1) We use a self-sign certificate for local development so you will have to accept it in your browser. Specifically, you will need to do so for the API before the dashboards will work by going to `api.teehr.local.app.garden` and accepting the self-signed cert.
2) Note you may need to edit your `/etc/hosts` file to have this address point to localhost.  You likely need the following entries in your `/etc/hosts` file.

```bash
# Add for TEEHR-HUB development
127.0.0.1       hub.teehr.local.app.garden
127.0.0.1       minio.teehr.local.app.garden
127.0.0.1       dashboards.teehr.local.app.garden
127.0.0.1       api.teehr.local.app.garden
127.0.0.1       panel.teehr.local.app.garden
```

### Load Test Data to Warehouse
Loading data is a little fractured depending on what data you are loading.  For the purpose of developing there are 2 different types of data that can be loaded. Regardless, you first need to create an Iceberg warehouse in the KinD cluster, then load some data.

1) To create the Iceberg warehouse and load some historic simulation data, start by going to the JupyterHub environment `hub.teehr.local.app.garden` and logging in with username: `user` and password: `password`.

2) Copy the following notebooks to JupyterHub and run them in order.  This will create an Iceberg data warehouse in the KinD cluster and populate it with historic observations and simulations for 10 sites.
- `examples/01_setup_minio_warehouse.ipynb`
- `examples/02_create_joined_timeseries.ipynb`
- `examples/03_generate_basic_metrics.ipynb`

3) To load some recent (but not too recent forecasts).  This involves port forwarding the Prefect service to localhost, going to Prefect in the browser and executing a couple of workflows.

```bash
kubectl config use-context kind-kind
kubectl port-forward -n teehr-hub svc/prefect-server 4200:4200
```

Open your browser and go to http://localhost:4200.  Navigate to `Deployments`.

1) Click on `ingest-usgs-streamflow-obs`.  In the upper right corner select Run > Custom Run.  Change the num_lookback_days to 10 and Submit.  Monitor the run through the browser UI.  When done, proceed to the next one.

2) Click on `ingest-nwm-medium-range-streamflow-forecasts`. In the upper right corner select Run > Custom Run.  Change the end_dt to a date approximately 9 days prior to today and Submit.  Monitor the run through the browser UI.  When done, proceed to the next one.

3) Click on `update-joined-forecast-table`. In the upper right corner select Run > Quick Run. Run with the default parameters.

4) Click on `update-forecast-metrics-table`. In the upper right corner select Run > Quick Run. Run with the default parameters.

Now go to `https://dashboards.teehr.local.app.garden`.  You should be able to go to both the retrospective and forecast dashboards and see some data.

Now the fun of adding new features and bug fixes starts.

### Code Syncing
When working on the API or the frontend it is convenient to have code syncing.  Code syncing can be done in `garden` by running:
```bash
garden deploy --sync
```

### Using External Docker Images in JupyterHub locally

The JupyterHub deployment supports two types of image configurations:

**Built-in Images** (e.g., TEEHR Evaluation System) are automatically built and managed by Garden using build actions. **External Images** (e.g., HEFS-FEWS Evaluation System) are built outside this project and must be manually loaded into the Kind cluster when locally tested.

#### Loading External Images into Kind

When using external images in JupyterHub profiles, load them into the Kind cluster:

```bash
# Build your image locally (or pull from a registry)
docker build -t hefs-hub:0.3.0 /path/to/external-project

# Load the image into the Kind cluster
kind load docker-image hefs-hub:0.3.0 --name kind

# Verify the image is loaded
docker exec -it kind-control-plane crictl images | grep hefs-hub
```

**Key Configuration Points for such images:**
- Set `image_pull_policy: IfNotPresent` (or `Never`) in `kubespawner_override` to prevent Kubernetes from attempting to pull from Docker Hub
- Use static image names (e.g., `"hefs-hub:0.3.0"`) without registry prefix
- External images must include the `jupyterhub` package in their Python environment to provide the `jupyterhub-singleuser` command

When you rebuild an external image, reload it into Kind and restart any running pods using that image.

## Remote Deployment

This section will walk you through standing up the `teehr-hub`` in an AWS account.
The instructions should generally work with other providers, but some steps will certainly be different.

NOTE: you must clean up complete from other approaches before running this.

Login to AWS.  You need to login with a user that has sufficient permissions.
We used Admin for testing but need to determine the minimum set of permissions needed.
```bash
aws configure
```

Plan Terraform (can take ~15 mins)
```bash
cd terraform
terraform init
terraform plan -var-file=teehr-hub.tfvars
cd ..
```

Plan Terraform (can take ~15 mins)
```bash
cd terraform
terraform apply -var-file=teehr-hub.tfvars
cd ..
```

Connect to cluster
```bash
export AWS_PROFILE=ciroh_mdenno
aws eks update-kubeconfig --name teehr-hub --region us-east-2 --role-arn arn:aws:iam::935462133478:role/teehr-hub-teehr-hub-admin
kubectl config set-context $(kubectl config current-context) --namespace teehr-hub
k9s
```

After the cluster is setup in an AWS account, you can deploy using the GitHub Actions.