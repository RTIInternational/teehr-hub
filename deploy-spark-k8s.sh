#!/bin/bash

# Spark on Kubernetes Deployment Script
# This script deploys the necessary Kubernetes resources for Spark

set -e

NAMESPACE="spark"
IMAGE_TAG="dev"
REGISTRY="935462133478.dkr.ecr.us-east-2.amazonaws.com/teehr"

echo "🚀 Deploying Spark on Kubernetes for TEEHR Hub"
echo "================================================"

# Create namespace if it doesn't exist
echo "📦 Creating namespace: $NAMESPACE"
kubectl apply -f kubernetes/spark-namespace.yaml

# Apply Spark RBAC configuration
echo "🔐 Applying Spark RBAC configuration..."
kubectl apply -f kubernetes/spark-roles.yaml

# Apply Spark configuration
echo "⚙️  Applying Spark configuration..."
kubectl apply -f kubernetes/spark-config.yaml

# Apply Spark PVC for shared data access
echo "💾 Creating PVC for shared data access..."
kubectl apply -f kubernetes/spark-pvc.yaml

# Apply Jupyter-Spark RBAC for cross-namespace permissions
echo "🔐 Applying Jupyter-Spark RBAC configuration..."
kubectl apply -f kubernetes/jupyter-spark-rbac.yaml

# Check if the image exists (optional)
echo "🔍 Checking container image..."
if docker manifest inspect $REGISTRY:$IMAGE_TAG > /dev/null 2>&1; then
    echo "✅ Container image $REGISTRY:$IMAGE_TAG exists"
else
    echo "⚠️  Container image $REGISTRY:$IMAGE_TAG not found"
    echo "   Please build and push the image:"
    echo "   docker build -t $REGISTRY:$IMAGE_TAG ."
    echo "   docker push $REGISTRY:$IMAGE_TAG"
fi

# Verify deployment
echo "🔍 Verifying deployment..."

# Check ServiceAccount
if kubectl get serviceaccount spark -n $NAMESPACE > /dev/null 2>&1; then
    echo "✅ ServiceAccount 'spark' created successfully"
else
    echo "❌ Failed to create ServiceAccount 'spark'"
    exit 1
fi

# Check Role
if kubectl get role spark-role -n $NAMESPACE > /dev/null 2>&1; then
    echo "✅ Role 'spark-role' created successfully"
else
    echo "❌ Failed to create Role 'spark-role'"
    exit 1
fi

# Check ClusterRole
if kubectl get clusterrole spark-cluster-role > /dev/null 2>&1; then
    echo "✅ ClusterRole 'spark-cluster-role' created successfully"
else
    echo "❌ Failed to create ClusterRole 'spark-cluster-role'"
    exit 1
fi

# Check ConfigMap
if kubectl get configmap spark-config -n $NAMESPACE > /dev/null 2>&1; then
    echo "✅ ConfigMap 'spark-config' created successfully"
else
    echo "❌ Failed to create ConfigMap 'spark-config'"
    exit 1
fi

# Check Service
if kubectl get service spark-driver-headless -n $NAMESPACE > /dev/null 2>&1; then
    echo "✅ Service 'spark-driver-headless' created successfully"
else
    echo "❌ Failed to create Service 'spark-driver-headless'"
    exit 1
fi

# Check Jupyter-Spark RBAC bindings
if kubectl get clusterrolebinding jupyter-default-spark-cluster-role-binding > /dev/null 2>&1; then
    echo "✅ ClusterRoleBinding for default serviceaccount created successfully"
else
    echo "❌ Failed to create ClusterRoleBinding for default serviceaccount"
    exit 1
fi

echo ""
echo "🎉 Spark on Kubernetes deployment completed successfully!"
echo ""
echo "Next steps:"
echo "1. Build and push the container image with Spark:"
echo "   docker build -t $REGISTRY:$IMAGE_TAG ."
echo "   docker push $REGISTRY:$IMAGE_TAG"
echo ""
echo "2. Update your JupyterHub configuration to use the new image"
echo ""
echo "3. Use the spark_k8s_helper module in your Jupyter notebooks:"
echo "   from spark_k8s_helper import create_spark_session"
echo "   spark = create_spark_session(app_name='my-app')"
echo ""
echo "📖 See docs/spark-kubernetes-setup.md for detailed usage instructions"
echo "📓 Check examples/spark-kubernetes-example.ipynb for a complete example"