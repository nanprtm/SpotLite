#!/bin/bash
set -e

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="stage-buddy"

echo "Building and deploying to Cloud Run..."

gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE_NAME" .

gcloud run deploy "$SERVICE_NAME" \
    --image "gcr.io/$PROJECT_ID/$SERVICE_NAME" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY" \
    --port 8080 \
    --memory 512Mi \
    --timeout 300

echo "Deployed! Service URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)"
