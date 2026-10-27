# Single-service image for hosting (Render etc): builds the React app, then serves it from FastAPI.
FROM node:22-alpine AS fe
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY ingestion ingestion
COPY ml ml
COPY scripts scripts
COPY --from=fe /fe/dist frontend/dist
ENV PYTHONUNBUFFERED=1
# seed is idempotent (skips existing users/items); passwords come from SEED_*_PASSWORD env vars
CMD ["sh", "-c", "python -m scripts.seed_demo_data; uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
