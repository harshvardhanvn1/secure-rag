# syntax=docker/dockerfile:1
FROM python:3.9-slim

# System deps (build-essential helps for some wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m spacy download en_core_web_sm

# Copy source
COPY . /app

# Expose API port
EXPOSE 8000

# Default DSN for compose (override with env)
ENV POSTGRES_DSN=postgresql://postgres:postgres@db:5432/securerag
ENV HF_HOME=/app/.cache/hf

# Start API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
