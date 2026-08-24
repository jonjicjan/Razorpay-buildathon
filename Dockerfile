# syntax=docker/dockerfile:1

# --- frontend build ---
FROM node:20-alpine AS frontend
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ ./
RUN npm run build

# --- api + static UI ---
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY ml ./ml
COPY data ./data
COPY evaluation ./evaluation
COPY docs ./docs

COPY --from=frontend /ui/dist ./frontend/dist

ENV PYTHONPATH=/app
ENV PORT=8000
EXPOSE 8000

# Include trained model + metrics in the image (needed for scoring / Metrics tab).
# Ensure ml/artifacts/xgb.joblib and evaluation/metrics.json exist before build.

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
