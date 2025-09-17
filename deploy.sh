#!/bin/bash

# LumaHealth Deployment Script for Google Cloud Run
# Usage: ./deploy.sh [PROJECT_ID] [REGION]

set -e

# Default values
PROJECT_ID="${1:-your-project-id}"
REGION="${2:-us-central1}"
SERVICE_NAME="lumahealth-api"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying LumaHealth to Google Cloud Run"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install it first."
    exit 1
fi

# Set project
echo "🔧 Setting project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Build and push Docker image
echo "🏗️  Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .

echo "📤 Pushing to Container Registry..."
docker push ${IMAGE_NAME}:latest

# Create secret for Anthropic API key (if not exists)
echo "🔐 Setting up secrets..."
if ! gcloud secrets describe anthropic-api-key &> /dev/null; then
    echo "Creating new secret for Anthropic API key..."
    echo "Please enter your Anthropic API key:"
    read -s ANTHROPIC_API_KEY
    echo "${ANTHROPIC_API_KEY}" | gcloud secrets create anthropic-api-key --data-file=-
else
    echo "Secret 'anthropic-api-key' already exists."
fi

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --max-instances 10 \
    --set-env-vars ENVIRONMENT=production,DEBUG=false,LOG_LEVEL=info \
    --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')

echo ""
echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: ${SERVICE_URL}"
echo "🔍 Health check: ${SERVICE_URL}/health"
echo "💬 Chat interface: ${SERVICE_URL}"
echo ""
echo "📊 To view logs:"
echo "gcloud logs tail --follow --service=${SERVICE_NAME}"
echo ""
echo "🎛️  To update secrets:"
echo "echo 'NEW_API_KEY' | gcloud secrets versions add anthropic-api-key --data-file=-"
