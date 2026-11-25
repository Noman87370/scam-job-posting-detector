# Two-stage build: Node builds the React frontend, Python runs the API.
# The production build lands in backend/static and is served by FastAPI,
# so the whole platform is a single service.
#
# The model is NOT retrained here: the app loads the committed artifact
# model/model_artifacts.joblib (exported from the research notebook).
# Retraining is a separate, deliberate step — see train/train_model.py.

FROM node:24-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm install --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && npm run build

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
COPY model ./model
COPY --from=frontend-build /app/backend/static ./backend/static
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
