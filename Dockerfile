# Multi-stage build: Node builds the React frontend, Python runs the API.
# The production build lands in backend/static and is served by FastAPI,
# so the whole platform is a single service.

FROM node:24-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm install --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && npm run build

# Train stage: reproduces the model artifacts at build time, so the binary
# .joblib files never need to be committed. Downloads the public Kaggle
# dataset via kagglehub (no auth needed) and runs the same pipeline as
# the research notebook.
FROM python:3.12-slim AS model-train
WORKDIR /app
COPY train/requirements.txt ./train-requirements.txt
RUN pip install --no-cache-dir -r train-requirements.txt
COPY common ./common
COPY train ./train
RUN python train/train_model.py

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY common ./common
COPY --from=model-train /app/model ./model
COPY --from=frontend-build /app/backend/static ./backend/static
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
