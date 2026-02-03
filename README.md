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
For local development developers can run a local instance of the cluster using KinD.  You will need to have the following installed:

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

After you have KinD, Gardem and kubctl installed you should be able to create a kind cluster by running the following from the repo root.
```bash
./kind/create_kind_cluster.sh 
```

If the kind cluster creation is successful, you can then run the following:
```bash
garden deploy
```

This should create all the services in the cluster.  To test, open a browser and go to `https://hub.teehr.local.app.garden`.  Note you may need to edit your `/etc/hosts` file to have this address point to localhost.  You likely need the following entries in your `/etc/hosts` file.

```bash
% cat /etc/hosts

...

# Add for TEEHR-HUB development
127.0.0.1       hub.teehr.local.app.garden
127.0.0.1       minio.teehr.local.app.garden
127.0.0.1       dashboards.teehr.local.app.garden
127.0.0.1       api.teehr.local.app.garden
127.0.0.1       panel.teehr.local.app.garden
```

We use a self-sign certificate for local development so you will have to accept it in your browser for each URL.  Specifically, you will need to do so for the API before the dashboards will work by going to `api.teehr.local.app.garden` and accepting the self-signed cert.

### Load Test Data to Warehouse
Coming soon

### Code Syncing
When working on the API or the frontend it is convenient to have code syncing.  Code syncing can be done in `garden` by running:
```bash
garden deploy --sync
```

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