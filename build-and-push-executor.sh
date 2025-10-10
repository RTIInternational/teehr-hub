#!/bin/bash

# Build and push TEEHR image with Spark binaries
# This fixes the "executor: not found" error

REGISTRY="935462133478.dkr.ecr.us-east-2.amazonaws.com"
NAMESPACE="teehr-spark"
IMAGE_NAME="teehr-spark-executor"
TAG="latest"

echo "🏗️  Building TEEHR image with Spark binaries..."
echo "📦 Image: ${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${TAG}"

# Build the image
docker build --platform linux/amd64 -t ${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${TAG} -f ./Dockerfile.spark-executor .

if [ $? -eq 0 ]; then
    echo "✅ Image built successfully!"
    
    # Login to ECR
    echo "🔐 Logging into ECR..."
    aws ecr get-login-password --region us-east-2 --profile ciroh_mdenno | docker login --username AWS --password-stdin ${REGISTRY}
    
    # Create repository if it doesn't exist
    echo "📦 Ensuring ECR repository exists..."
    aws ecr describe-repositories --repository-names ${IMAGE_NAME} --region us-east-2 --profile ciroh_mdenno || \
    aws ecr create-repository --repository-name ${IMAGE_NAME} --region us-east-2 --profile ciroh_mdenno
    
    # Push image
    echo "🚀 Pushing to ECR..."
    docker push ${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${TAG}
    
    echo "✅ Image pushed successfully!"
    echo "🎯 Updated image: ${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${TAG}"
    echo ""
    echo "Now restart your Jupyter pod to use the new image:"
    echo "kubectl delete pod <your-jupyter-pod> -n teehr-hub"
else
    echo "❌ Build failed!"
    exit 1
fi