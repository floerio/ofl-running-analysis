#!/usr/bin/env bash
# deploy.sh — Build image on Mac, push to GHCR, deploy to VPS
# Usage: ./deploy.sh

set -euo pipefail

IMAGE="ghcr.io/floerio/ofl-running-analysis:latest"
VPS="ht2-cmd"
APP_DIR="~/apps/ofl-running-analysis"

echo "[1/3] Building image..."
docker build --platform linux/amd64 -t "$IMAGE" .

echo "[2/3] Pushing to GitHub Container Registry..."
docker push "$IMAGE"

echo "[3/3] Deploying on VPS..."
ssh -t "$VPS" "docker pull $IMAGE && cd $APP_DIR && docker compose up -d"

echo "Done! App is live."
