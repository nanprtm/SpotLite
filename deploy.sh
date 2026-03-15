#!/bin/bash
set -e

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="spotlite"

echo "Building and deploying SpotLite to Cloud Run..."

gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE_NAME" --project "$PROJECT_ID" .

gcloud run deploy "$SERVICE_NAME" \
    --image "gcr.io/$PROJECT_ID/$SERVICE_NAME" \
    --platform managed \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --allow-unauthenticated \
    --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION" \
    --port 8080 \
    --memory 1Gi \
    --timeout 900 \
    --session-affinity \
    --min-instances 0 \
    --max-instances 3

echo ""
echo "Deployed! Service URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID" --format="value(status.url)"
