#!/usr/bin/env bash
set -e

echo "👉 Building containers..."
docker compose build

echo "👉 Starting stack..."
docker compose up -d

echo "✅ Secure-RAG is running!"
echo "   - Backend API: http://localhost:8000"
echo "   - Frontend UI: http://localhost:3000"
